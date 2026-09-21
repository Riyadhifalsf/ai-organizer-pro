// aiorganizer CLI: scan | hash | duplicates | move-approved | stats | jobs |
//   proposals | audit | doctor | version. (master doc #85, #150)
// Mesin inti AIOrganizerPro. Semua perintah yang mengubah data menulis ke
// SQLite terpadu (skema v4); output --json dikonsumsi GUI modern + server Node.
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <vector>

#include "core/database/database.h"
#include "core/duplicate/duplicate.h"
#include "core/filesystem/utf8.h"
#include "core/hashing/pipeline.h"
#include "core/hashing/sha256.h"
#include "core/scanner/scanner.h"
#include "spdlog/spdlog.h"
#include "sqlite3.h"

namespace {

void Usage() {
  std::puts(
      "pakai:\n"
      "  aiorganizer scan <folder> --db <file> [--json] [--actor cli|gui|daemon]\n"
      "  aiorganizer hash <file> [--db <file>]\n"
      "  aiorganizer duplicates <folder> --db <file> [--json] [--min-size N] [--workers N]\n"
      "  aiorganizer move-approved --db <file> --group ID --keep <path> --to <dir> [--json]\n"
      "  aiorganizer stats --db <file> [--json]\n"
      "  aiorganizer job-enqueue <kind> <payload> --db <file>\n"
      "  aiorganizer job-claim --db <file> [--json]\n"
      "  aiorganizer job-finish <id> <status> [result] --db <file>\n"
      "  aiorganizer job-list [--status S] [--limit N] --db <file> [--json]\n"
      "  aiorganizer job-pause|job-resume|job-cancel <id> --db <file> [--json]\n"
      "  aiorganizer proposals propose --group ID --keep <path> --to <dir> [--reasons T] --db <file> [--json]\n"
      "  aiorganizer proposals list [--status S] --db <file> [--json]\n"
      "  aiorganizer proposals preview <id|batch> --db <file> [--json]\n"
      "  aiorganizer proposals approve <batch> --db <file> [--json]\n"
      "  aiorganizer proposals reject <id|batch> --db <file> [--json]\n"
      "  aiorganizer audit [--action A] [--limit N] --db <file> [--json]\n"
      "  aiorganizer doctor [--db <file>] [--root <folder>] [--json]\n"
      "  aiorganizer version\n");
}

std::string ToGeneric(std::string s) {
  for (auto& c : s)
    if (c == '\\') c = '/';
  return s;
}

std::string JsonEscape(const std::string& s) {
  std::string o;
  for (char c : s) {
    switch (c) {
      case '"': o += "\\\""; break;
      case '\\': o += "\\\\"; break;
      case '\n': o += "\\n"; break;
      case '\r': o += "\\r"; break;
      case '\t': o += "\\t"; break;
      default:
        if ((unsigned char)c < 0x20) {
          char b[8];
          std::snprintf(b, sizeof b, "\\u%04x", c);
          o += b;
        } else {
          o += c;
        }
    }
  }
  return o;
}

bool HasFlag(int argc, char** argv, const std::string& f) {
  for (int i = 0; i < argc; i++)
    if (argv[i] == f) return true;
  return false;
}

std::string FlagVal(int argc, char** argv, const std::string& f,
                    const std::string& def = "") {
  for (int i = 0; i + 1 < argc; i++)
    if (argv[i] == f) return argv[i + 1];
  return def;
}

std::string ActorOf(int argc, char** argv) {
  std::string a = FlagVal(argc, argv, "--actor", "cli");
  return (a == "gui" || a == "daemon") ? a : "cli";
}

// Flag yang mengambil nilai: nilainya harus dilewati saat cari argumen posisi.
bool IsValFlag(const std::string& a) {
  return a == "--db" || a == "--actor" || a == "--status" ||
         a == "--limit" || a == "--group" || a == "--keep" || a == "--to" ||
         a == "--reasons" || a == "--min-size" || a == "--workers" ||
         a == "--action" || a == "--root";
}

int CmdScan(int argc, char** argv) {
  std::string folder, db_path = "aiorganizer.db";
  for (int i = 2; i < argc; i++) {
    std::string a = argv[i];
    if (a == "--db" && i + 1 < argc)
      db_path = argv[++i];
    else if (a.rfind("--", 0) == 0) {
      if (i + 1 < argc && argv[i + 1][0] != '-') i++;  // lewati nilai flag
    } else if (!a.empty() && a[0] != '-')
      folder = a;
  }
  if (folder.empty()) {
    Usage();
    return 2;
  }
  bool json = HasFlag(argc, argv, "--json");
  aiorg::db::Database db(db_path);
  std::string err;
  if (!db.open(err)) {
    spdlog::error("db: {}", err);
    return 1;
  }
  int64_t sess = db.begin_session("scan", ToGeneric(folder));
  aiorg::scanner::Options opts;
  opts.root = folder;
  aiorg::scanner::Scanner scanner(db, opts);
  std::atomic<bool> cancel{false}, paused{false};
  auto t0 = std::chrono::steady_clock::now();
  bool quiet = json;
  bool ok = scanner.run(
      cancel, paused,
      [&](const aiorg::scanner::Progress& p) {
        if (quiet) return;
        auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                      std::chrono::steady_clock::now() - t0)
                      .count();
        double s = ms / 1000.0;
        std::printf("\rseen=%llu new=%llu changed=%llu skip=%llu err=%llu "
                    "%.0f f/s :: %s   ",
                    p.seen, p.fresh, p.changed, p.unchanged, p.errors,
                    s > 0 ? p.seen / s : 0,
                    aiorg::fsutil::ToDisplay(p.current).c_str());
        fflush(stdout);
      },
      [&](const std::string& path, const std::string& msg) {
        db.log_error("scan", path, msg);
        if (!quiet)
          spdlog::warn("skip {}: {}", aiorg::fsutil::ToDisplay(path), msg);
      },
      err);
  if (!quiet) std::puts("");
  if (!ok) {
    spdlog::error("scan: {}", err);
    return 1;
  }
  long long n = (long long)db.file_count();
  db.end_session(sess, "files=" + std::to_string(n), err);
  db.Audit(ActorOf(argc, argv), "scan", ToGeneric(folder), "",
           ok ? "ok" : "fail", "files=" + std::to_string(n));
  if (json)
    std::printf("{\"ok\":true,\"files\":%lld,\"db\":\"%s\"}\n", n,
                JsonEscape(db_path).c_str());
  else
    std::printf("indexed files in db: %lld\n", n);
  return 0;
}

