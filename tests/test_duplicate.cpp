// Duplicate engine tests: grouping, persistence, approved move, min-size, jobs.
#include <atomic>
#include <filesystem>
#include <fstream>

#include "core/database/database.h"
#include "core/duplicate/duplicate.h"
#include "core/scanner/scanner.h"
#include "gtest/gtest.h"

namespace fs = std::filesystem;
using aiorg::db::Database;

namespace {
std::string Tmp(const std::string& name) {
  fs::path p = fs::temp_directory_path() / ("aiorg_produp_" + name);
  fs::remove_all(p);
  fs::remove_all(fs::path(p.string() + "_idx"));
  fs::create_directories(p);
  fs::create_directories(fs::path(p.string() + "_idx"));
  return p.lexically_normal().generic_string();
}
std::string DbPath(const std::string& dir) { return dir + "_idx/t.db"; }
void Write(const std::string& p, const std::string& data) {
  std::ofstream f(p, std::ios::binary);
  f << data;
}
void ScanInto(Database& db, const std::string& root) {
  aiorg::scanner::Options opts;
  opts.root = root;
  aiorg::scanner::Scanner sc(db, opts);
  std::atomic<bool> c{false}, q{false};
  std::string err;
  ASSERT_TRUE(sc.run(c, q, nullptr, nullptr, err)) << err;
}
void Cleanup(const std::string& dir) {
  fs::remove_all(dir);
  fs::remove_all(dir + "_idx");
}
}  // namespace

TEST(Duplicate, GroupsExactAndSplitsSameSize) {
  auto dir = Tmp("group");
  Write(dir + "/a1.bin", "SAMA-PERSIS-0123456789");
  Write(dir + "/a2.bin", "SAMA-PERSIS-0123456789");
  Write(dir + "/solo.bin", "unik-unik-unik-1234567");
  // same size (4B) as each other, different content -> must NOT group.
  Write(dir + "/c1.bin", "ABCD");
  Write(dir + "/c2.bin", "WXYZ");
  {
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    ScanInto(db, dir);

    aiorg::duplicate::Options opts;
    opts.root = dir;
    std::atomic<bool> cancel{false};
    auto groups =
        aiorg::duplicate::FindDuplicates(db, opts, cancel, nullptr, err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_EQ(groups.size(), 1u);
    EXPECT_EQ(groups[0].paths.size(), 2u);
    EXPECT_FALSE(groups[0].sha256.empty());

    // persisted: ListActiveGroups finds it too.
    auto listed = aiorg::duplicate::ListActiveGroups(db, dir, err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_EQ(listed.size(), 1u);
    EXPECT_EQ(listed[0].id, groups[0].id);
  }
  Cleanup(dir);
}

TEST(Duplicate, MinSizeFilters) {
  auto dir = Tmp("minsize");
  Write(dir + "/a1.bin", "xx");
  Write(dir + "/a2.bin", "xx");
  {
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    ScanInto(db, dir);
    aiorg::duplicate::Options opts;
    opts.root = dir;
    opts.min_size = 100;
    std::atomic<bool> cancel{false};
    auto groups =
        aiorg::duplicate::FindDuplicates(db, opts, cancel, nullptr, err);
    ASSERT_TRUE(err.empty()) << err;
    EXPECT_TRUE(groups.empty());
  }
  Cleanup(dir);
}

TEST(Duplicate, ApproveMoveKeepsOneAndLogs) {
  auto dir = Tmp("move");
  fs::create_directories(dir + "/karantina");
  Write(dir + "/k1.bin", "DATA-DUPLIKAT-1234567890");
  Write(dir + "/k2.bin", "DATA-DUPLIKAT-1234567890");
  {
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    ScanInto(db, dir);
    aiorg::duplicate::Options opts;
    opts.root = dir;
    std::atomic<bool> cancel{false};
    auto groups =
        aiorg::duplicate::FindDuplicates(db, opts, cancel, nullptr, err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_EQ(groups.size(), 1u);
    std::string keep = groups[0].paths[0];
    auto moved = aiorg::duplicate::ApproveMove(db, groups[0].id, keep,
                                              dir + "/karantina", err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_EQ(moved.size(), 1u);
    EXPECT_TRUE(fs::exists(keep));
    EXPECT_TRUE(fs::exists(moved[0]));
    // group no longer active (1 member left).
    auto listed = aiorg::duplicate::ListActiveGroups(db, dir, err);
    EXPECT_TRUE(listed.empty());
    // stats reflect history.
    auto st = db.Stats("");
    EXPECT_EQ(st.dup_groups, 0);
  }
  Cleanup(dir);
}

TEST(Duplicate, JobsQueue) {
  auto dir = Tmp("jobs");
  {
    Database db(DbPath(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    int64_t id = db.EnqueueJob("scan", "{\"root\":\"D:/x\"}");
    EXPECT_GT(id, 0);
    aiorg::db::Job j;
    ASSERT_TRUE(db.ClaimJob(j, err)) << err;
    EXPECT_EQ(j.id, id);
    EXPECT_EQ(j.status, "running");
    EXPECT_TRUE(db.FinishJob(id, "done", "ok", err)) << err;
    auto st = db.Stats("");
    EXPECT_EQ(st.pending_jobs, 0);
    EXPECT_TRUE(db.RecordBehavior("scan", "D:/x", "test"));
    auto beh = db.BehaviorSummary(5);
    ASSERT_EQ(beh.size(), 1u);
    EXPECT_EQ(beh[0].first, "scan");
  }
  Cleanup(dir);
}
