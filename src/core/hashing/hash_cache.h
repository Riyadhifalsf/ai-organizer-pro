#pragma once
// Hash stage cache over the `hashes` table: (path,size,mtime_ns,stage)->sha256.
// Unchanged files never re-hash. Schema v2 migrates v1 (adds mtime_ns, stage).
#include <cstdint>
#include <optional>
#include <string>

namespace aiorg::db {
class Database;
}

namespace aiorg::hash {

enum class Stage : int { kQuick = 1, kPartial = 2, kFull = 3 };

// Returns cached digest if (size,mtime,stage) match, else nullopt.
std::optional<std::string> Lookup(db::Database& db, const std::string& path,
                                  int64_t size, int64_t mtime_ns, Stage stage);
bool Store(db::Database& db, const std::string& path, int64_t size,
           int64_t mtime_ns, Stage stage, const std::string& sha256);

}  // namespace aiorg::hash