int CmdDuplicates(int argc, char** argv) {
  std::string folder, db_path = "aiorganizer.db";
  for (int i = 2; i < argc; i++) {
    std::string a = argv[i];
    if (a == "--db" && i + 1 < argc)
      db_path = argv[++i];
    else if (a == "--min-size" && i + 1 < argc)
      i++;
    else if (a == "--workers" && i + 1 < argc)
      i++;
    else if (a.rfind("--", 0) == 0) {
      if (i + 1 < argc && argv[i + 1][0] != '-') i++;  // lewati nilai flag
    } else if (!a.empty() && a[0] != '-')
      folder = a;
  }
  if (folder.empty()) {
    Usage();
    return 2;
  }
  bool json = HasFlag(argc, argv, "--json");
  aiorg::duplicate::Options opts;
  opts.root = folder;
  opts.min_size = std::stoll(FlagVal(argc, argv, "--min-size", "1"));
  opts.workers = std::stoi(FlagVal(argc, argv, "--workers", "4"));
  aiorg::db::Database db(db_path);
  std::string err;
  if (!db.open(err)) {
    spdlog::error("db: {}", err);
    return 1;
  }
  int64_t sess = db.begin_session("duplicates", ToGeneric(folder));
  std::atomic<bool> cancel{false};
  auto groups = aiorg::duplicate::FindDuplicates(
      db, opts, cancel,
      [&](const aiorg::duplicate::Progress& p) {
        if (!json)
          std::printf("\rsize_groups=%llu hashed=%llu confirmed=%llu err=%llu",
                      p.size_groups, p.hashed, p.confirmed_groups, p.errors);
      },
      err);
  if (!json) std::puts("");
  if (!err.empty()) {
    spdlog::error("duplicates: {}", err);
    return 1;
  }
  db.RecordBehavior("duplicates", ToGeneric(folder),
                    "groups=" + std::to_string(groups.size()));
  db.Audit(ActorOf(argc, argv), "duplicates", ToGeneric(folder), "", "ok",
           "groups=" + std::to_string(groups.size()));
  db.end_session(sess, "groups=" + std::to_string(groups.size()), err);
  if (json) {
    std::printf("{\"ok\":true,\"groups\":[");
    bool first = true;
    for (auto& g : groups) {
      if (!first) std::printf(",");
      first = false;
      std::printf("{\"id\":%lld,\"size\":%lld,\"sha256\":\"%s\",\"paths\":[",
                 (long long)g.id, (long long)g.size,
                 JsonEscape(g.sha256).c_str());
      bool f2 = true;
      for (auto& p : g.paths) {
        if (!f2) std::printf(",");
        f2 = false;
        std::printf("\"%s\"", JsonEscape(p).c_str());
      }
      std::printf("]}");
    }
    std::printf("]}\n");
  } else {
    std::printf("%zu grup duplikat:\n", groups.size());
    for (auto& g : groups) {
      std::printf("[%lld] %lld bytes %s\n", (long long)g.id,
                 (long long)g.size, g.sha256.c_str());
      for (auto& p : g.paths)
        std::printf("    %s\n", aiorg::fsutil::ToDisplay(p).c_str());
    }
  }
  return 0;
}

