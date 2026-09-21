// Hash engine tests: known vectors, staging, cache, pipeline, cancel.
#include <atomic>
#include <filesystem>
#include <fstream>

#include "core/database/database.h"
#include "core/hashing/hash_cache.h"
#include "core/hashing/pipeline.h"
#include "core/hashing/sha256.h"
#include "gtest/gtest.h"

namespace fs = std::filesystem;
using aiorg::db::Database;
using aiorg::hash::Stage;

namespace {
std::string Tmp(const std::string& name) {
  fs::path p = fs::temp_directory_path() / ("aiorg_h_" + name);
  fs::remove_all(p);
  fs::create_directories(p);
  fs::create_directories(fs::path(p.string() + "_idx"));
  return p.lexically_normal().generic_string();
}
void Write(const std::string& p, const std::string& data) {
  std::ofstream f(p, std::ios::binary);
  f << data;
}
}  // namespace

TEST(Sha256, KnownVectors) {
  auto dir = Tmp("vec");
  Write(dir + "/empty", "");
  Write(dir + "/abc", "abc");
  auto e = aiorg::hash::FullHash(dir + "/empty");
  ASSERT_TRUE(e.ok) << e.error;
  EXPECT_EQ(e.hex, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  auto a = aiorg::hash::FullHash(dir + "/abc");
  ASSERT_TRUE(a.ok) << a.error;
  EXPECT_EQ(a.hex, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  fs::remove_all(dir);
}

TEST(Sha256, StagingLimitsBytes) {
  auto dir = Tmp("stage");
  std::string big(3 * 1024 * 1024, 'z');
  Write(dir + "/big.bin", big);
  std::string p = dir + "/big.bin";
  auto q = aiorg::hash::QuickHash(p);
  auto m = aiorg::hash::PartialHash(p);
  auto f = aiorg::hash::FullHash(p);
  ASSERT_TRUE(q.ok && m.ok && f.ok);
  EXPECT_EQ(q.bytes_read, 64u * 1024u);
  EXPECT_EQ(m.bytes_read, 1024u * 1024u);
  EXPECT_EQ(f.bytes_read, big.size());
  // quick of big == full of its 64KiB prefix
  Write(dir + "/prefix", big.substr(0, 64 * 1024));
  auto fp = aiorg::hash::FullHash(dir + "/prefix");
  EXPECT_EQ(q.hex, fp.hex);
  fs::remove_all(dir);
}

TEST(HashCache, HitAndInvalidate) {
  auto dir = Tmp("cache");
  Write(dir + "/a.txt", "data-1");
  Database db(dir + "_idx/t.db");
  std::string err;
  ASSERT_TRUE(db.open(err)) << err;
  auto st = fs::last_write_time(dir + "/a.txt");
  int64_t mtime = std::chrono::duration_cast<std::chrono::nanoseconds>(
                      st.time_since_epoch())
                      .count();
  EXPECT_FALSE(aiorg::hash::Lookup(db, dir + "/a.txt", 6, mtime, Stage::kFull).has_value());
  EXPECT_TRUE(aiorg::hash::Store(db, dir + "/a.txt", 6, mtime, Stage::kFull, "deadbeef"));
  auto hit = aiorg::hash::Lookup(db, dir + "/a.txt", 6, mtime, Stage::kFull);
  ASSERT_TRUE(hit.has_value());
  EXPECT_EQ(*hit, "deadbeef");
  // changed mtime -> miss
  EXPECT_FALSE(aiorg::hash::Lookup(db, dir + "/a.txt", 6, mtime + 1, Stage::kFull).has_value());
  fs::remove_all(dir);
}

TEST(Pipeline, GroupsAndSkipsCache) {
  auto dir = Tmp("pipe");
  Write(dir + "/a.txt", "same-content");
  Write(dir + "/b.txt", "same-content");
  Write(dir + "/c.txt", "different!!");
  Database db(dir + "_idx/t.db");
  std::string err;
  ASSERT_TRUE(db.open(err)) << err;
  auto meta = [&](const std::string& p) {
    aiorg::hash::Target t;
    t.path = p;
    t.size = (int64_t)fs::file_size(p);
    auto ft = fs::last_write_time(p);
    t.mtime_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                     ft.time_since_epoch())
                     .count();
    return t;
  };
  std::vector<aiorg::hash::Target> ts = {meta(dir + "/a.txt"), meta(dir + "/b.txt"),
                                         meta(dir + "/c.txt")};
  std::atomic<bool> cancel{false};
  aiorg::hash::Stats st1, st2;
  auto o1 = aiorg::hash::HashFiles(db, ts, Stage::kFull, 2, cancel, nullptr, st1);
  ASSERT_EQ(o1.size(), 3u);
  EXPECT_TRUE(o1[0].error.empty());
  EXPECT_EQ(o1[0].full, o1[1].full);
  EXPECT_NE(o1[0].full, o1[2].full);
  EXPECT_EQ(st1.full_new, 3u);
  // rerun: everything cached, zero bytes read
  auto o2 = aiorg::hash::HashFiles(db, ts, Stage::kFull, 2, cancel, nullptr, st2);
  EXPECT_EQ(o2[0].full, o1[0].full);
  EXPECT_EQ(st2.full_hit, 3u);
  EXPECT_EQ(st2.bytes_read, 0u);
  fs::remove_all(dir);
}

TEST(Pipeline, CancelFast) {
  auto dir = Tmp("cancel");
  for (int i = 0; i < 50; i++) Write(dir + "/f" + std::to_string(i), std::string(10000, 'q'));
  Database db(dir + "_idx/t.db");
  std::string err;
  ASSERT_TRUE(db.open(err)) << err;
  std::vector<aiorg::hash::Target> ts;
  for (int i = 0; i < 50; i++) {
    std::string p = dir + "/f" + std::to_string(i);
    ts.push_back({p, 10000, 1});
  }
  std::atomic<bool> cancel{true};
  aiorg::hash::Stats st;
  auto o = aiorg::hash::HashFiles(db, ts, Stage::kFull, 4, cancel, nullptr, st);
  EXPECT_EQ(o.size(), 50u);  // shape preserved; workers exit immediately
  fs::remove_all(dir);
}
