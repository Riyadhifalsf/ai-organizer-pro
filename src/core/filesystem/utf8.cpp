// UTF-8 path utilities implementation.
#include "utf8.h"

#ifdef _WIN32
#include <windows.h>
#endif

namespace aiorg::fsutil {

std::string ToUtf8(const std::wstring& w) {
#ifdef _WIN32
  if (w.empty()) return {};
  int n = WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), nullptr, 0, nullptr, nullptr);
  if (n <= 0) return {};
  std::string out((size_t)n, '\0');
  WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), out.data(), n, nullptr, nullptr);
  return out;
#else
  // POSIX narrow encoding is already UTF-8 in practice.
  std::string out;
  out.reserve(w.size());
  for (wchar_t c : w) {
    if (c < 0x80)
      out += (char)c;
    else
      out += "\xEF\xBF\xBD";  // U+FFFD
  }
  return out;
#endif
}

std::wstring ToWide(const std::string& u) {
#ifdef _WIN32
  if (u.empty()) return {};
  int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, u.data(), (int)u.size(), nullptr, 0);
  if (n <= 0) {
    // Fallback: ANSI code page for legacy narrow input.
    n = MultiByteToWideChar(CP_ACP, 0, u.data(), (int)u.size(), nullptr, 0);
    if (n <= 0) return {};
    std::wstring out((size_t)n, L'\0');
    MultiByteToWideChar(CP_ACP, 0, u.data(), (int)u.size(), out.data(), n);
    return out;
  }
  std::wstring out((size_t)n, L'\0');
  MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, u.data(), (int)u.size(), out.data(), n);
  return out;
#else
  return std::wstring(u.begin(), u.end());
#endif
}

std::string PathToUtf8(const fs::path& p) {
#ifdef _WIN32
  std::wstring w = p.generic_wstring();
  // generic_wstring avoids narrow conversion entirely.
  std::string u8 = ToUtf8(w);
  if (!u8.empty()) return u8;
  // Last resort: per-character ASCII-fy (never crash, may collide).
  std::string out;
  for (wchar_t c : w) out += (c < 0x80) ? (char)c : '?';
  for (auto& c : out)
    if (c == '\\') c = '/';
  return out;
#else
  return p.generic_string();
#endif
}

fs::path PathFromUtf8(const std::string& u) {
#ifdef _WIN32
  return fs::path(ToWide(u));
#else
  return fs::path(u);
#endif
}

std::string ToDisplay(const std::string& utf8) {
  // Decode UTF-8, replace non-ASCII code points with '?'.
  std::string out;
  out.reserve(utf8.size());
  for (size_t i = 0; i < utf8.size();) {
    unsigned char c = (unsigned char)utf8[i];
    size_t len = 1;
    if ((c & 0x80) == 0)
      len = 1;
    else if ((c & 0xE0) == 0xC0)
      len = 2;
    else if ((c & 0xF0) == 0xE0)
      len = 3;
    else if ((c & 0xF8) == 0xF0)
      len = 4;
    if (len == 1)
      out += (char)c;
    else {
      out += '?';
      // Validate continuation bytes; resync on error.
      for (size_t k = 1; k < len && i + k < utf8.size(); k++) {
        if (((unsigned char)utf8[i + k] & 0xC0) != 0x80) {
          len = k;
          break;
        }
      }
    }
    i += len;
  }
  return out;
}

}  // namespace aiorg::fsutil