int CmdMoveApproved(int argc, char** argv) {
  std::string db_path = "aiorganizer.db";
  int64_t group = std::stoll(FlagVal(argc, argv, "--group", "0"));
  std::string keep = ToGeneric(FlagVal(argc, argv, "--keep", ""));
  std::string to = FlagVal(argc, argv, "--to", "");
  for (int i = 2; i < argc; i++) {
    if (std::string(argv[i]) == "--db" && i + 1 < argc) db_path = argv[++i];
  }
  if (!group || keep.empty() || to.empty()) {
    Usage();
    return 2;
  }
  bool json = HasFlag(argc, argv, "--json");
  aiorg::db::Database db(db_path);
  std::string err;
  if (!db.open(err)) {
    spdlog::error("db: {}", err);
    return 1;
  }
  auto moved = aiorg::duplicate::ApproveMove(db, group, keep, to, err);
  if (!err.empty()) {
    if (json)
      std::printf("{\"ok\":false,\"error\":\"%s\"}\n",
                  JsonEscape(err).c_str());
    else
      spdlog::error("move: {}", err);
    return 1;
  }
  db.RecordBehavior("move-approved", keep,
                    "group=" + std::to_string(group) +
                        " moved=" + std::to_string(moved.size()));
  db.Audit(ActorOf(argc, argv), "move", keep, to, "ok",
           "group=" + std::to_string(group) +
               " moved=" + std::to_string(moved.size()));
  if (json) {
    std::printf("{\"ok\":true,\"moved\":[");
    bool f = true;
    for (auto& m : moved) {
      if (!f) std::printf(",");
      f = false;
      std::printf("\"%s\"", JsonEscape(m).c_str());
    }
    std::printf("]}\n");
  } else {
    std::printf("dipindah %zu file (rollback tercatat di tabel moves):\n",
                moved.size());
    for (auto& m : moved) std::printf("  %s\n", m.c_str());
  }
  return 0;
}

int CmdStats(int argc, char** argv) {
  std::string db_path = FlagVal(argc, argv, "--db", "aiorganizer.db");
  bool json = HasFlag(argc, argv, "--json");
  aiorg::db::Database db(db_path);
  std::string err;
  if (!db.open(err)) {
    spdlog::error("db: {}", err);
    return 1;
  }
  auto s = db.Stats("");
  auto beh = db.BehaviorSummary(10);
  if (json) {
    std::printf(
        "{\"ok\":true,\"files\":%lld,\"gone\":%lld,\"errors\":%lld,"
        "\"dup_groups\":%lld,\"dup_files\":%lld,\"pending_jobs\":%lld,"
        "\"sessions\":%lld,\"proposals\":%lld,\"audit_rows\":%lld,\"behavior\":[",
        (long long)s.files, (long long)s.gone, (long long)s.errors,
        (long long)s.dup_groups, (long long)s.dup_files,
        (long long)s.pending_jobs, (long long)s.sessions,
        (long long)s.proposals, (long long)s.audit_rows);
    bool f = true;
    for (auto& [k, c] : beh) {
      if (!f) std::printf(",");
      f = false;
      std::printf("{\"kind\":\"%s\",\"count\":%lld}", JsonEscape(k).c_str(),
                 (long long)c);
    }
    std::printf("]}\n");
  } else {
    std::printf("files=%lld gone=%lld errors=%lld dup_groups=%lld "
                "dup_files=%lld pending_jobs=%lld sessions=%lld "
                "proposals=%lld audit_rows=%lld\n",
                (long long)s.files, (long long)s.gone, (long long)s.errors,
                (long long)s.dup_groups, (long long)s.dup_files,
                (long long)s.pending_jobs, (long long)s.sessions,
                (long long)s.proposals, (long long)s.audit_rows);
    for (auto& [k, c] : beh)
      std::printf("  behavior %s: %lld\n", k.c_str(), (long long)c);
  }
  return 0;
}

