#pragma once
// Local SQLite index: files, hashes, sessions, errors, settings.
// WAL mode. Schema migrated via PRAGMA user_version. Never stores file data.
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <vector>

struct sqlite3;

namespace aiorg::db {

constexpr int kSchemaVersion = 4;

struct FileRow {
  int64_t id = 0;
  std::string path;
  std::string filename;
  std::string extension;
  int64_t size = 0;
  int64_t mtime_ns = 0;
  uint64_t volume_serial = 0;
  uint64_t file_index = 0;  // NTFS file id (hi/lo) when available
  std::string file_type;
  std::string hash_status = "pending";  // pending|partial|full|error
  std::string scan_status = "new";      // new|indexed|changed|gone|error
  std::string ai_status = "pending";
  int64_t last_seen_ms = 0;
  std::string sha256;
  std::string error;
};

// v3 unified-schema rows (duplicates, jobs, stats). Never store file data.
struct DupeGroup {
  int64_t id = 0;
  int64_t size = 0;
  std::string sha256;
  std::vector<std::string> paths;  // UTF-8 generic, sorted
};

struct SizeCandidate {
  std::string path;
  int64_t size = 0;
  int64_t mtime_ns = 0;
};

struct Job {
  int64_t id = 0;
  std::string kind;
  std::string payload;
  std::string status;
  int64_t created_ms = 0;
  int64_t started_ms = 0;
  int64_t ended_ms = 0;
  std::string result;
};

// v4: proposal organizer (master doc #150: list/preview/approve) + audit.
struct Proposal {
  int64_t id = 0;
  int64_t created_ms = 0;
  std::string batch;
  std::string kind;    // move
  std::string action;  // move
  int64_t group_id = 0;  // grup duplikat asal (0 = umum)
  std::string src;
  std::string dst;     // tujuan yang diminta (tabrakan di-resolve saat approve)
  std::string reasons;  // "Why this file is proposed here?"
  std::string risk;     // low|medium|high
  std::string status;   // pending|approved|done|rejected|failed
};

struct AuditRow {
  int64_t id = 0;
  int64_t t_ms = 0;
  std::string actor;   // cli|gui|daemon
  std::string action;  // scan|duplicates|move|proposal|job|...
  std::string src;
  std::string dst;
  std::string result;  // ok|fail|dry-run
  std::string detail;
};

struct DbStats {
  int64_t files = 0;
  int64_t gone = 0;
  int64_t errors = 0;
  int64_t dup_groups = 0;
  int64_t dup_files = 0;
  int64_t pending_jobs = 0;
  int64_t sessions = 0;
  int64_t proposals = 0;  // v4: pending proposals
  int64_t audit_rows = 0;  // v4: audit_log rows
};

class Database {
 public:
  explicit Database(std::string path);
  ~Database();
  Database(const Database&) = delete;
  Database& operator=(const Database&) = delete;

  bool open(std::string& err);
  int user_version();
  bool migrate(std::string& err);

  // Files
  std::optional<FileRow> find_by_path(const std::string& path);
  bool upsert_file(const FileRow& row, std::string& err);
  bool mark_gone_before(int64_t cutoff_ms, const std::string& root_prefix, int64_t& count,
                        std::string& err);
  // Max last_seen_ms under root (for airtight gone-detection). -1 if none.
  int64_t max_last_seen(const std::string& root_prefix);
  int64_t file_count();

  // Sessions / errors / settings
  int64_t begin_session(const std::string& kind, const std::string& root);
  bool end_session(int64_t id, const std::string& summary, std::string& err);
  bool log_error(const std::string& stage, const std::string& path,
                 const std::string& message);
  bool set_setting(const std::string& k, const std::string& v);
  std::string get_setting(const std::string& k, const std::string& def = "");

  // Hash stage cache: v2 schema (path,size,mtime_ns,stage)->sha256.
  std::optional<std::string> hash_lookup(const std::string& path, int64_t size,
                                         int64_t mtime_ns, int stage);
  bool hash_store(const std::string& path, int64_t size, int64_t mtime_ns,
                  int stage, const std::string& sha256, std::string& err);

  // ---- v3: duplicates / moves / jobs / behavior / docs (unified DB) ----
  std::vector<SizeCandidate> SameSizeCandidates(const std::string& root_prefix,
                                               int64_t min_size,
                                               std::string& err);
  int64_t SaveDuplicateGroup(int64_t size, const std::string& sha256,
                             const std::vector<std::string>& paths,
                             std::string& err);
  std::vector<DupeGroup> ListDuplicateGroups(const std::string& root_prefix,
                                            std::string& err);
  bool RemoveDupeMember(int64_t group_id, const std::string& path,
                        std::string& err);
  bool LogMove(int64_t group_id, const std::string& src,
               const std::string& dst, int64_t size,
               const std::string& rollback, std::string& err);
  int64_t EnqueueJob(const std::string& kind, const std::string& payload);
  bool ClaimJob(Job& out, std::string& err);
  bool FinishJob(int64_t id, const std::string& status,
                 const std::string& result, std::string& err);
  // v4: daftar + pause/resume/cancel (transisi divalidasi) + checkpoint.
  std::vector<Job> ListJobs(const std::string& status_filter, int limit,
                            std::string& err);
  bool SetJobStatus(int64_t id, const std::string& status, std::string& err);
  bool SaveCheckpoint(int64_t job_id, const std::string& state);
  std::optional<std::string> LoadCheckpoint(int64_t job_id);
  // v4: audit tahan lama (terpisah dari log aplikasi).
  bool Audit(const std::string& actor, const std::string& action,
             const std::string& src, const std::string& dst,
             const std::string& result, const std::string& detail);
  std::vector<AuditRow> ListAudit(const std::string& action_filter, int limit,
                                  std::string& err);
  // v4: proposal organizer. Satu baris per file (src->dst), dikelompokkan batch.
  std::string ProposeMoves(int64_t group_id, const std::string& keep,
                           const std::string& dest_dir,
                           const std::vector<std::pair<std::string, std::string>>& items,
                           const std::string& reasons, const std::string& risk,
                           std::string& err);
  std::vector<Proposal> ListProposals(const std::string& status_filter,
                                      std::string& err);
  std::vector<Proposal> BatchProposals(const std::string& batch,
                                       std::string& err);
  bool ResolveProposal(int64_t id, const std::string& status,
                       std::string& err);
  // v4: doctor helpers.
  std::string IntegrityCheck();
  std::string JournalMode();
  bool RecordBehavior(const std::string& kind, const std::string& path,
                      const std::string& detail);
  // kind -> count (for GUI recommendations panel).
  std::vector<std::pair<std::string, int64_t>> BehaviorSummary(int limit);
  DbStats Stats(const std::string& root_prefix);

  bool exec(const std::string& sql, std::string& err);

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
  std::string path_;
};

int64_t NowMs();
std::string ToLower(std::string s);

}  // namespace aiorg::db
