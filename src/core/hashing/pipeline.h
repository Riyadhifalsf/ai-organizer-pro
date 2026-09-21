#pragma once
// Hash pipeline: size -> quick -> partial -> full, with SQLite stage cache.
// I/O-bound pool (small, storage-aware). CPU work (hashing) rides along the
// reader thread; separation of I/O vs compare happens in duplicate engine.
// Callbacks: progress + per-file error. Cancellation + resume via cache.
#include <atomic>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

#include "hash_cache.h"

namespace aiorg::db {
class Database;
}

namespace aiorg::hash {

struct Target {
  std::string path;  // UTF-8 generic
  int64_t size = 0;
  int64_t mtime_ns = 0;
};

struct Stats {
  uint64_t quick_hit = 0, quick_new = 0;
  uint64_t partial_hit = 0, partial_new = 0;
  uint64_t full_hit = 0, full_new = 0;
  uint64_t errors = 0;
  uint64_t bytes_read = 0;
};

struct Outcome {
  // path -> {quick, partial, full} digests (empty string = not computed)
  std::string path;
  std::string quick, partial, full;
  std::string error;
};

// Hash `upto` stage for each target (stages below are always computed first).
// Results carry digests for grouping; cache makes reruns nearly free.
std::vector<Outcome> HashFiles(db::Database& db, const std::vector<Target>& targets,
                               Stage upto, int workers,
                               const std::atomic<bool>& cancel,
                               std::function<void(uint64_t done, uint64_t total)> on_progress,
                               Stats& stats);

}  // namespace aiorg::hash
