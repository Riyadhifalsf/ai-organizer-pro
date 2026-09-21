#pragma once
// Duplicate engine: group by (size -> quick -> partial -> full SHA-256).
// Reads candidates from the SQLite index, reuses the hash stage cache
// (unchanged files are never re-read), persists confirmed groups.
// Destructive action is APPROVED MOVE ONLY: one member stays, the rest are
// relocated to a quarantine dir with full rollback info in `moves`.
// Never deletes. Never throws on bad files: errors go to the DB.
#include <atomic>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <optional>
#include <string>
#include <vector>

#include "core/database/database.h"

namespace aiorg::duplicate {

// Wide-safe: std::string selalu UTF-8; jangan pakai konversi narrow di Windows.
std::filesystem::path P8pub(const std::string& utf8);

struct Progress {
  uint64_t size_groups = 0;
  uint64_t hashed = 0;
  uint64_t confirmed_groups = 0;
  uint64_t errors = 0;
  std::string current;
};

struct Options {
  std::string root;        // UTF-8 generic prefix filter, e.g. "D:/Data"
  int64_t min_size = 1;    // ignore files smaller than this
  int workers = 4;         // hash threads (clamped 1..8 by pipeline)
};

// Finds exact duplicates under root, persists groups, returns confirmed ones.
std::vector<aiorg::db::DupeGroup> FindDuplicates(
    aiorg::db::Database& db, const Options& opts,
    const std::atomic<bool>& cancel,
    std::function<void(const Progress&)> on_progress, std::string& err);

// Lists persisted groups that still have >1 member (active groups).
std::vector<aiorg::db::DupeGroup> ListActiveGroups(aiorg::db::Database& db,
                                                  const std::string& root_prefix,
                                                  std::string& err);

// Approved move: keep `keep_path`, relocate every other member of `group_id`
// into `dest_dir`. Verifies size after each move, logs rollback info.
// Returns moved destination paths. Never deletes the kept file.
std::vector<std::string> ApproveMove(aiorg::db::Database& db, int64_t group_id,
                                     const std::string& keep_path,
                                     const std::string& dest_dir, std::string& err);

// v4 proposal flow (master doc #150: list/preview/approve, GUI shares service):
// ProposeFromGroup records one pending proposal per moved file, returns batch id.
// ApproveBatch executes all pending proposals of a batch with the same
// verified-move guarantees as ApproveMove. Nothing moves before approve.
std::string ProposeFromGroup(aiorg::db::Database& db, int64_t group_id,
                             const std::string& keep_path,
                             const std::string& dest_dir,
                             const std::string& reasons, std::string& err);
std::vector<std::string> ApproveBatch(aiorg::db::Database& db,
                                      const std::string& batch,
                                      std::string& err);

}  // namespace aiorg::duplicate