int CmdJobs(int argc, char** argv, const std::string& sub) {
  std::string db_path = FlagVal(argc, argv, "--db", "aiorganizer.db");
  bool json = HasFlag(argc, argv, "--json");
  aiorg::db::Database db(db_path);
  std::string err;
  if (!db.open(err)) {
    spdlog::error("db: {}", err);
    return 1;
  }
  if (sub == "job-enqueue") {
    std::string kind, payload;
    for (int i = 2; i < argc; i++) {
      std::string a = argv[i];
      if (IsValFlag(a)) {
        i++;
        continue;
      }
      if (!a.empty() && a[0] != '-' && a != "--json") {
        if (kind.empty())
          kind = a;
        else if (payload.empty())
          payload = a;
      }
    }
    if (kind.empty()) {
      Usage();
      return 2;
    }
    int64_t id = db.EnqueueJob(kind, payload);
    if (json)
      std::printf("{\"ok\":true,\"id\":%lld}\n", (long long)id);
    else
      std::printf("job %lld enqueued (%s)\n", (long long)id, kind.c_str());
    return id ? 0 : 1;
  }
  if (sub == "job-claim") {
    aiorg::db::Job j;
    if (!db.ClaimJob(j, err) || !err.empty()) {
      if (json) std::printf("{\"ok\":false}\n");
      return 1;
    }
    if (json)
      std::printf("{\"ok\":true,\"id\":%lld,\"kind\":\"%s\",\"payload\":\"%s\"}\n",
                 (long long)j.id, JsonEscape(j.kind).c_str(),
                 JsonEscape(j.payload).c_str());
    else
      std::printf("claimed job %lld (%s)\n", (long long)j.id, j.kind.c_str());
    return 0;
  }
  if (sub == "job-finish") {
    std::string id_s, status, result;
    for (int i = 2; i < argc; i++) {
      std::string a = argv[i];
      if (IsValFlag(a)) {
        i++;
        continue;
      }
      if (!a.empty() && a[0] != '-' && a != "--json") {
        if (id_s.empty())
          id_s = a;
        else if (status.empty())
          status = a;
        else if (result.empty())
          result = a;
      }
    }
    if (id_s.empty() || status.empty()) {
      Usage();
      return 2;
    }
    bool ok = db.FinishJob(std::stoll(id_s), status, result, err);
    if (json)
      std::printf("{\"ok\":%s}\n", ok ? "true" : "false");
    else
      std::printf(ok ? "job finished\n" : "finish failed: %s\n", err.c_str());
    return ok ? 0 : 1;
  }
  if (sub == "job-list" || sub == "job-pause" || sub == "job-resume" ||
      sub == "job-cancel") {
    std::string filter, id_s;
    for (int i = 2; i < argc; i++) {
      std::string a = argv[i];
      if (IsValFlag(a)) {
        i++;
        continue;
      }
      if ((a == "--status" || a == "--limit") && i + 1 < argc) {
        i++;
        continue;
      }
      if (!a.empty() && a[0] != '-' && a != "--json") {
        if (sub == "job-list" && filter.empty())
          filter = a;
        else if (id_s.empty())
          id_s = a;
      }
    }
    if (sub == "job-list") {
      if (filter.empty()) filter = FlagVal(argc, argv, "--status", "");
      int lim = std::stoi(FlagVal(argc, argv, "--limit", "50"));
      auto jobs = db.ListJobs(filter, lim, err);
      if (!err.empty()) {
        if (json) std::printf("{\"ok\":false,\"error\":\"%s\"}\n", JsonEscape(err).c_str());
        else spdlog::error("job-list: {}", err);
        return 1;
      }
      if (json) {
        std::printf("{\"ok\":true,\"jobs\":[");
        bool f = true;
        for (auto& j : jobs) {
          if (!f) std::printf(",");
          f = false;
          std::printf("{\"id\":%lld,\"kind\":\"%s\",\"payload\":\"%s\",\"status\":\"%s\","
                     "\"created_ms\":%lld,\"started_ms\":%lld,\"ended_ms\":%lld,\"result\":\"%s\"}",
                     (long long)j.id, JsonEscape(j.kind).c_str(), JsonEscape(j.payload).c_str(),
                     JsonEscape(j.status).c_str(), (long long)j.created_ms,
                     (long long)j.started_ms, (long long)j.ended_ms, JsonEscape(j.result).c_str());
        }
        std::printf("]}\n");
      } else {
        for (auto& j : jobs)
          std::printf("#%lld [%s] %s :: %s\n", (long long)j.id, j.status.c_str(),
                     j.kind.c_str(), j.payload.c_str());
      }
      return 0;
    }
    if (id_s.empty()) {
      Usage();
      return 2;
    }
    std::string to = sub == "job-pause" ? "paused" : (sub == "job-resume" ? "pending" : "cancelled");
    bool ok = db.SetJobStatus(std::stoll(id_s), to, err);
    db.Audit(ActorOf(argc, argv), sub, "#" + id_s, "", ok ? "ok" : "fail", err);
    if (json)
      std::printf("{\"ok\":%s%s%s}\n", ok ? "true" : "false",
                 ok ? "" : ",\"error\":\"", ok ? "" : (JsonEscape(err) + "\"").c_str());
    else
      std::printf(ok ? "job %s -> %s\n" : "gagal: %s\n", id_s.c_str(), to.c_str(), err.c_str());
    return ok ? 0 : 1;
  }
  Usage();
  return 2;
}

