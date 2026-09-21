#pragma once
// Fast recursive scanner: traversal -> metadata -> SQLite index.
// Only new/changed files are marked for downstream work (SKIP unchanged).
// Single traversal thread; commits in batches. Never throws on bad files:
// errors are counted + logged to the database.
#include <atomic>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <string>
#include <vector>

namespace aiorg::db {
class Database;
}

namespace aiorg::scanner {

struct Progress {
  uint64_t seen = 0;
  uint64_t fresh = 0;    // PROCESS
  uint64_t changed = 0;  // RESCAN
  uint64_t unchanged = 0;  // SKIP
  uint64_t errors = 0;
  uint64_t bytes_seen = 0;
  std::string current;
};

struct Options {
  std::string root;
  // Jangan scan folder output sendiri (kontrak: output bukan sumber).
  std::vector<std::string> skip_dir_names = {"$RECYCLE.BIN", "System Volume Information",
                                              ".ai_organizer.lock", "duplicate", "broken",
                                              "results", "duplikat", "video_broken_detection"};
  bool follow_symlinks = false;
  int commit_batch = 2000;
};

struct FileMeta {
  std::string path;  // UTF-8, generic separators
  std::string filename;
  std::string extension;
  int64_t size = 0;
  int64_t mtime_ns = 0;
  uint64_t volume_serial = 0;
  uint64_t file_index = 0;
  std::string file_type;  // video|image|audio|document|archive|other
};

std::string ClassifyType(const std::string& ext_lower);
// Takes a NATIVE path (wide on Windows). Never pass narrow on Windows.
bool ReadMeta(const std::filesystem::path& native, FileMeta& out, std::string& err);

// Adaptive worker suggestion (storage-aware stub; tuned by benchmarks later).
int SuggestedWorkers(const std::string& root);

class Scanner {
 public:
  using ProgressCb = std::function<void(const Progress&)>;
  using ErrorCb = std::function<void(const std::string& path, const std::string& msg)>;

  Scanner(db::Database& db, Options opts);
  // Returns false only on fatal root error. Honors cancel/pause.
  bool run(const std::atomic<bool>& cancel, const std::atomic<bool>& paused,
           ProgressCb on_progress, ErrorCb on_error, std::string& err);

 private:
  db::Database& db_;
  Options opts_;
};

}  // namespace aiorg::scanner
