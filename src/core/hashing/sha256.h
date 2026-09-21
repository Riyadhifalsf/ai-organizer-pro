#pragma once
// SHA-256 streaming. Windows: BCrypt (native, no extra dependency).
// Other platforms: bundled portable fallback (same test vectors).
// NEVER hash whole files blindly: use HashKind to stage work.
#include <cstdint>
#include <string>
#include <vector>

namespace aiorg::hash {

enum class Kind { kQuick, kPartial, kFull };

// Limits: quick reads head bytes, partial reads head bytes (1 MiB).
inline constexpr uint64_t kQuickBytes = 64ull * 1024;
inline constexpr uint64_t kPartialBytes = 1024ull * 1024;
inline constexpr uint64_t kIoChunk = 4ull * 1024 * 1024;

struct Result {
  bool ok = false;
  std::string hex;  // lowercase hex digest
  uint64_t bytes_read = 0;
  std::string error;
};

// Hash first `limit` bytes (0 = whole file) of native path given as UTF-8 generic.
Result HashFile(const std::string& utf8_path, uint64_t limit);
inline Result QuickHash(const std::string& p) { return HashFile(p, kQuickBytes); }
inline Result PartialHash(const std::string& p) { return HashFile(p, kPartialBytes); }
inline Result FullHash(const std::string& p) { return HashFile(p, 0); }

std::string HexOf(const uint8_t digest[32]);

}  // namespace aiorg::hash
