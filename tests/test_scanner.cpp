// Scanner tests: fixtures, rescan-skip, change detection, cancel, gone.
#include <atomic>
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <thread>

#include "core/database/database.h"
#include "core/filesystem/utf8.h"
#include "core/scanner/scanner.h"
#include "gtest/gtest.h"

namespace fs = std::filesystem;
using aiorg::db::Database;
using aiorg::scanner::Options;
using aiorg::scanner::Progress;
using aiorg::scanner::Scanner;

namespace {
std::string TmpDir(const std::string& name) {
  fs::path p = fs::temp_directory_path() / ("aiorg_" + name);
  fs::remove_all(p);
  fs::remove_all(fs::path(p.string() + "_idx"));
  fs::create_directories(p);
  fs::create_directories(fs::path(p.string() + "_idx"));  // DB lives outside scan root
  return p.lexically_normal().generic_string();
}
std::string DbPath(const std::string& dir) { return dir + "_idx/t.db"; }
void Write(const std::string& p, const std::string& data) {
  std::ofstream f(p, std::ios::binary);
  f << data;
}
// NB: db dikonstruksi di dalam scope test; RunScan tidak menyimpan referensi.
int RunScan(Database& db, const std::string& root, Progress* out) {
  Options o;
  o.root = root;
  Scanner s(db, o);
  std::atomic<bool> cancel{false}, paused{false};
  std::string err;
  Progress pr;
  bool ok = s.run(
      cancel, paused, [&](const Progress& p) { pr = p; }, nullptr, err);
  EXPECT_TRUE(ok) << err;
  if (out) *out = pr;
  return ok ? 0 : 1;
}
}  // namespace

TEST(Scanner, FreshThenSkip) {
  auto dir = TmpDir("fresh");
  {
    Write(dir + "/a.txt", "hello");
    fs::create_directories(dir + "/sub");
    Write(dir + "/sub/b.bin", std::string(1000, 'x'));
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    Progress p1, p2;
    ASSERT_EQ(RunScan(db, dir, &p1), 0);
    EXPECT_EQ(p1.fresh, 2u);
    ASSERT_EQ(RunScan(db, dir, &p2), 0);
    EXPECT_EQ(p2.unchanged, p1.seen);
    EXPECT_EQ(p2.fresh, 0u);
    EXPECT_EQ(p2.changed, 0u);
  }
  fs::remove_all(dir);
}

TEST(Scanner, DetectsChange) {
  auto dir = TmpDir("change");
  {
    Write(dir + "/a.txt", "v1");
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    ASSERT_EQ(RunScan(db, dir, nullptr), 0);
    std::this_thread::sleep_for(std::chrono::milliseconds(30));
    Write(dir + "/a.txt", "v2-longer");
    Progress p;
    ASSERT_EQ(RunScan(db, dir, &p), 0);
    EXPECT_EQ(p.changed, 1u);
  }
  fs::remove_all(dir);
}

TEST(Scanner, MarksGone) {
  auto dir = TmpDir("gone");
  {
    Write(dir + "/a.txt", "x");
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    ASSERT_EQ(RunScan(db, dir, nullptr), 0);
    fs::remove(dir + "/a.txt");
    Progress p2;
    ASSERT_EQ(RunScan(db, dir, &p2), 0);
    EXPECT_EQ(p2.seen, 0u);
    auto row = db.find_by_path(dir + "/a.txt");
    ASSERT_TRUE(row.has_value());
    EXPECT_EQ(row->scan_status, "gone");
  }
  fs::remove_all(dir);
}

TEST(Scanner, PreCancelledImmediately) {
  auto dir = TmpDir("cancel");
  Write(dir + "/a.txt", "x");
  {
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    Options o;
    o.root = dir;
    Scanner s(db, o);
    std::atomic<bool> cancel{true}, paused{false};
    Progress pr;
    bool ok = s.run(
        cancel, paused, [&](const Progress& p) { pr = p; }, nullptr, err);
    EXPECT_TRUE(ok);
    EXPECT_EQ(pr.seen, 0u);
  }
  fs::remove_all(dir);
}

TEST(Scanner, SkipsConfiguredDirs) {
  auto dir = TmpDir("skip");
  {
    fs::create_directories(dir + "/$RECYCLE.BIN");
    Write(dir + "/$RECYCLE.BIN/junk.tmp", "x");
    Write(dir + "/ok.txt", "y");
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    Progress p;
    ASSERT_EQ(RunScan(db, dir, &p), 0);
    EXPECT_FALSE(db.find_by_path(dir + "/$RECYCLE.BIN/junk.tmp").has_value());
    EXPECT_TRUE(db.find_by_path(dir + "/ok.txt").has_value());
  }
  fs::remove_all(dir);
}

TEST(Database, MigrateAndSettings) {
  auto dir = TmpDir("db");
  {
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    EXPECT_EQ(db.user_version(), aiorg::db::kSchemaVersion);
    EXPECT_TRUE(db.set_setting("k", "v"));
    EXPECT_EQ(db.get_setting("k"), "v");
    EXPECT_TRUE(db.log_error("test", "p", "m"));
  }
  fs::remove_all(dir);
}

TEST(Scanner, NonAnsiFilenameNoCrash) {
  // Regression: MSVC narrow path conversion crashed (0xC0000409) on CJK names.
  auto dir = TmpDir("cjk");
  {
    std::wstring wname = L"[\u4e0d\u53ef\u601d\u8b70]_test_\u30ab\u30eb\u30c6(128k).m4a";
    fs::path fp = aiorg::fsutil::PathFromUtf8(dir) / wname;
    {
      std::ofstream f(fp, std::ios::binary);
      f << "audio-bytes";
    }
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    Progress p;
    ASSERT_EQ(RunScan(db, dir, &p), 0);
    EXPECT_EQ(p.fresh, 1u);
    EXPECT_EQ(p.errors, 0u);
    auto row = db.find_by_path(dir + "/" + aiorg::fsutil::ToUtf8(wname));
    ASSERT_TRUE(row.has_value());
    EXPECT_EQ(row->extension, ".m4a");
    EXPECT_EQ(row->file_type, "audio");
  }
  fs::remove_all(dir);
}
