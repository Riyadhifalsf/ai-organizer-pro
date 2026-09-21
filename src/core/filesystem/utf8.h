#pragma once
// UTF-8 path utilities (Windows-safe).
// NEVER rely on std::filesystem narrow conversions on Windows:
// MSVC's ANSI-codepage conversion can crash (observed STATUS_STACK_BUFFER_OVERRUN)
// and corrupts non-ANSI names into '?'. DB stores UTF-8; fs calls use wide paths.
#include <filesystem>
#include <string>

namespace aiorg::fsutil {

namespace fs = std::filesystem;

// Wide -> UTF-8 (lossy-safe: unconvertible chars become U+FFFD, never throws).
std::string ToUtf8(const std::wstring& w);
// UTF-8 -> wide (lossy-safe).
std::wstring ToWide(const std::string& u);
// Native path -> generic UTF-8 ("a/b/c"). Safe on all platforms.
std::string PathToUtf8(const fs::path& p);
// UTF-8 generic -> native path (wide on Windows).
fs::path PathFromUtf8(const std::string& u);
// Console-safe: non-ASCII replaced with '?'. For printf/logging only.
std::string ToDisplay(const std::string& utf8);

}  // namespace aiorg::fsutil