void PrintProposalJson(const aiorg::db::Proposal& p, bool& first) {
  if (!first) std::printf(",");
  first = false;
  std::printf("{\"id\":%lld,\"batch\":\"%s\",\"kind\":\"%s\",\"action\":\"%s\","
             "\"group_id\":%lld,\"src\":\"%s\",\"dst\":\"%s\",\"reasons\":\"%s\","
             "\"risk\":\"%s\",\"status\":\"%s\"}",
             (long long)p.id, JsonEscape(p.batch).c_str(), JsonEscape(p.kind).c_str(),
             JsonEscape(p.action).c_str(), (long long)p.group_id,
             JsonEscape(p.src).c_str(), JsonEscape(p.dst).c_str(),
             JsonEscape(p.reasons).c_str(), JsonEscape(p.risk).c_str(),
             JsonEscape(p.status).c_str());
}

int CmdProposals(int argc, char** argv, const std::string& sub) {
  std::string db_path = FlagVal(argc, argv, "--db", "aiorganizer.db");
  bool json = HasFlag(argc, argv, "--json");
  aiorg::db::Database db(db_path);
  std::string err;
  if (!db.open(err)) {
    spdlog::error("db: {}", err);
    return 1;
  }
  if (sub == "propose") {
    int64_t group = std::stoll(FlagVal(argc, argv, "--group", "0"));
    std::string keep = ToGeneric(FlagVal(argc, argv, "--keep", ""));
    std::string to = FlagVal(argc, argv, "--to", "");
    std::string reasons = FlagVal(argc, argv, "--reasons", "");
    if (!group || keep.empty() || to.empty()) {
      Usage();
      return 2;
    }
    std::string batch = aiorg::duplicate::ProposeFromGroup(db, group, keep, to, reasons, err);
    if (batch.empty()) {
      if (json) std::printf("{\"ok\":false,\"error\":\"%s\"}\n", JsonEscape(err).c_str());
      else spdlog::error("propose: {}", err);
      return 1;
    }
    auto items = db.BatchProposals(batch, err);
    db.Audit(ActorOf(argc, argv), "proposal", keep, to, "ok",
             "batch=" + batch + " items=" + std::to_string(items.size()));
    if (json)
      std::printf("{\"ok\":true,\"batch\":\"%s\",\"items\":%zu}\n", batch.c_str(), items.size());
    else
      std::printf("proposal batch %s: %zu item (status pending, belum ada yang pindah)\n",
                 batch.c_str(), items.size());
    return 0;
  }
  if (sub == "list") {
    std::string st = FlagVal(argc, argv, "--status", "");
    auto ps = db.ListProposals(st, err);
    if (!err.empty()) {
      if (json) std::printf("{\"ok\":false,\"error\":\"%s\"}\n", JsonEscape(err).c_str());
      else spdlog::error("proposals: {}", err);
      return 1;
    }
    if (json) {
      std::printf("{\"ok\":true,\"proposals\":[");
      bool f = true;
      for (auto& p : ps) PrintProposalJson(p, f);
      std::printf("]}\n");
    } else {
      for (auto& p : ps)
        std::printf("#%lld [%s] %s %s -> %s (%s)\n", (long long)p.id, p.status.c_str(),
                   p.action.c_str(), p.src.c_str(), p.dst.c_str(), p.reasons.c_str());
    }
    return 0;
  }
  // preview / approve: arg = id ATAU batch.
  std::string target;
  for (int i = 2; i < argc; i++) {
    std::string a = argv[i];
    if (IsValFlag(a)) {
      i++;
      continue;
    }
    if (!a.empty() && a[0] != '-' && a != "--json" && a != "preview" && a != "approve" &&
        a != "list" && a != "propose") {
      if (target.empty()) target = a;
    }
  }
  if (target.empty()) {
    Usage();
    return 2;
  }
  std::vector<aiorg::db::Proposal> items;
  bool is_batch = !target.empty() && target[0] == 'p';
  if (is_batch) {
    items = db.BatchProposals(target, err);
  } else {
    auto all = db.ListProposals("", err);
    for (auto& p : all)
      if (p.id == std::stoll(target)) items.push_back(p);
  }
  if (!err.empty() || items.empty()) {
    if (json) std::printf("{\"ok\":false,\"error\":\"%s\"}\n",
                          JsonEscape(err.empty() ? "proposal tidak ada" : err).c_str());
    else spdlog::error("proposal: {}", err.empty() ? "tidak ada" : err);
    return 1;
  }
  if (sub == "preview") {
    if (json) {
      std::printf("{\"ok\":true,\"proposals\":[");
      bool f = true;
      for (auto& p : items) PrintProposalJson(p, f);
      std::printf("]}\n");
    } else {
      for (auto& p : items) {
        std::error_code ec;
        bool src_ok = std::filesystem::exists(aiorg::duplicate::P8pub(p.src), ec);
        std::printf("#%lld [%s] %s\n  alasan: %s\n  src %s: %s\n  dst: %s\n",
                   (long long)p.id, p.status.c_str(), p.risk.c_str(), p.reasons.c_str(),
                   src_ok ? "ADA" : "HILANG", p.src.c_str(), p.dst.c_str());
      }
    }
    return 0;
  }
  if (sub == "approve") {
    if (!is_batch) {
      if (json) std::printf("{\"ok\":false,\"error\":\"approve butuh batch (mis. p123)\"}\n");
      else spdlog::error("approve butuh batch, bukan id");
      return 2;
    }    auto moved = aiorg::duplicate::ApproveBatch(db, target, err);
    if (!err.empty()) {
      if (json) std::printf("{\"ok\":false,\"error\":\"%s\"}\n", JsonEscape(err).c_str());
      else spdlog::error("approve: {}", err);
      return 1;
    }
    db.Audit(ActorOf(argc, argv), "proposal-approve", target, "", "ok",
             "moved=" + std::to_string(moved.size()));
    if (json) {
      std::printf("{\"ok\":true,\"batch\":\"%s\",\"moved\":[", JsonEscape(target).c_str());
      bool f = true;
      for (auto& m : moved) {
        if (!f) std::printf(",");
        f = false;
        std::printf("\"%s\"", JsonEscape(m).c_str());
      }
      std::printf("]}\n");
    } else {
      std::printf("batch %s disetujui: %zu dipindah (terverifikasi + rollback tercatat)\n",
                 target.c_str(), moved.size());
    }
    return 0;
  }
  if (sub == "reject") {
    int n = 0;
    for (auto& p : items) {
      if (p.status != "pending") continue;
      std::string e2;
      if (db.ResolveProposal(p.id, "rejected", e2)) n++;
    }
    db.Audit(ActorOf(argc, argv), "proposal-reject", target, "", "ok",
             "rejected=" + std::to_string(n));
    if (json)
      std::printf("{\"ok\":true,\"rejected\":%d}\n", n);
    else
      std::printf("%d proposal ditolak\n", n);
    return 0;
  }
  Usage();
  return 2;
}

