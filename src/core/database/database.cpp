// SQLite index implementation. WAL, foreign_keys, synchronous=NORMAL.
// All writes that belong together use explicit transactions at call sites.
#include "database.h"

#include <algorithm>
#include <chrono>
#include <cstring>
#include <map>
#include <spdlog/spdlog.h>

#include "sqlite3.h"

namespace aiorg::db {
namespace {

void ThrowIf(int rc, sqlite3* db, const char* what, std::string& err) {
  if (rc != SQLITE_OK && rc != SQLITE_DONE && rc != SQLITE_ROW) {
    err = std::string(what) + ": " + sqlite3_errmsg(db);
    throw std::runtime_error(err);
  }
}

constexpr const char* kSchema = R"(
CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  filename TEXT NOT NULL,
  extension TEXT NOT NULL,
  size INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  volume_serial INTEGER NOT NULL DEFAULT 0,
  file_index INTEGER NOT NULL DEFAULT 0,
  file_type TEXT NOT NULL DEFAULT '',
  hash_status TEXT NOT NULL DEFAULT 'pending',
  scan_status TEXT NOT NULL DEFAULT 'new',
  ai_status TEXT NOT NULL DEFAULT 'pending',
  last_seen_ms INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_files_size ON files(size);
CREATE INDEX IF NOT EXISTS idx_files_scan ON files(scan_status);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash_status);
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, root TEXT NOT NULL,
  started_ms INTEGER NOT NULL, ended_ms INTEGER NOT NULL DEFAULT 0,
  summary TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS errors(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL, stage TEXT NOT NULL,
  path TEXT NOT NULL, message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_errors_stage ON errors(stage);
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hashes(
  path TEXT PRIMARY KEY, size INTEGER NOT NULL, sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hash_stages(
  path TEXT NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
  stage INTEGER NOT NULL, sha256 TEXT NOT NULL,
  PRIMARY KEY(path, stage)
);
CREATE INDEX IF NOT EXISTS idx_hash_stages ON hash_stages(stage, sha256);
-- v3 unified: duplicates / moves / jobs / behavior / docs (shared with engine-py).
CREATE TABLE IF NOT EXISTS duplicate_groups(
  id INTEGER PRIMARY KEY, size INTEGER NOT NULL,
  sha256 TEXT NOT NULL DEFAULT '', created_ms INTEGER NOT NULL,
  UNIQUE(size, sha256)
);
CREATE TABLE IF NOT EXISTS dupe_members(
  group_id INTEGER NOT NULL REFERENCES duplicate_groups(id) ON DELETE CASCADE,
  path TEXT NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
  PRIMARY KEY(group_id, path)
);
CREATE INDEX IF NOT EXISTS idx_dupe_members_path ON dupe_members(path);
CREATE TABLE IF NOT EXISTS moves(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL,
  group_id INTEGER NOT NULL DEFAULT 0, src TEXT NOT NULL, dst TEXT NOT NULL,
  size INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'moved',
  rollback TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending', created_ms INTEGER NOT NULL,
  started_ms INTEGER NOT NULL DEFAULT 0, ended_ms INTEGER NOT NULL DEFAULT 0,
  result TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, id);
CREATE TABLE IF NOT EXISTS behavior_events(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL, kind TEXT NOT NULL,
  path TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_behavior_kind ON behavior_events(kind, t_ms);
CREATE TABLE IF NOT EXISTS behavior_prefs(
  key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS doc_index(
  path TEXT PRIMARY KEY, kategori TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0, ringkasan TEXT NOT NULL DEFAULT '',
  saran_nama TEXT NOT NULL DEFAULT '', updated_ms INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS doc_feedback(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL, path TEXT NOT NULL,
  kategori TEXT NOT NULL, teks_hash TEXT NOT NULL DEFAULT ''
);
-- v4: proposal organizer (master #150) + audit tahan lama + checkpoint jobs.
CREATE TABLE IF NOT EXISTS proposals(
  id INTEGER PRIMARY KEY, created_ms INTEGER NOT NULL,
  batch TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'move',
  action TEXT NOT NULL DEFAULT 'move', group_id INTEGER NOT NULL DEFAULT 0,
  src TEXT NOT NULL, dst TEXT NOT NULL,
  reasons TEXT NOT NULL DEFAULT '', risk TEXT NOT NULL DEFAULT 'low',
  status TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status, batch);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, src TEXT NOT NULL DEFAULT '',
  dst TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT 'ok',
  detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, t_ms);
CREATE TABLE IF NOT EXISTS job_checkpoints(
  job_id INTEGER PRIMARY KEY, state TEXT NOT NULL DEFAULT '',
  updated_ms INTEGER NOT NULL DEFAULT 0
);
)";

}  // namespace

struct Database::Impl {
  sqlite3* db = nullptr;
};

Database::Database(std::string path) : impl_(new Impl), path_(std::move(path)) {}
Database::~Database() {
  if (impl_ && impl_->db) sqlite3_close(impl_->db);
}

int64_t NowMs() {
  return std::chrono::duration_cast<std::chrono::milliseconds>(
             std::chrono::system_clock::now().time_since_epoch())
      .count();
}

std::string ToLower(std::string s) {
  for (auto& c : s) c = (char)tolower((unsigned char)c);
  return s;
}

bool Database::open(std::string& err) {
  sqlite3* db = nullptr;
  int rc = sqlite3_open_v2(path_.c_str(), &db,
                           SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, nullptr);
  if (rc != SQLITE_OK) {
    err = std::string("open: ") + (db ? sqlite3_errmsg(db) : "oom");
    if (db) sqlite3_close(db);
    return false;
  }
  impl_->db = db;
  char* msg = nullptr;
  rc = sqlite3_exec(db, "PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;"
                        "PRAGMA synchronous=NORMAL;",
                    nullptr, nullptr, &msg);
  if (rc != SQLITE_OK) {
    err = std::string("pragma: ") + (msg ? msg : "?");
    sqlite3_free(msg);
    return false;
  }
  return migrate(err);
}

int Database::user_version() {
  sqlite3_stmt* st = nullptr;
  int v = 0;
  if (sqlite3_prepare_v2(impl_->db, "PRAGMA user_version", -1, &st, nullptr) == SQLITE_OK) {
    if (sqlite3_step(st) == SQLITE_ROW) v = sqlite3_column_int(st, 0);
    sqlite3_finalize(st);
  }
  return v;
}

bool Database::migrate(std::string& err) {
  try {
    if (user_version() > kSchemaVersion) {
      err = "database newer than binary";
      return false;
    }
    char* msg = nullptr;
    int rc = sqlite3_exec(impl_->db, kSchema, nullptr, nullptr, &msg);
    if (rc != SQLITE_OK) {
      err = std::string("schema: ") + (msg ? msg : "?");
      sqlite3_free(msg);
      return false;
    }
    std::string set = "PRAGMA user_version=" + std::to_string(kSchemaVersion);
    rc = sqlite3_exec(impl_->db, set.c_str(), nullptr, nullptr, &msg);
    if (rc != SQLITE_OK) {
      err = std::string("version: ") + (msg ? msg : "?");
      sqlite3_free(msg);
      return false;
    }
    return true;
  } catch (const std::exception& e) {
    err = e.what();
    return false;
  }
}

std::optional<FileRow> Database::find_by_path(const std::string& path) {
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "SELECT id,path,filename,extension,size,mtime_ns,volume_serial,"
                         "file_index,file_type,hash_status,scan_status,ai_status,"
                         "last_seen_ms,sha256,error FROM files WHERE path=?1",
                         -1, &st, nullptr) != SQLITE_OK)
    return std::nullopt;
  sqlite3_bind_text(st, 1, path.c_str(), -1, SQLITE_TRANSIENT);
  std::optional<FileRow> out;
  if (sqlite3_step(st) == SQLITE_ROW) {
    FileRow r;
    auto txt = [&](int c) -> std::string {
      const unsigned char* t = sqlite3_column_text(st, c);
      return t ? (const char*)t : "";
    };
    r.id = sqlite3_column_int64(st, 0);
    r.path = txt(1);
    r.filename = txt(2);
    r.extension = txt(3);
    r.size = sqlite3_column_int64(st, 4);
    r.mtime_ns = sqlite3_column_int64(st, 5);
    r.volume_serial = (uint64_t)sqlite3_column_int64(st, 6);
    r.file_index = (uint64_t)sqlite3_column_int64(st, 7);
    r.file_type = txt(8);
    r.hash_status = txt(9);
    r.scan_status = txt(10);
    r.ai_status = txt(11);
    r.last_seen_ms = sqlite3_column_int64(st, 12);
    r.sha256 = txt(13);
    r.error = txt(14);
    out = r;
  }
  sqlite3_finalize(st);
  return out;
}

bool Database::upsert_file(const FileRow& r, std::string& err) {
  static constexpr const char* kSql =
      "INSERT INTO files(path,filename,extension,size,mtime_ns,volume_serial,"
      "file_index,file_type,hash_status,scan_status,ai_status,last_seen_ms,sha256,error)"
      " VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14)"
      " ON CONFLICT(path) DO UPDATE SET filename=excluded.filename,"
      "extension=excluded.extension,size=excluded.size,mtime_ns=excluded.mtime_ns,"
      "volume_serial=excluded.volume_serial,file_index=excluded.file_index,"
      "file_type=excluded.file_type,hash_status=excluded.hash_status,"
      "scan_status=excluded.scan_status,ai_status=excluded.ai_status,"
      "last_seen_ms=excluded.last_seen_ms,sha256=excluded.sha256,error=excluded.error";
  try {
    sqlite3_stmt* st = nullptr;
    ThrowIf(sqlite3_prepare_v2(impl_->db, kSql, -1, &st, nullptr), impl_->db, "prepare", err);
    auto bind = [&](int i, const std::string& v) {
      sqlite3_bind_text(st, i, v.c_str(), -1, SQLITE_TRANSIENT);
    };
    bind(1, r.path);
    bind(2, r.filename);
    bind(3, r.extension);
    sqlite3_bind_int64(st, 4, r.size);
    sqlite3_bind_int64(st, 5, r.mtime_ns);
    sqlite3_bind_int64(st, 6, (int64_t)r.volume_serial);
    sqlite3_bind_int64(st, 7, (int64_t)r.file_index);
    bind(8, r.file_type);
    bind(9, r.hash_status);
    bind(10, r.scan_status);
    bind(11, r.ai_status);
    sqlite3_bind_int64(st, 12, r.last_seen_ms);
    bind(13, r.sha256);
    bind(14, r.error);
    int rc = sqlite3_step(st);
    sqlite3_finalize(st);
    ThrowIf(rc, impl_->db, "upsert", err);
    return true;
  } catch (const std::exception&) {
    return false;
  }
}

bool Database::mark_gone_before(int64_t cutoff_ms, const std::string& root_prefix,
                                int64_t& count, std::string& err) {
  count = 0;
  try {
    sqlite3_stmt* st = nullptr;
    ThrowIf(sqlite3_prepare_v2(impl_->db,
                               "UPDATE files SET scan_status='gone' WHERE last_seen_ms<=?1 "
                               "AND path LIKE ?2 ESCAPE '\\' AND scan_status!='gone'",
                               -1, &st, nullptr),
            impl_->db, "prepare", err);
    sqlite3_bind_int64(st, 1, cutoff_ms);
    std::string pat;  // LIKE-escaped root prefix
    for (char c : root_prefix) {
      if (c == '%' || c == '_' || c == '\\') pat += '\\';
      pat += c;
    }
    pat += '%';
    sqlite3_bind_text(st, 2, pat.c_str(), -1, SQLITE_TRANSIENT);
    ThrowIf(sqlite3_step(st), impl_->db, "update", err);
    count = sqlite3_changes(impl_->db);
    sqlite3_finalize(st);
    return true;
  } catch (const std::exception&) {
    return false;
  }
}

int64_t Database::file_count() {
  sqlite3_stmt* st = nullptr;
  int64_t n = 0;
  if (sqlite3_prepare_v2(impl_->db, "SELECT COUNT(*) FROM files", -1, &st, nullptr) == SQLITE_OK) {
    if (sqlite3_step(st) == SQLITE_ROW) n = sqlite3_column_int64(st, 0);
    sqlite3_finalize(st);
  }
  return n;
}

int64_t Database::begin_session(const std::string& kind, const std::string& root) {
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "INSERT INTO sessions(kind,root,started_ms) VALUES(?1,?2,?3)",
                         -1, &st, nullptr) != SQLITE_OK)
    return 0;
  sqlite3_bind_text(st, 1, kind.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, root.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int64(st, 3, NowMs());
  int64_t id = 0;
  if (sqlite3_step(st) == SQLITE_DONE) id = sqlite3_last_insert_rowid(impl_->db);
  sqlite3_finalize(st);
  return id;
}

bool Database::end_session(int64_t id, const std::string& summary, std::string& err) {
  try {
    sqlite3_stmt* st = nullptr;
    ThrowIf(sqlite3_prepare_v2(impl_->db,
                               "UPDATE sessions SET ended_ms=?1,summary=?2 WHERE id=?3",
                               -1, &st, nullptr),
            impl_->db, "prepare", err);
    sqlite3_bind_int64(st, 1, NowMs());
    sqlite3_bind_text(st, 2, summary.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(st, 3, id);
    ThrowIf(sqlite3_step(st), impl_->db, "update", err);
    sqlite3_finalize(st);
    return true;
  } catch (const std::exception&) {
    return false;
  }
}

bool Database::log_error(const std::string& stage, const std::string& path,
                         const std::string& message) {
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "INSERT INTO errors(t_ms,stage,path,message) VALUES(?1,?2,?3,?4)",
                         -1, &st, nullptr) != SQLITE_OK)
    return false;
  sqlite3_bind_int64(st, 1, NowMs());
  sqlite3_bind_text(st, 2, stage.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 3, path.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 4, message.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

bool Database::set_setting(const std::string& k, const std::string& v) {
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "INSERT INTO settings(key,value) VALUES(?1,?2) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                         -1, &st, nullptr) != SQLITE_OK)
    return false;
  sqlite3_bind_text(st, 1, k.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, v.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

std::string Database::get_setting(const std::string& k, const std::string& def) {
  sqlite3_stmt* st = nullptr;
  std::string out = def;
  if (sqlite3_prepare_v2(impl_->db, "SELECT value FROM settings WHERE key=?1", -1, &st,
                         nullptr) == SQLITE_OK) {
    sqlite3_bind_text(st, 1, k.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(st) == SQLITE_ROW) {
      const unsigned char* t = sqlite3_column_text(st, 0);
      if (t) out = (const char*)t;
    }
    sqlite3_finalize(st);
  }
  return out;
}

bool Database::exec(const std::string& sql, std::string& err) {
  char* msg = nullptr;
  int rc = sqlite3_exec(impl_->db, sql.c_str(), nullptr, nullptr, &msg);
  if (rc != SQLITE_OK) {
    err = msg ? msg : "exec failed";
    sqlite3_free(msg);
    return false;
  }
  return true;
}

int64_t Database::max_last_seen(const std::string& root_prefix) {
  sqlite3_stmt* st = nullptr;
  int64_t v = -1;
  if (sqlite3_prepare_v2(impl_->db,
                         "SELECT MAX(last_seen_ms) FROM files WHERE path LIKE ?1 ESCAPE '\\'",
                         -1, &st, nullptr) == SQLITE_OK) {
    std::string pat;
    for (char c : root_prefix) {
      if (c == '%' || c == '_' || c == '\\') pat += '\\';
      pat += c;
    }
    pat += '%';
    sqlite3_bind_text(st, 1, pat.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(st) == SQLITE_ROW && sqlite3_column_type(st, 0) != SQLITE_NULL)
      v = sqlite3_column_int64(st, 0);
    sqlite3_finalize(st);
  }
  return v;
}

std::optional<std::string> Database::hash_lookup(const std::string& path, int64_t size,
                                                 int64_t mtime_ns, int stage) {
  sqlite3_stmt* st = nullptr;
  std::optional<std::string> out;
  if (sqlite3_prepare_v2(impl_->db,
                         "SELECT sha256 FROM hash_stages WHERE path=?1 AND stage=?2 "
                         "AND size=?3 AND mtime_ns=?4",
                         -1, &st, nullptr) != SQLITE_OK)
    return out;
  sqlite3_bind_text(st, 1, path.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int(st, 2, stage);
  sqlite3_bind_int64(st, 3, size);
  sqlite3_bind_int64(st, 4, mtime_ns);
  if (sqlite3_step(st) == SQLITE_ROW) {
    const unsigned char* t = sqlite3_column_text(st, 0);
    if (t) out = (const char*)t;
  }
  sqlite3_finalize(st);
  return out;
}

bool Database::hash_store(const std::string& path, int64_t size, int64_t mtime_ns,
                          int stage, const std::string& sha256, std::string& err) {
  try {
    sqlite3_stmt* st = nullptr;
    ThrowIf(sqlite3_prepare_v2(impl_->db,
                               "INSERT INTO hash_stages(path,size,mtime_ns,stage,sha256)"
                               " VALUES(?1,?2,?3,?4,?5) ON CONFLICT(path,stage) DO UPDATE SET "
                               "size=excluded.size,mtime_ns=excluded.mtime_ns,sha256=excluded.sha256",
                               -1, &st, nullptr),
            impl_->db, "prepare", err);
    sqlite3_bind_text(st, 1, path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(st, 2, size);
    sqlite3_bind_int64(st, 3, mtime_ns);
    sqlite3_bind_int(st, 4, stage);
    sqlite3_bind_text(st, 5, sha256.c_str(), -1, SQLITE_TRANSIENT);
    int rc = sqlite3_step(st);
    sqlite3_finalize(st);
    ThrowIf(rc, impl_->db, "store", err);
    return true;
  } catch (const std::exception&) {
    return false;
  }
}

// ---- v3: duplicates / moves / jobs / behavior / stats ----

namespace {
std::string LikePattern(const std::string& prefix) {
  std::string pat;
  for (char c : prefix) {
    if (c == '%' || c == '_' || c == '\\') pat += '\\';
    pat += c;
  }
  return pat + '%';
}
}  // namespace

std::vector<SizeCandidate> Database::SameSizeCandidates(
    const std::string& root_prefix, int64_t min_size, std::string& err) {
  std::vector<SizeCandidate> out;
  err.clear();
  const char* kSql =
      "SELECT f.path,f.size,f.mtime_ns FROM files f "
      "JOIN (SELECT size FROM files WHERE path LIKE ?1 ESCAPE '\\' "
      "AND scan_status!='gone' AND size>=?2 GROUP BY size HAVING COUNT(*) > 1) d "
      "ON f.size=d.size WHERE f.path LIKE ?1 ESCAPE '\\' "
      "AND f.scan_status!='gone' AND f.size>=?2 ORDER BY f.size,f.path";
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db, kSql, -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return out;
  }
  std::string pat = LikePattern(root_prefix);
  sqlite3_bind_text(st, 1, pat.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int64(st, 2, min_size);
  while (sqlite3_step(st) == SQLITE_ROW) {
    SizeCandidate c;
    const unsigned char* t = sqlite3_column_text(st, 0);
    c.path = t ? (const char*)t : "";
    c.size = sqlite3_column_int64(st, 1);
    c.mtime_ns = sqlite3_column_int64(st, 2);
    out.push_back(c);
  }
  sqlite3_finalize(st);
  return out;
}

int64_t Database::SaveDuplicateGroup(int64_t size, const std::string& sha256,
                                     const std::vector<std::string>& paths,
                                     std::string& err) {
  err.clear();
  char* msg = nullptr;
  if (sqlite3_exec(impl_->db, "BEGIN IMMEDIATE", nullptr, nullptr, &msg) !=
      SQLITE_OK) {
    err = msg ? msg : "begin failed";
    sqlite3_free(msg);
    return 0;
  }
  int64_t gid = 0;
  sqlite3_stmt* st = nullptr;
  // NB: JANGAN andalkan last_insert_rowid() setelah UPSERT — jalur
  // ON CONFLICT DO UPDATE tidak (selalu) memperbaruinya, sehingga gid bisa
  // basi (mis. rowid dari hash_stages oleh thread lain) -> FK fail / korupsi
  // diam-diam. Resolve eksplisit: SELECT dulu, INSERT bila belum ada.
  if (sqlite3_prepare_v2(impl_->db,
                         "SELECT id FROM duplicate_groups WHERE size=?1 AND sha256=?2",
                         -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    sqlite3_exec(impl_->db, "ROLLBACK", nullptr, nullptr, nullptr);
    return 0;
  }
  sqlite3_bind_int64(st, 1, size);
  sqlite3_bind_text(st, 2, sha256.c_str(), -1, SQLITE_TRANSIENT);
  if (sqlite3_step(st) == SQLITE_ROW) gid = sqlite3_column_int64(st, 0);
  sqlite3_finalize(st);
  if (gid == 0) {
    if (sqlite3_prepare_v2(impl_->db,
                           "INSERT INTO duplicate_groups(size,sha256,created_ms)"
                           " VALUES(?1,?2,?3)",
                           -1, &st, nullptr) != SQLITE_OK) {
      err = sqlite3_errmsg(impl_->db);
      sqlite3_exec(impl_->db, "ROLLBACK", nullptr, nullptr, nullptr);
      return 0;
    }
    sqlite3_bind_int64(st, 1, size);
    sqlite3_bind_text(st, 2, sha256.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(st, 3, NowMs());
    if (sqlite3_step(st) != SQLITE_DONE) {
      err = sqlite3_errmsg(impl_->db);
      sqlite3_finalize(st);
      sqlite3_exec(impl_->db, "ROLLBACK", nullptr, nullptr, nullptr);
      return 0;
    }
    sqlite3_finalize(st);
    gid = sqlite3_last_insert_rowid(impl_->db);
    if (gid == 0) {
      err = "save group: no rowid";
      sqlite3_exec(impl_->db, "ROLLBACK", nullptr, nullptr, nullptr);
      return 0;
    }
  }
  for (const auto& p : paths) {
    sqlite3_stmt* m = nullptr;
    if (sqlite3_prepare_v2(impl_->db,
                           "INSERT OR IGNORE INTO dupe_members(group_id,path,size,mtime_ns)"
                           " VALUES(?1,?2,?3,?4)",
                           -1, &m, nullptr) != SQLITE_OK) {
      err = sqlite3_errmsg(impl_->db);
      break;
    }
    sqlite3_bind_int64(m, 1, gid);
    sqlite3_bind_text(m, 2, p.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(m, 3, size);
    sqlite3_bind_int64(m, 4, 0);
    if (sqlite3_step(m) != SQLITE_DONE) err = sqlite3_errmsg(impl_->db);
    sqlite3_finalize(m);
    if (!err.empty()) break;
  }
  if (err.empty())
    sqlite3_exec(impl_->db, "COMMIT", nullptr, nullptr, nullptr);
  else
    sqlite3_exec(impl_->db, "ROLLBACK", nullptr, nullptr, nullptr);
  return err.empty() ? gid : 0;
}

std::vector<DupeGroup> Database::ListDuplicateGroups(
    const std::string& root_prefix, std::string& err) {
  std::vector<DupeGroup> out;
  err.clear();
  // Active groups = >1 member (moves delete member rows, history stays).
  const char* kSql =
      "SELECT g.id,g.size,g.sha256,m.path FROM duplicate_groups g "
      "JOIN dupe_members m ON m.group_id=g.id "
      "WHERE (?1='' OR m.path LIKE ?1 ESCAPE '\\') "
      "AND g.id IN (SELECT group_id FROM dupe_members GROUP BY group_id HAVING COUNT(*) > 1) "
      "ORDER BY g.size DESC,g.id,m.path";
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db, kSql, -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return out;
  }
  std::string pat = root_prefix.empty() ? "" : LikePattern(root_prefix);
  sqlite3_bind_text(st, 1, pat.c_str(), -1, SQLITE_TRANSIENT);
  std::map<int64_t, size_t> idx;
  while (sqlite3_step(st) == SQLITE_ROW) {
    int64_t id = sqlite3_column_int64(st, 0);
    const unsigned char* s = sqlite3_column_text(st, 2);
    const unsigned char* p = sqlite3_column_text(st, 3);
    auto it = idx.find(id);
    if (it == idx.end()) {
      DupeGroup g;
      g.id = id;
      g.size = sqlite3_column_int64(st, 1);
      g.sha256 = s ? (const char*)s : "";
      if (p) g.paths.emplace_back((const char*)p);
      idx[id] = out.size();
      out.push_back(std::move(g));
    } else if (p) {
      out[it->second].paths.emplace_back((const char*)p);
    }
  }
  sqlite3_finalize(st);
  return out;
}

bool Database::RemoveDupeMember(int64_t group_id, const std::string& path,
                                std::string& err) {
  err.clear();
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "DELETE FROM dupe_members WHERE group_id=?1 AND path=?2",
                         -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return false;
  }
  sqlite3_bind_int64(st, 1, group_id);
  sqlite3_bind_text(st, 2, path.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  if (!ok) err = sqlite3_errmsg(impl_->db);
  sqlite3_finalize(st);
  return ok;
}

bool Database::LogMove(int64_t group_id, const std::string& src,
                       const std::string& dst, int64_t size,
                       const std::string& rollback, std::string& err) {
  err.clear();
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "INSERT INTO moves(t_ms,group_id,src,dst,size,status,rollback)"
                         " VALUES(?1,?2,?3,?4,?5,'moved',?6)",
                         -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return false;
  }
  sqlite3_bind_int64(st, 1, NowMs());
  sqlite3_bind_int64(st, 2, group_id);
  sqlite3_bind_text(st, 3, src.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 4, dst.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int64(st, 5, size);
  sqlite3_bind_text(st, 6, rollback.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  if (!ok) err = sqlite3_errmsg(impl_->db);
  sqlite3_finalize(st);
  return ok;
}

int64_t Database::EnqueueJob(const std::string& kind,
                             const std::string& payload) {
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "INSERT INTO jobs(kind,payload,status,created_ms)"
                         " VALUES(?1,?2,'pending',?3)",
                         -1, &st, nullptr) != SQLITE_OK)
    return 0;
  sqlite3_bind_text(st, 1, kind.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, payload.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int64(st, 3, NowMs());
  int64_t id = 0;
  if (sqlite3_step(st) == SQLITE_DONE) id = sqlite3_last_insert_rowid(impl_->db);
  sqlite3_finalize(st);
  return id;
}

bool Database::ClaimJob(Job& out, std::string& err) {
  err.clear();
  char* msg = nullptr;
  if (sqlite3_exec(impl_->db, "BEGIN IMMEDIATE", nullptr, nullptr, &msg) !=
      SQLITE_OK) {
    err = msg ? msg : "begin failed";
    sqlite3_free(msg);
    return false;
  }
  bool got = false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "SELECT id,kind,payload,status FROM jobs WHERE status='pending'"
                         " ORDER BY id LIMIT 1",
                         -1, &st, nullptr) == SQLITE_OK &&
      sqlite3_step(st) == SQLITE_ROW) {
    out.id = sqlite3_column_int64(st, 0);
    const unsigned char* k = sqlite3_column_text(st, 1);
    const unsigned char* p = sqlite3_column_text(st, 2);
    const unsigned char* s = sqlite3_column_text(st, 3);
    out.kind = k ? (const char*)k : "";
    out.payload = p ? (const char*)p : "";
    out.status = s ? (const char*)s : "";
    got = true;
  }
  sqlite3_finalize(st);
  if (got) {
    if (sqlite3_prepare_v2(impl_->db,
                           "UPDATE jobs SET status='running',started_ms=?1 WHERE id=?2",
                           -1, &st, nullptr) == SQLITE_OK) {
      sqlite3_bind_int64(st, 1, NowMs());
      sqlite3_bind_int64(st, 2, out.id);
      got = sqlite3_step(st) == SQLITE_DONE;
      if (!got) err = sqlite3_errmsg(impl_->db);
      sqlite3_finalize(st);
      out.status = "running";
    } else {
      err = sqlite3_errmsg(impl_->db);
      got = false;
    }
  }
  sqlite3_exec(impl_->db, got ? "COMMIT" : "ROLLBACK", nullptr, nullptr,
               nullptr);
  return got;
}

bool Database::FinishJob(int64_t id, const std::string& status,
                         const std::string& result, std::string& err) {
  err.clear();
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "UPDATE jobs SET status=?1,ended_ms=?2,result=?3 WHERE id=?4",
                         -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return false;
  }
  sqlite3_bind_text(st, 1, status.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int64(st, 2, NowMs());
  sqlite3_bind_text(st, 3, result.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int64(st, 4, id);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  if (!ok) err = sqlite3_errmsg(impl_->db);
  sqlite3_finalize(st);
  return ok;
}

bool Database::RecordBehavior(const std::string& kind,
                              const std::string& path,
                              const std::string& detail) {
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "INSERT INTO behavior_events(t_ms,kind,path,detail)"
                         " VALUES(?1,?2,?3,?4)",
                         -1, &st, nullptr) != SQLITE_OK)
    return false;
  sqlite3_bind_int64(st, 1, NowMs());
  sqlite3_bind_text(st, 2, kind.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 3, path.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 4, detail.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

std::vector<std::pair<std::string, int64_t>> Database::BehaviorSummary(
    int limit) {
  std::vector<std::pair<std::string, int64_t>> out;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "SELECT kind,COUNT(*) FROM behavior_events GROUP BY kind"
                         " ORDER BY COUNT(*) DESC LIMIT ?1",
                         -1, &st, nullptr) != SQLITE_OK)
    return out;
  sqlite3_bind_int(st, 1, limit > 0 ? limit : 10);
  while (sqlite3_step(st) == SQLITE_ROW) {
    const unsigned char* k = sqlite3_column_text(st, 0);
    out.emplace_back(k ? (const char*)k : "", sqlite3_column_int64(st, 1));
  }
  sqlite3_finalize(st);
  return out;
}

namespace {
int64_t SingleCount(sqlite3* db, const char* sql) {
  sqlite3_stmt* st = nullptr;
  int64_t n = 0;
  if (sqlite3_prepare_v2(db, sql, -1, &st, nullptr) == SQLITE_OK) {
    if (sqlite3_step(st) == SQLITE_ROW) n = sqlite3_column_int64(st, 0);
    sqlite3_finalize(st);
  }
  return n;
}
}  // namespace

DbStats Database::Stats(const std::string& root_prefix) {
  DbStats s;
  sqlite3* raw = impl_->db;
  s.files = SingleCount(raw, "SELECT COUNT(*) FROM files");
  s.gone = SingleCount(raw, "SELECT COUNT(*) FROM files WHERE scan_status='gone'");
  s.errors = SingleCount(raw, "SELECT COUNT(*) FROM errors");
  s.dup_groups = SingleCount(
      raw, "SELECT COUNT(*) FROM duplicate_groups WHERE id IN "
           "(SELECT group_id FROM dupe_members GROUP BY group_id HAVING COUNT(*) > 1)");
  s.dup_files = SingleCount(
      raw, "SELECT COUNT(*) FROM dupe_members WHERE group_id IN "
           "(SELECT group_id FROM dupe_members GROUP BY group_id HAVING COUNT(*) > 1)");
  s.pending_jobs =
      SingleCount(raw, "SELECT COUNT(*) FROM jobs WHERE status IN ('pending','running')");
  s.sessions = SingleCount(raw, "SELECT COUNT(*) FROM sessions");
  s.proposals = SingleCount(raw, "SELECT COUNT(*) FROM proposals WHERE status='pending'");
  s.audit_rows = SingleCount(raw, "SELECT COUNT(*) FROM audit_log");
  (void)root_prefix;
  return s;
}

// ---- v4: jobs list/status/checkpoint, audit, proposals, doctor ----

std::vector<Job> Database::ListJobs(const std::string& status_filter,
                                    int limit, std::string& err) {
  std::vector<Job> out;
  err.clear();
  std::string sql =
      "SELECT id,kind,payload,status,created_ms,started_ms,ended_ms,result"
      " FROM jobs";
  if (!status_filter.empty()) sql += " WHERE status=?1";
  sql += " ORDER BY id DESC LIMIT ?" + std::string(status_filter.empty() ? "1" : "2");
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db, sql.c_str(), -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return out;
  }
  auto txt = [&](int c) -> std::string {
    const unsigned char* t = sqlite3_column_text(st, c);
    return t ? (const char*)t : "";
  };
  if (status_filter.empty()) {
    sqlite3_bind_int(st, 1, limit > 0 ? limit : 50);
  } else {
    sqlite3_bind_text(st, 1, status_filter.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(st, 2, limit > 0 ? limit : 50);
  }
  while (sqlite3_step(st) == SQLITE_ROW) {
    Job j;
    j.id = sqlite3_column_int64(st, 0);
    j.kind = txt(1);
    j.payload = txt(2);
    j.status = txt(3);
    j.created_ms = sqlite3_column_int64(st, 4);
    j.started_ms = sqlite3_column_int64(st, 5);
    j.ended_ms = sqlite3_column_int64(st, 6);
    j.result = txt(7);
    out.push_back(j);
  }
  sqlite3_finalize(st);
  return out;
}

bool Database::SetJobStatus(int64_t id, const std::string& status,
                            std::string& err) {
  err.clear();
  // Transisi valid (master: pause/resume/cancel; finish via FinishJob).
  static const std::map<std::string, std::vector<std::string>> kOk = {
      {"paused", {"pending", "running"}},
      {"pending", {"paused"}},  // resume
      {"cancelled", {"pending", "running", "paused"}},
  };
  auto it = kOk.find(status);
  if (it == kOk.end()) {
    err = "status tak dikenal: " + status;
    return false;
  }
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db, "SELECT status FROM jobs WHERE id=?1",
                         -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return false;
  }
  sqlite3_bind_int64(st, 1, id);
  std::string cur;
  if (sqlite3_step(st) == SQLITE_ROW) {
    const unsigned char* t = sqlite3_column_text(st, 0);
    cur = t ? (const char*)t : "";
  }
  sqlite3_finalize(st);
  if (cur.empty()) {
    err = "job tidak ada";
    return false;
  }
  const auto& allowed = it->second;
  if (std::find(allowed.begin(), allowed.end(), cur) == allowed.end()) {
    err = "transisi " + cur + " -> " + status + " ditolak";
    return false;
  }
  if (sqlite3_prepare_v2(impl_->db,
                         "UPDATE jobs SET status=?1,ended_ms=CASE WHEN ?1 IN"
                         " ('cancelled') THEN ?2 ELSE ended_ms END WHERE id=?3",
                         -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return false;
  }
  sqlite3_bind_text(st, 1, status.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int64(st, 2, NowMs());
  sqlite3_bind_int64(st, 3, id);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  if (!ok) err = sqlite3_errmsg(impl_->db);
  sqlite3_finalize(st);
  return ok;
}

bool Database::SaveCheckpoint(int64_t job_id, const std::string& state) {
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "INSERT INTO job_checkpoints(job_id,state,updated_ms)"
                         " VALUES(?1,?2,?3) ON CONFLICT(job_id) DO UPDATE SET"
                         " state=excluded.state,updated_ms=excluded.updated_ms",
                         -1, &st, nullptr) != SQLITE_OK)
    return false;
  sqlite3_bind_int64(st, 1, job_id);
  sqlite3_bind_text(st, 2, state.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int64(st, 3, NowMs());
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

std::optional<std::string> Database::LoadCheckpoint(int64_t job_id) {
  sqlite3_stmt* st = nullptr;
  std::optional<std::string> out;
  if (sqlite3_prepare_v2(impl_->db,
                         "SELECT state FROM job_checkpoints WHERE job_id=?1",
                         -1, &st, nullptr) != SQLITE_OK)
    return out;
  sqlite3_bind_int64(st, 1, job_id);
  if (sqlite3_step(st) == SQLITE_ROW) {
    const unsigned char* t = sqlite3_column_text(st, 0);
    if (t) out = (const char*)t;
  }
  sqlite3_finalize(st);
  return out;
}

bool Database::Audit(const std::string& actor, const std::string& action,
                     const std::string& src, const std::string& dst,
                     const std::string& result, const std::string& detail) {
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "INSERT INTO audit_log(t_ms,actor,action,src,dst,result,detail)"
                         " VALUES(?1,?2,?3,?4,?5,?6,?7)",
                         -1, &st, nullptr) != SQLITE_OK)
    return false;
  sqlite3_bind_int64(st, 1, NowMs());
  sqlite3_bind_text(st, 2, actor.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 3, action.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 4, src.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 5, dst.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 6, result.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 7, detail.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

std::vector<AuditRow> Database::ListAudit(const std::string& action_filter,
                                          int limit, std::string& err) {
  std::vector<AuditRow> out;
  err.clear();
  std::string sql =
      "SELECT id,t_ms,actor,action,src,dst,result,detail FROM audit_log";
  if (!action_filter.empty()) sql += " WHERE action=?1";
  sql += " ORDER BY id DESC LIMIT ?" + std::string(action_filter.empty() ? "1" : "2");
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db, sql.c_str(), -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return out;
  }
  auto txt = [&](int c) -> std::string {
    const unsigned char* t = sqlite3_column_text(st, c);
    return t ? (const char*)t : "";
  };
  if (action_filter.empty()) {
    sqlite3_bind_int(st, 1, limit > 0 ? limit : 100);
  } else {
    sqlite3_bind_text(st, 1, action_filter.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(st, 2, limit > 0 ? limit : 100);
  }
  while (sqlite3_step(st) == SQLITE_ROW) {
    AuditRow r;
    r.id = sqlite3_column_int64(st, 0);
    r.t_ms = sqlite3_column_int64(st, 1);
    r.actor = txt(2);
    r.action = txt(3);
    r.src = txt(4);
    r.dst = txt(5);
    r.result = txt(6);
    r.detail = txt(7);
    out.push_back(r);
  }
  sqlite3_finalize(st);
  return out;
}

std::string Database::ProposeMoves(
    int64_t group_id, const std::string& keep, const std::string& dest_dir,
    const std::vector<std::pair<std::string, std::string>>& items,
    const std::string& reasons, const std::string& risk, std::string& err) {
  err.clear();
  if (items.empty()) {
    err = "tidak ada item proposal";
    return "";
  }
  std::string batch = "p" + std::to_string(NowMs());
  char* msg = nullptr;
  if (sqlite3_exec(impl_->db, "BEGIN IMMEDIATE", nullptr, nullptr, &msg) !=
      SQLITE_OK) {
    err = msg ? msg : "begin failed";
    sqlite3_free(msg);
    return "";
  }
  int64_t now = NowMs();
  for (const auto& [src, dst] : items) {
    sqlite3_stmt* st = nullptr;
    if (sqlite3_prepare_v2(impl_->db,
                           "INSERT INTO proposals(created_ms,batch,kind,action,group_id,src,dst,"
                           "reasons,risk,status) VALUES(?1,?2,'move','move',?3,?4,?5,?6,?7,'pending')",
                           -1, &st, nullptr) != SQLITE_OK) {
      err = sqlite3_errmsg(impl_->db);
      break;
    }
    sqlite3_bind_int64(st, 1, now);
    sqlite3_bind_text(st, 2, batch.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(st, 3, group_id);
    sqlite3_bind_text(st, 4, src.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(st, 5, dst.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(st, 6, reasons.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(st, 7, risk.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(st) != SQLITE_DONE) err = sqlite3_errmsg(impl_->db);
    sqlite3_finalize(st);
    if (!err.empty()) break;
    (void)keep;
    (void)dest_dir;
  }
  sqlite3_exec(impl_->db, err.empty() ? "COMMIT" : "ROLLBACK", nullptr,
               nullptr, nullptr);
  return err.empty() ? batch : "";
}

std::vector<Proposal> Database::ListProposals(const std::string& status_filter,
                                              std::string& err) {
  std::vector<Proposal> out;
  err.clear();
  std::string sql =
      "SELECT id,created_ms,batch,kind,action,group_id,src,dst,reasons,risk,status"
      " FROM proposals";
  if (!status_filter.empty()) sql += " WHERE status=?1";
  sql += " ORDER BY id DESC LIMIT 200";
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db, sql.c_str(), -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return out;
  }
  auto txt = [&](int c) -> std::string {
    const unsigned char* t = sqlite3_column_text(st, c);
    return t ? (const char*)t : "";
  };
  if (!status_filter.empty())
    sqlite3_bind_text(st, 1, status_filter.c_str(), -1, SQLITE_TRANSIENT);
  while (sqlite3_step(st) == SQLITE_ROW) {
    Proposal p;
    p.id = sqlite3_column_int64(st, 0);
    p.created_ms = sqlite3_column_int64(st, 1);
    p.batch = txt(2);
    p.kind = txt(3);
    p.action = txt(4);
    p.group_id = sqlite3_column_int64(st, 5);
    p.src = txt(6);
    p.dst = txt(7);
    p.reasons = txt(8);
    p.risk = txt(9);
    p.status = txt(10);
    out.push_back(p);
  }
  sqlite3_finalize(st);
  return out;
}

std::vector<Proposal> Database::BatchProposals(const std::string& batch,
                                               std::string& err) {
  std::vector<Proposal> out;
  err.clear();
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "SELECT id,created_ms,batch,kind,action,group_id,src,dst,reasons,risk,status"
                         " FROM proposals WHERE batch=?1 ORDER BY id",
                         -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return out;
  }
  auto txt = [&](int c) -> std::string {
    const unsigned char* t = sqlite3_column_text(st, c);
    return t ? (const char*)t : "";
  };
  sqlite3_bind_text(st, 1, batch.c_str(), -1, SQLITE_TRANSIENT);
  while (sqlite3_step(st) == SQLITE_ROW) {
    Proposal p;
    p.id = sqlite3_column_int64(st, 0);
    p.created_ms = sqlite3_column_int64(st, 1);
    p.batch = txt(2);
    p.kind = txt(3);
    p.action = txt(4);
    p.group_id = sqlite3_column_int64(st, 5);
    p.src = txt(6);
    p.dst = txt(7);
    p.reasons = txt(8);
    p.risk = txt(9);
    p.status = txt(10);
    out.push_back(p);
  }
  sqlite3_finalize(st);
  return out;
}

bool Database::ResolveProposal(int64_t id, const std::string& status,
                               std::string& err) {
  err.clear();
  if (status != "approved" && status != "done" && status != "rejected" &&
      status != "failed") {
    err = "status proposal tak dikenal: " + status;
    return false;
  }
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(impl_->db,
                         "UPDATE proposals SET status=?1 WHERE id=?2 AND status='pending'",
                         -1, &st, nullptr) != SQLITE_OK) {
    err = sqlite3_errmsg(impl_->db);
    return false;
  }
  sqlite3_bind_text(st, 1, status.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int64(st, 2, id);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  if (!ok) err = sqlite3_errmsg(impl_->db);
  sqlite3_finalize(st);
  return ok;
}

std::string Database::IntegrityCheck() {
  sqlite3_stmt* st = nullptr;
  std::string out = "unknown";
  if (sqlite3_prepare_v2(impl_->db, "PRAGMA integrity_check", -1, &st,
                         nullptr) == SQLITE_OK) {
    if (sqlite3_step(st) == SQLITE_ROW) {
      const unsigned char* t = sqlite3_column_text(st, 0);
      out = t ? (const char*)t : "?";
    }
    sqlite3_finalize(st);
  }
  return out;
}

std::string Database::JournalMode() {
  sqlite3_stmt* st = nullptr;
  std::string out;
  if (sqlite3_prepare_v2(impl_->db, "PRAGMA journal_mode", -1, &st,
                         nullptr) == SQLITE_OK) {
    if (sqlite3_step(st) == SQLITE_ROW) {
      const unsigned char* t = sqlite3_column_text(st, 0);
      if (t) out = (const char*)t;
    }
    sqlite3_finalize(st);
  }
  return out;
}

}  // namespace aiorg::db
