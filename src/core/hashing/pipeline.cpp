// Hash pipeline: staged hashing with cache, small I/O pool.
#include "pipeline.h"

#include <algorithm>
#include <mutex>
#include <queue>
#include <thread>

#include "../database/database.h"
#include "hash_cache.h"
#include "sha256.h"

namespace aiorg::hash {

std::vector<Outcome> HashFiles(db::Database& db, const std::vector<Target>& targets,
                               Stage upto, int workers,
                               const std::atomic<bool>& cancel,
                               std::function<void(uint64_t, uint64_t)> on_progress,
                               Stats& stats) {
  std::vector<Outcome> out(targets.size());
  if (targets.empty()) return out;
  if (workers < 1) workers = 1;
  if (workers > 8) workers = 8;  // I/O-bound: more threads != faster (see benchmarks)

  std::mutex mtx;  // guards db + stats (sqlite handle is single-threaded here)
  std::atomic<uint64_t> next{0}, done{0};
  auto work = [&](int) {
    while (!cancel.load()) {
      uint64_t i = next.fetch_add(1);
      if (i >= targets.size()) break;
      const Target& t = targets[i];
      Outcome o;
      o.path = t.path;
      auto stage = [&](Stage s, std::string& slot, uint64_t& hit, uint64_t& nw) {
        if (auto hit_v = Lookup(db, t.path, t.size, t.mtime_ns, s)) {
          slot = *hit_v;
          std::lock_guard<std::mutex> g(mtx);
          hit++;
          return true;
        }
        Result r = (s == Stage::kQuick)    ? QuickHash(t.path)
                   : (s == Stage::kPartial) ? PartialHash(t.path)
                                            : FullHash(t.path);
        std::lock_guard<std::mutex> g(mtx);
        if (!r.ok) {
          o.error = r.error;
          stats.errors++;
          return false;
        }
        slot = r.hex;
        stats.bytes_read += r.bytes_read;
        Store(db, t.path, t.size, t.mtime_ns, s, r.hex);
        nw++;
        return true;
      };
      bool ok = true;
      // Stages run in order; stop early on error. Only compute up to `upto`.
      if (ok) ok = stage(Stage::kQuick, o.quick, stats.quick_hit, stats.quick_new);
      if (ok && (int)upto >= (int)Stage::kPartial)
        ok = stage(Stage::kPartial, o.partial, stats.partial_hit, stats.partial_new);
      if (ok && (int)upto >= (int)Stage::kFull)
        ok = stage(Stage::kFull, o.full, stats.full_hit, stats.full_new);
      out[i] = std::move(o);
      uint64_t d = ++done;
      if (on_progress && (d % 16 == 0 || d == targets.size())) on_progress(d, targets.size());
    }
  };
  // NOTE: sqlite connection used under a single mutex (serialized). Throughput
  // comes from overlapping reads, not parallel writes. Measured later.
  std::vector<std::thread> pool;
  for (int w = 0; w < workers; w++) pool.emplace_back(work, w);
  for (auto& t : pool) t.join();
  if (on_progress) on_progress(done.load(), targets.size());
  return out;
}

}  // namespace aiorg::hash