int CmdAudit(int argc, char** argv) {
  std::string db_path = FlagVal(argc, argv, "--db", "aiorganizer.db");
  std::string filter = FlagVal(argc, argv, "--action", "");
  int lim = std::stoi(FlagVal(argc, argv, "--limit", "100"));
  bool json = HasFlag(argc, argv, "--json");
  aiorg::db::Database db(db_path);
  std::string err;
  if (!db.open(err)) {
    spdlog::error("db: {}", err);
    return 1;
  }
  auto rows = db.ListAudit(filter, lim, err);
  if (!err.empty()) {
    if (json) std::printf("{\"ok\":false,\"error\":\"%s\"}\n", JsonEscape(err).c_str());
    else spdlog::error("audit: {}", err);
    return 1;
  }
  if (json) {
    std::printf("{\"ok\":true,\"audit\":[");
    bool f = true;
    for (auto& r : rows) {
      if (!f) std::printf(",");
      f = false;
      std::printf("{\"id\":%lld,\"t_ms\":%lld,\"actor\":\"%s\",\"action\":\"%s\","
                 "\"src\":\"%s\",\"dst\":\"%s\",\"result\":\"%s\",\"detail\":\"%s\"}",
                 (long long)r.id, (long long)r.t_ms, JsonEscape(r.actor).c_str(),
                 JsonEscape(r.action).c_str(), JsonEscape(r.src).c_str(),
                 JsonEscape(r.dst).c_str(), JsonEscape(r.result).c_str(),
                 JsonEscape(r.detail).c_str());
    }
    std::printf("]}\n");
  } else {
    for (auto& r : rows)
      std::printf("#%lld [%s/%s] %s %s -> %s :: %s\n", (long long)r.id,
                 r.actor.c_str(), r.result.c_str(), r.action.c_str(),
                 r.src.c_str(), r.dst.c_str(), r.detail.c_str());
  }
  return 0;
}

