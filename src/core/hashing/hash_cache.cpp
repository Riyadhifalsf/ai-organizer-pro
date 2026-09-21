// Hash cache over Database::hash_lookup/hash_store (schema v2).
#include "hash_cache.h"

#include "../database/database.h"

namespace aiorg::hash {

std::optional<std::string> Lookup(db::Database& db, const std::string& path,
                                  int64_t size, int64_t mtime_ns, Stage stage) {
  return db.hash_lookup(path, size, mtime_ns, (int)stage);
}

bool Store(db::Database& db, const std::string& path, int64_t size,
           int64_t mtime_ns, Stage stage, const std::string& sha256) {
  std::string err;
  return db.hash_store(path, size, mtime_ns, (int)stage, sha256, err);
}

}  // namespace aiorg::hash
