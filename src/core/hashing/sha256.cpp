// SHA-256: BCrypt on Windows, portable fallback elsewhere.
#include "sha256.h"

#include <cstdio>
#include <cstring>

#include "../filesystem/utf8.h"

#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#pragma comment(lib, "bcrypt.lib")
#else
#define AIORG_SHA256_FALLBACK 1
#endif

namespace aiorg::hash {
namespace {

#ifdef AIORG_SHA256_FALLBACK
// Minimal portable SHA-256 (FIPS 180-4). Used only off-Windows.
struct Ctx {
  uint32_t h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                   0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
  uint64_t total = 0;
  uint8_t buf[64] = {};
  size_t used = 0;
};
inline uint32_t Ror(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }
void Block(Ctx& c, const uint8_t* p) {
  static const uint32_t K[64] = {
      0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
      0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
      0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
      0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
      0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
      0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
      0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
      0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
      0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
  uint32_t w[64];
  for (int i = 0; i < 16; i++)
    w[i] = ((uint32_t)p[i * 4] << 24) | ((uint32_t)p[i * 4 + 1] << 16) |
           ((uint32_t)p[i * 4 + 2] << 8) | p[i * 4 + 3];
  for (int i = 16; i < 64; i++) {
    uint32_t s0 = Ror(w[i - 15], 7) ^ Ror(w[i - 15], 18) ^ (w[i - 15] >> 3);
    uint32_t s1 = Ror(w[i - 2], 17) ^ Ror(w[i - 2], 19) ^ (w[i - 2] >> 10);
    w[i] = w[i - 16] + s0 + w[i - 7] + s1;
  }
  uint32_t a = c.h[0], b = c.h[1], cc = c.h[2], d = c.h[3], e = c.h[4],
           f = c.h[5], g = c.h[6], h = c.h[7];
  for (int i = 0; i < 64; i++) {
    uint32_t S1 = Ror(e, 6) ^ Ror(e, 11) ^ Ror(e, 25);
    uint32_t ch = (e & f) ^ (~e & g);
    uint32_t t1 = h + S1 + ch + K[i] + w[i];
    uint32_t S0 = Ror(a, 2) ^ Ror(a, 13) ^ Ror(a, 22);
    uint32_t mj = (a & b) ^ (a & cc) ^ (b & cc);
    uint32_t t2 = S0 + mj;
    h = g;
    g = f;
    f = e;
    e = d + t1;
    d = cc;
    cc = b;
    b = a;
    a = t1 + t2;
  }
  c.h[0] += a;
  c.h[1] += b;
  c.h[2] += cc;
  c.h[3] += d;
  c.h[4] += e;
  c.h[5] += f;
  c.h[6] += g;
  c.h[7] += h;
}
void Update(Ctx& c, const uint8_t* data, size_t n) {
  c.total += n;
  while (n > 0) {
    size_t take = 64 - c.used;
    if (take > n) take = n;
    memcpy(c.buf + c.used, data, take);
    c.used += take;
    data += take;
    n -= take;
    if (c.used == 64) {
      Block(c, c.buf);
      c.used = 0;
    }
  }
}
void Final(Ctx& c, uint8_t out[32]) {
  uint64_t bits = c.total * 8;
  uint8_t pad = 0x80;
  Update(c, &pad, 1);
  uint8_t zero = 0;
  while (c.used != 56) Update(c, &zero, 1);
  uint8_t len[8];
  for (int i = 0; i < 8; i++) len[i] = (uint8_t)(bits >> (56 - i * 8));
  Update(c, len, 8);
  for (int i = 0; i < 8; i++) {
    out[i * 4] = (uint8_t)(c.h[i] >> 24);
    out[i * 4 + 1] = (uint8_t)(c.h[i] >> 16);
    out[i * 4 + 2] = (uint8_t)(c.h[i] >> 8);
    out[i * 4 + 3] = (uint8_t)c.h[i];
  }
}
#endif

class FileReader {
 public:
  explicit FileReader(const std::string& utf8_path) {
#ifdef _WIN32
    h_ = CreateFileW(fsutil::PathFromUtf8(utf8_path).c_str(), GENERIC_READ,
                     FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                     nullptr, OPEN_EXISTING, FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    ok_ = (h_ != INVALID_HANDLE_VALUE);
#else
    f_ = std::fopen(utf8_path.c_str(), "rb");
    ok_ = (f_ != nullptr);
#endif
    if (!ok_) err_ = "open failed";
  }
  ~FileReader() {
#ifdef _WIN32
    if (h_ != INVALID_HANDLE_VALUE) CloseHandle(h_);
#else
    if (f_) std::fclose(f_);
#endif
  }
  bool ok() const { return ok_; }
  const std::string& error() const { return err_; }
  // Returns bytes read (0 = EOF), -1 on error.
  int64_t Read(uint8_t* buf, size_t n) {
#ifdef _WIN32
    DWORD got = 0;
    if (!ReadFile(h_, buf, (DWORD)n, &got, nullptr)) {
      err_ = "read failed";
      return -1;
    }
    return (int64_t)got;
#else
    size_t got = std::fread(buf, 1, n, f_);
    if (got == 0 && std::ferror(f_)) {
      err_ = "read failed";
      return -1;
    }
    return (int64_t)got;
#endif
  }

 private:
#ifdef _WIN32
  HANDLE h_ = INVALID_HANDLE_VALUE;
#else
  std::FILE* f_ = nullptr;
#endif
  bool ok_ = false;
  std::string err_;
};

}  // namespace

std::string HexOf(const uint8_t digest[32]) {
  static const char* kHex = "0123456789abcdef";
  std::string out;
  out.reserve(64);
  for (int i = 0; i < 32; i++) {
    out += kHex[digest[i] >> 4];
    out += kHex[digest[i] & 15];
  }
  return out;
}

Result HashFile(const std::string& utf8_path, uint64_t limit) {
  Result r;
  FileReader f(utf8_path);
  if (!f.ok()) {
    r.error = f.error();
    return r;
  }
#ifdef _WIN32
  BCRYPT_ALG_HANDLE alg = nullptr;
  BCRYPT_HASH_HANDLE h = nullptr;
  DWORD hash_len = 0, tmp = 0;
  bool bcrypt_ok = false;
  if (BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, nullptr, 0)) &&
      BCRYPT_SUCCESS(BCryptGetProperty(alg, BCRYPT_HASH_LENGTH, (PUCHAR)&hash_len,
                                       sizeof(hash_len), &tmp, 0)) &&
      hash_len == 32 &&
      BCRYPT_SUCCESS(BCryptCreateHash(alg, &h, nullptr, 0, nullptr, 0, 0))) {
    bcrypt_ok = true;
  } else {
    if (alg) BCryptCloseAlgorithmProvider(alg, 0);
    r.error = "bcrypt init failed";
    return r;
  }
#endif
  std::vector<uint8_t> buf((size_t)(limit && limit < kIoChunk ? limit : kIoChunk));
  uint64_t left = limit;
#ifdef AIORG_SHA256_FALLBACK
  Ctx fctx;
#endif
  while (true) {
    size_t want = buf.size();
    if (limit && (uint64_t)want > left) want = (size_t)left;
    if (want == 0) break;
    int64_t got = f.Read(buf.data(), want);
    if (got < 0) {
      r.error = f.error();
#ifdef _WIN32
      BCryptDestroyHash(h);
      BCryptCloseAlgorithmProvider(alg, 0);
#endif
      return r;
    }
    if (got == 0) break;
#ifdef _WIN32
    if (!BCRYPT_SUCCESS(BCryptHashData(h, buf.data(), (ULONG)got, 0))) {
      r.error = "bcrypt hash failed";
      BCryptDestroyHash(h);
      BCryptCloseAlgorithmProvider(alg, 0);
      return r;
    }
#else
    Update(fctx, buf.data(), (size_t)got);
#endif
    r.bytes_read += (uint64_t)got;
    if (limit) {
      left -= (uint64_t)got;
      if (left == 0) break;
    }
  }
#ifdef _WIN32
  uint8_t digest[32] = {};
  bool ok = BCRYPT_SUCCESS(BCryptFinishHash(h, digest, sizeof(digest), 0));
  BCryptDestroyHash(h);
  BCryptCloseAlgorithmProvider(alg, 0);
  if (!ok) {
    r.error = "bcrypt finish failed";
    return r;
  }
  r.hex = HexOf(digest);
  r.ok = true;
  return r;
#else
  uint8_t digest[32] = {};
  Final(fctx, digest);
  r.hex = HexOf(digest);
  r.ok = true;
  return r;
#endif
}

}  // namespace aiorg::hash
