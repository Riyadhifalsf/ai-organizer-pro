// v4 tests: audit_log, proposals (propose/preview/approve), job pause/resume,
// checkpoints, integrity check, schema version.
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
std::string Tmp4(const std::string& name) {
  fs::path p = fs::temp_directory_path() / ("aiorg_prov4_" + name);
  fs::remove_all(p);
  fs::remove_all(fs::path(p.string() + "_idx"));
  fs::create_directories(p);
  fs::create_directories(fs::path(p.string() + "_idx"));
  return p.lexically_normal().generic_string();
}
std::string DbPath4(const std::string& dir) { return dir + "_idx/t.db"; }
void Write4(const std::string& p, const std::string& data) {
  std::ofstream f(p, std::ios::binary);
  f << data;
}
void Cleanup4(const std::string& dir) {
  fs::remove_all(dir);
  fs::remove_all(dir + "_idx");
}
}  // namespace

TEST(DbV4, SchemaVersionAndIntegrity) {
  auto dir = Tmp4("schema");
  {
    Database db(DbPath4(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    EXPECT_EQ(db.user_version(), aiorg::db::kSchemaVersion);
    EXPECT_EQ(db.user_version(), 4);
    EXPECT_EQ(db.IntegrityCheck(), "ok");
    EXPECT_FALSE(db.JournalMode().empty());
  }
  Cleanup4(dir);
}

TEST(DbV4, AuditRoundtrip) {
  auto dir = Tmp4("audit");
  {
    Database db(DbPath4(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    EXPECT_TRUE(db.Audit("cli", "scan", "D:/x", "", "ok", "files=3"));
    EXPECT_TRUE(db.Audit("gui", "move", "D:/x/a", "D:/q/a", "ok", "1 moved"));
    auto rows = db.ListAudit("", 10, err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_EQ(rows.size(), 2u);
    EXPECT_EQ(rows[0].action, "move");  // DESC: terbaru dulu
    EXPECT_EQ(rows[0].actor, "gui");
    auto filt = db.ListAudit("scan", 10, err);
    ASSERT_EQ(filt.size(), 1u);
    EXPECT_EQ(filt[0].detail, "files=3");
  }
  Cleanup4(dir);
}

TEST(DbV4, SaveDuplicateGroupConflictReturnsStableId) {
  // Regresi: UPSERT + last_insert_rowid basi pernah membuat gid salah
  // (rowid tabel lain) -> FK fail / korupsi diam-diam. Simulasi interleaving
  // insert tabel lain (spt hash_store oleh worker) di antara dua save.
  auto dir = Tmp4("gidstable");
  {
    Database db(DbPath4(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    int64_t g1 = db.SaveDuplicateGroup(10, "abc", {"D:/a", "D:/b"}, err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_GT(g1, 0);
    // insert tabel lain di antara (meniru hash_store): last_insert_rowid berubah
    int64_t jid = db.EnqueueJob("scan", "{}");
    ASSERT_GT(jid, 0);
    int64_t g2 = db.SaveDuplicateGroup(10, "abc", {"D:/a", "D:/b"}, err);
    ASSERT_TRUE(err.empty()) << err;
    EXPECT_EQ(g1, g2);  // jalur konflik HARUS mengembalikan id yang sama
    auto all = db.ListDuplicateGroups("", err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_EQ(all.size(), 1u);
    EXPECT_EQ(all[0].paths.size(), 2u);
  }
  Cleanup4(dir);
}

TEST(DbV4, ProposalFlowExecutesVerifiedMove) {
  auto dir = Tmp4("proposal");
  Write4(dir + "/k1.bin", "DATA-DUPLIKAT-1234567890");
  Write4(dir + "/k2.bin", "DATA-DUPLIKAT-1234567890");
  fs::create_directories(dir + "/karantina");
  {
    Database db(DbPath4(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    aiorg::scanner::Options sopts;
    sopts.root = dir;
    aiorg::scanner::Scanner sc(db, sopts);
    std::atomic<bool> c{false}, q{false};
    ASSERT_TRUE(sc.run(c, q, nullptr, nullptr, err)) << err;

    aiorg::duplicate::Options opts;
    opts.root = dir;
    auto groups = aiorg::duplicate::FindDuplicates(db, opts, c, nullptr, err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_EQ(groups.size(), 1u);

    // propose: belum ada yang pindah.
    std::string batch = aiorg::duplicate::ProposeFromGroup(
        db, groups[0].id, groups[0].paths[0], dir + "/karantina", "", err);
    ASSERT_TRUE(err.empty()) << err;
    EXPECT_FALSE(batch.empty());
    EXPECT_TRUE(fs::exists(dir + "/k1.bin"));
    EXPECT_TRUE(fs::exists(dir + "/k2.bin"));

    // preview: 1 item pending dengan alasan.
    auto items = db.BatchProposals(batch, err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_EQ(items.size(), 1u);
    EXPECT_EQ(items[0].status, "pending");
    EXPECT_FALSE(items[0].reasons.empty());

    // approve: pindah terverifikasi + audit.
    EXPECT_TRUE(db.Audit("cli", "proposal", groups[0].paths[0],
                         dir + "/karantina", "ok", "batch=" + batch));
    auto moved = aiorg::duplicate::ApproveBatch(db, batch, err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_EQ(moved.size(), 1u);
    EXPECT_TRUE(fs::exists(groups[0].paths[0]));  // keep tetap
    EXPECT_TRUE(fs::exists(moved[0]));
    auto after = db.BatchProposals(batch, err);
    ASSERT_EQ(after[0].status, "done");
    auto audit = db.ListAudit("proposal", 5, err);
    EXPECT_EQ(audit.size(), 1u);
  }
  Cleanup4(dir);
}

TEST(DbV4, JobPauseResumeCancelAndCheckpoint) {
  auto dir = Tmp4("jobs");
  {
    Database db(DbPath4(dir));
    std::string err;
    ASSERT_TRUE(db.open(err)) << err;
    int64_t id = db.EnqueueJob("scan", "{}");
    ASSERT_GT(id, 0);
    // pause dari pending, resume ke pending, cancel final.
    EXPECT_TRUE(db.SetJobStatus(id, "paused", err)) << err;
    EXPECT_FALSE(db.SetJobStatus(id, "paused", err));  // paused->paused ditolak
    EXPECT_TRUE(db.SetJobStatus(id, "pending", err)) << err;  // resume
    EXPECT_TRUE(db.SaveCheckpoint(id, "{\"done\":10}"));
    auto cp = db.LoadCheckpoint(id);
    ASSERT_TRUE(cp.has_value());
    EXPECT_EQ(*cp, "{\"done\":10}");
    auto jobs = db.ListJobs("", 10, err);
    ASSERT_TRUE(err.empty()) << err;
    ASSERT_EQ(jobs.size(), 1u);
    EXPECT_EQ(jobs[0].status, "pending");
    EXPECT_TRUE(db.SetJobStatus(id, "cancelled", err)) << err;
    auto jobs2 = db.ListJobs("cancelled", 10, err);
    ASSERT_EQ(jobs2.size(), 1u);
  }
  Cleanup4(dir);
}
