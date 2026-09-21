// Scanner implementation. Windows: NTFS identity via GetFileInformationByHandle.
#include "scanner.h"

#include <spdlog/spdlog.h>

#include <algorithm>
#include <chrono>
#include <cctype>
#include <filesystem>
#include <thread>

#include "../database/database.h"
#include "../filesystem/utf8.h"

#ifdef _WIN32
#include <windows.h>
#endif

namespace aiorg::scanner {
namespace fs = std::filesystem;

std::string ClassifyType(const std::string& ext) {
  using namespace std::string_literals;
  if (ext == ".mp4" || ext == ".mkv" || ext == ".avi" || ext == ".mov" ||
      ext == ".wmv" || ext == ".webm" || ext == ".m2ts" || ext == ".mts" ||
      ext == ".ts" || ext == ".flv" || ext == ".m4v" || ext == ".mpg" ||
      ext == ".mpeg" || ext == ".3gp")
    return "video";
  if (ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".webp" ||
      ext == ".bmp" || ext == ".gif" || ext == ".tif" || ext == ".tiff" ||
      ext == ".heic")
    return "image";
  if (ext == ".mp3" || ext == ".wav" || ext == ".flac" || ext == ".ogg" ||
      ext == ".m4a" || ext == ".opus")
    return "audio";
  if (ext == ".pdf" || ext == ".docx" || ext == ".txt" || ext == ".md" ||
      ext == ".csv" || ext == ".xlsx" || ext == ".pptx")
    return "document";
  if (ext == ".zip" || ext == ".rar" || ext == ".7z" || ext == ".tar" ||
      ext == ".gz")
    return "archive";
  return "other";
}

bool ReadMeta(const fs::path& native, FileMeta& out, std::string& err) {
  std::error_code ec;
  fs::file_status st = fs::symlink_status(native, ec);
  if (ec) {
    err = ec.message();
    return false;
  }
  if (!fs::is_regular_file(st)) {
    err = "not a regular file";
    return false;
  }
  out.path = fsutil::PathToUtf8(native.lexically_normal());
  fs::path p(native.filename());
  out.filename = fsutil::PathToUtf8(p);
  std::string ext = fsutil::PathToUtf8(native.extension());
  for (auto& c : ext) c = (char)tolower((unsigned char)c);
  out.extension = ext;
  out.file_type = ClassifyType(ext);
  out.size = (int64_t)fs::file_size(native, ec);
  if (ec) {
    err = ec.message();
    return false;
  }
  auto ft = fs::last_write_time(native, ec);
  if (ec) {
    err = ec.message();
    return false;
  }
  out.mtime_ns =
      std::chrono::duration_cast<std::chrono::nanoseconds>(ft.time_since_epoch()).count();
#ifdef _WIN32
  HANDLE h = CreateFileW(native.c_str(), 0,
                         FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                         nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, nullptr);
  if (h != INVALID_HANDLE_VALUE) {
    BY_HANDLE_FILE_INFORMATION info{};
    if (GetFileInformationByHandle(h, &info)) {
      out.volume_serial = info.dwVolumeSerialNumber;
      out.file_index =
          (uint64_t(info.nFileIndexHigh) << 32) | info.nFileIndexLow;
    }
    CloseHandle(h);
  }
#else
  (void)0;
#endif
  return true;
}

int SuggestedWorkers(const std::string& root) {
  // TODO(benchmark): measure storage profile (HDD/SSD/NVMe) and tune.
  // Conservative default: traversal is single-threaded; hashing pool small.
  unsigned n = std::thread::hardware_concurrency();
  if (n == 0) n = 4;
  (void)root;
  return (int)std::min<unsigned>(n, 8);
}

Scanner::Scanner(db::Database& db, Options opts) : db_(db), opts_(std::move(opts)) {}

bool Scanner::run(const std::atomic<bool>& cancel, const std::atomic<bool>& paused,
                  ProgressCb on_progress, ErrorCb on_error, std::string& err) {
  std::error_code ec;
  // Normalize root once (native side), keep UTF-8 generic form for DB.
  fs::path root_native = fsutil::PathFromUtf8(opts_.root).lexically_normal();
  opts_.root = fsutil::PathToUtf8(root_native);
  if (!fs::is_directory(root_native, ec) || ec) {
    err = "root not a directory: " + opts_.root;
    return false;
  }
  Progress pr;
  int64_t session = db_.begin_session("scan", opts_.root);
  // Airtight gone-detection: cutoff = previous max stamp; seen files stamped
  // strictly above it. Immune to coarse clock granularity.
  std::string prefix = opts_.root;
  if (!prefix.empty() && prefix.back() != '/') prefix += '/';
  const int64_t cutoff = db_.max_last_seen(prefix);
  const int64_t stamp = (std::max)(db::NowMs(), cutoff + 1);
  auto last_report = std::chrono::steady_clock::now();
  int pending = 0;
  std::string tx_err;
  db_.exec("BEGIN", tx_err);

  auto flush = [&] {
    std::string e;
    db_.exec("COMMIT", e);
    db_.exec("BEGIN", e);
    pending = 0;
  };

  fs::recursive_directory_iterator it(root_native,
                                      fs::directory_options::skip_permission_denied, ec);
  fs::recursive_directory_iterator end;
  if (ec) {
    err = ec.message();
    return false;
  }
  for (; it != end; it.increment(ec)) {
    if (cancel.load()) break;
    while (paused.load() && !cancel.load()) std::this_thread::sleep_for(std::chrono::milliseconds(50));
    if (ec) {
      pr.errors++;
      // NB: it->path() may be unusable here; log generically.
      db_.log_error("scan", opts_.root, ec.message());
      if (on_error) on_error(opts_.root, ec.message());
      ec.clear();
      continue;
    }
    const fs::directory_entry& e = *it;
    std::error_code t2;
    if (e.is_directory(t2)) {
      // Compare directory names on the WIDE side (no narrow conversion).
      std::wstring wname = e.path().filename().wstring();
      std::string aname;
      aname.reserve(wname.size());
      for (wchar_t c : wname) aname += (c < 0x80) ? (char)c : '?';
      bool skip = false;
      for (const auto& s : opts_.skip_dir_names) {
        if (_stricmp(aname.c_str(), s.c_str()) == 0) {
          skip = true;
          break;
        }
      }
      if (skip) it.disable_recursion_pending();
      continue;
    }
    if (t2) continue;
    if (!opts_.follow_symlinks && e.is_symlink(t2)) continue;

    // UTF-8 generic path for DB/callbacks; native path for fs calls.
    const fs::path native = e.path();
    const std::string p = fsutil::PathToUtf8(native.lexically_normal());
    pr.seen++;
    pr.current = p;
    FileMeta m;
    std::string merr;
    if (!ReadMeta(native, m, merr)) {
      pr.errors++;
      db_.log_error("scan", p, merr);
      if (on_error) on_error(p, merr);
      continue;
    }
    pr.bytes_seen += (uint64_t)m.size;
    db::FileRow row;
    row.path = m.path;
    row.filename = m.filename;
    row.extension = m.extension;
    row.size = m.size;
    row.mtime_ns = m.mtime_ns;
    row.volume_serial = m.volume_serial;
    row.file_index = m.file_index;
    row.file_type = m.file_type;
    row.last_seen_ms = stamp;
    if (auto old = db_.find_by_path(p)) {
      bool same = old->size == m.size && old->mtime_ns == m.mtime_ns &&
                  (old->file_index == 0 || old->file_index == m.file_index ||
                   m.file_index == 0);
      if (same) {
        pr.unchanged++;  // SKIP downstream work
        row = *old;
        row.scan_status = "indexed";
        row.last_seen_ms = stamp;
      } else {
        pr.changed++;  // RESCAN
        row.scan_status = "changed";
        row.hash_status = "pending";
        row.ai_status = "pending";
        row.sha256.clear();
      }
    } else {
      pr.fresh++;  // PROCESS
      row.scan_status = "new";
    }
    std::string uerr;
    if (!db_.upsert_file(row, uerr)) {
      pr.errors++;
      db_.log_error("scan", p, uerr);
      if (on_error) on_error(p, uerr);
    }
    if (++pending >= opts_.commit_batch) flush();
    auto now = std::chrono::steady_clock::now();
    if (now - last_report > std::chrono::milliseconds(250)) {
      last_report = now;
      if (on_progress) on_progress(pr);
    }
  }
  {
    std::string e;
    db_.exec("COMMIT", e);
  }
  int64_t gone = 0;
  {
    std::string e;
    db_.mark_gone_before(cutoff, prefix, gone, e);
  }
  if (on_progress) on_progress(pr);
  char summary[256];
  snprintf(summary, sizeof(summary), "seen=%llu new=%llu changed=%llu skip=%llu err=%llu",
           pr.seen, pr.fresh, pr.changed, pr.unchanged, pr.errors);
  if (session > 0) {
    std::string e;
    db_.end_session(session, summary, e);
  }
  if (cancel.load()) spdlog::info("scan cancelled: {}", summary);
  return true;
}

}  // namespace aiorg::scanner