int CmdDoctor(int argc, char** argv) {
  std::string db_path = FlagVal(argc, argv, "--db", "aiorganizer.db");
  std::string root = FlagVal(argc, argv, "--root", "");
  bool json = HasFlag(argc, argv, "--json");
  struct Check { std::string name, status, detail; };
  std::vector<Check> cs;
  auto add = [&](const std::string& n, const std::string& s, const std::string& d) {
    cs.push_back({n, s, d});
  };
  bool mem = (db_path == ":memory:");
  add("core", "OK", "aiorganizer 0.3.0 (db v4)");
  add("sqlite", "OK", sqlite3_libversion());
  if (!mem) {
    std::error_code ec;
    bool exists = std::filesystem::exists(aiorg::duplicate::P8pub(db_path), ec);
    add("database-file", exists ? "OK" : "WARN", exists ? db_path : "belum ada, dibuat saat open");
  } else {
    add("database-file", "OK", ":memory: (efemeral, tak tersimpan)");
  }
  {
    aiorg::db::Database db(db_path);
    std::string err;
    if (!db.open(err)) {
      add("database-open", "FAIL", err);
    } else {
      add("database-open", "OK", "WAL, synchronous=NORMAL");
      std::string ic = db.IntegrityCheck();
      add("database-integrity", ic == "ok" ? "OK" : "FAIL", ic);
      int uv = db.user_version();
      add("schema-version", uv == aiorg::db::kSchemaVersion ? "OK" : "FAIL",
          "user_version=" + std::to_string(uv));
      add("journal-mode", "OK", db.JournalMode());
      auto s = db.Stats("");
      add("stats", "OK", "files=" + std::to_string(s.files) +
                             " dup_groups=" + std::to_string(s.dup_groups));
    }
  }
  if (!mem) {
    std::filesystem::path dir = aiorg::duplicate::P8pub(db_path).parent_path();
    if (dir.empty()) dir = ".";
    std::error_code ec;
    auto sp = std::filesystem::space(dir, ec);
    if (!ec) {
      long long free_gb = (long long)sp.available / (1024 * 1024 * 1024);
      add("disk-space", free_gb >= 1 ? "OK" : "WARN",
          std::to_string(free_gb) + " GB bebas");
    }
    std::filesystem::path probe = dir / ".aiorg_write_test";
    bool writable = false;
    {
      FILE* f = nullptr;
#ifdef _WIN32
      writable = (_wfopen_s(&f, probe.c_str(), L"wb") == 0);
#else
      f = std::fopen(probe.string().c_str(), "wb");
      writable = (f != nullptr);
#endif
      if (f) std::fclose(f);
      std::error_code ec2;
      std::filesystem::remove(probe, ec2);
    }
    add("write-permission", writable ? "OK" : "FAIL", "");
  }
  {
    const char* env = std::getenv("AIORG_FFPROBE");
    std::string cand = env ? env : "engine-py/app/ffmpeg/bin/ffprobe.exe";
    std::error_code ec;
    bool ok = std::filesystem::exists(aiorg::duplicate::P8pub(cand), ec);
    add("ffprobe", ok ? "OK" : "WARN", ok ? cand : "tak ada (mode video-broken nonaktif)");
  }
  if (!root.empty()) {
    std::error_code ec;
    bool ok = std::filesystem::is_directory(aiorg::duplicate::P8pub(root), ec);
    add("source-volume", ok ? "OK" : "FAIL", root);
  }
  bool allok = true;
  for (auto& c : cs) if (c.status == "FAIL") allok = false;
  if (json) {
    std::printf("{\"ok\":%s,\"checks\":[", allok ? "true" : "false");
    bool f = true;
    for (auto& c : cs) {
      if (!f) std::printf(",");
      f = false;
      std::printf("{\"name\":\"%s\",\"status\":\"%s\",\"detail\":\"%s\"}",
                 JsonEscape(c.name).c_str(), JsonEscape(c.status).c_str(),
                 JsonEscape(c.detail).c_str());
    }
    std::printf("]}\n");
  } else {
    for (auto& c : cs)
      std::printf("[%s] %s: %s\n", c.status.c_str(), c.name.c_str(), c.detail.c_str());
  }
  return allok ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
  spdlog::set_pattern("[%H:%M:%S] [%l] %v");
  if (argc >= 2) {
    std::string sub = argv[1];
    if (sub == "version") {
      std::puts("aiorganizer 0.3.0 (AIOrganizerPro unified core, db v4)");
      return 0;
    }
    if (sub == "scan") return CmdScan(argc, argv);
    if (sub == "duplicates") return CmdDuplicates(argc, argv);
    if (sub == "move-approved") return CmdMoveApproved(argc, argv);
    if (sub == "stats") return CmdStats(argc, argv);
    if (sub == "job-enqueue" || sub == "job-claim" || sub == "job-finish" ||
        sub == "job-list" || sub == "job-pause" || sub == "job-resume" ||
        sub == "job-cancel")
      return CmdJobs(argc, argv, sub);
    if (sub == "proposals" && argc >= 3)
      return CmdProposals(argc, argv, argv[2]);
    if (sub == "audit") return CmdAudit(argc, argv);
    if (sub == "doctor") return CmdDoctor(argc, argv);
    if (sub == "hash" && argc >= 3) {
      std::string file, db_path;
      for (int i = 2; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--db" && i + 1 < argc)
          db_path = argv[++i];
        else if (!a.empty() && a[0] != '-')
          file = a;
      }
      if (file.empty()) {
        Usage();
        return 2;
      }
      aiorg::db::Database* dbp = nullptr;
      aiorg::db::Database db(db_path.empty() ? ":memory:" : db_path);
      std::string err;
      if (!db_path.empty()) {
        if (!db.open(err)) {
          spdlog::error("db: {}", err);
          return 1;
        }
        dbp = &db;
      }
      auto q = aiorg::hash::QuickHash(file);
      auto p = aiorg::hash::PartialHash(file);
      auto f = aiorg::hash::FullHash(file);
      std::printf("quick:   %s\npartial: %s\nfull:    %s\n",
                  q.ok ? q.hex.c_str() : ("ERR " + q.error).c_str(),
                  p.ok ? p.hex.c_str() : ("ERR " + p.error).c_str(),
                  f.ok ? f.hex.c_str() : ("ERR " + f.error).c_str());
      (void)dbp;
      return (q.ok && p.ok && f.ok) ? 0 : 1;
    }
  }
  Usage();
  return 2;
}
