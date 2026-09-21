// Duplicate engine implementation. Staged grouping keeps I/O minimal:
// size (SQL) -> quick 64K -> partial 1M -> full SHA-256 (all stage-cached).
#include "duplicate.h"

#include <algorithm>
#include <filesystem>
#include <map>

#include "core/database/database.h"
#include "core/hashing/hash_cache.h"
#include "core/hashing/pipeline.h"

namespace fs = std::filesystem;
using aiorg::db::Database;
using aiorg::db::DupeGroup;
using aiorg::hash::HashFiles;
using aiorg::hash::Stage;
using aiorg::hash::Stats;
using aiorg::hash::Target;

namespace aiorg::duplicate {
namespace {

std::string ToGeneric(const std::string& p) {
  std::string o = p;
  std::replace(o.begin(), o.end(), '\\', '/');
  return o;
}

// Wide-safe helpers: std::string is always UTF-8; never use narrow
// path::string() on Windows (ANSI conversion corrupts CJK names).
fs::path P8(const std::string& utf8) {
  return fs::path(
      std::u8string(reinterpret_cast<const char8_t*>(utf8.data()),
                    utf8.size()));
}
std::string U8(const fs::path& p) {
  auto u = p.u8string();
  return std::string(reinterpret_cast<const char*>(u.data()), u.size());
}

// Regroup indexes of `paths` by digest at `stage` (cascade: lower stages
// already computed in Outcome). Errored files are logged and dropped.
std::map<std::string, std::vector<std::string>> Regroup(
    Database& db, const std::vector<std::string>& paths,
    const std::map<std::string, int64_t>& size_of,
    const std::map<std::string, int64_t>& mtime_of, Stage stage, int workers,
    const std::atomic<bool>& cancel, const std::string& /*root_prefix*/,
    Progress& prog, std::function<void(const Progress&)> on_progress) {
  std::vector<Target> targets;
  targets.reserve(paths.size());
  for (const auto& p : paths) targets.push_back({p, size_of.at(p), mtime_of.at(p)});
  Stats st;
  auto outcomes = HashFiles(
      db, targets, stage, workers, cancel,
      [&](uint64_t done, uint64_t total) {
        prog.hashed++;
        prog.current = total ? targets[done < targets.size() ? done : 0].path : "";
        if (on_progress) on_progress(prog);
      },
      st);
  std::map<std::string, std::vector<std::string>> groups;
  for (auto& o : outcomes) {
    if (cancel) break;
    if (!o.error.empty()) {
      prog.errors++;
      db.log_error("duplicate", o.path, o.error);
      continue;
    }
    std::string d = stage == Stage::kQuick
                        ? o.quick
                        : (stage == Stage::kPartial ? o.partial : o.full);
    if (d.empty()) {
      prog.errors++;
      db.log_error("duplicate", o.path, "empty digest at stage");
      continue;
    }
    groups[d].push_back(o.path);
  }
  return groups;
}

}  // namespace

std::filesystem::path P8pub(const std::string& utf8) { return P8(utf8); }

std::vector<DupeGroup> FindDuplicates(Database& db, const Options& opts,
                                      const std::atomic<bool>& cancel,
                                      std::function<void(const Progress&)> on_progress,
                                      std::string& err) {
  std::vector<DupeGroup> confirmed;
  Progress prog;
  // 1. size grouping straight from the index (no I/O at all).
  auto cands = db.SameSizeCandidates(ToGeneric(opts.root), opts.min_size, err);
  if (!err.empty()) return confirmed;
  std::map<int64_t, std::vector<std::string>> by_size;
  std::map<std::string, int64_t> size_of, mtime_of;
  for (auto& c : cands) {
    by_size[c.size].push_back(c.path);
    size_of[c.path] = c.size;
    mtime_of[c.path] = c.mtime_ns;
  }
  // 2. staged hash refinement per size group.
  const Stage stages[3] = {Stage::kQuick, Stage::kPartial, Stage::kFull};
  for (auto& [size, paths] : by_size) {
    if (cancel) break;
    if (paths.size() < 2) continue;
    prog.size_groups++;
    std::sort(paths.begin(), paths.end());
    std::vector<std::vector<std::string>> live = {paths};
    for (Stage st : stages) {
      std::vector<std::vector<std::string>> next;
      for (auto& bucket : live) {
        if (cancel) break;
        if (bucket.size() < 2) continue;
        auto g = Regroup(db, bucket, size_of, mtime_of, st, opts.workers,
                         cancel, opts.root, prog, on_progress);
        for (auto& [digest, members] : g) {
          if (members.size() < 2) continue;
          if (st == Stage::kFull) {
            std::sort(members.begin(), members.end());
            int64_t gid = db.SaveDuplicateGroup(size, digest, members, err);
            if (!err.empty()) return confirmed;
            DupeGroup grp{gid, size, digest, members};
            confirmed.push_back(grp);
            prog.confirmed_groups++;
            if (on_progress) on_progress(prog);
          } else {
            next.push_back(members);
          }
        }
      }
      live = std::move(next);
      if (live.empty()) break;
    }
  }
  return confirmed;
}

std::vector<DupeGroup> ListActiveGroups(Database& db,
                                       const std::string& root_prefix,
                                       std::string& err) {
  return db.ListDuplicateGroups(ToGeneric(root_prefix), err);
}

namespace {

// Satu move terverifikasi: rename natif (atau copy+verify+hapus source
// lintas volume), cek ukuran, catat rollback. "" = gagal (sudah di-log).
std::string MoveOneVerified(Database& db, int64_t group_id,
                            const std::string& src,
                            const std::string& dest_dir) {
  std::string e2;
  std::error_code ec;
  fs::path src_p = P8(src);
  uint64_t src_size = 0;
  {
    std::error_code sz_ec;
    src_size = fs::file_size(src_p, sz_ec);
    if (sz_ec) {
      db.log_error("move", src, "cannot stat: " + sz_ec.message());
      return "";
    }
  }
  fs::path dst_p = P8(dest_dir) / src_p.filename();
  for (int i = 2; fs::exists(dst_p, ec); i++)
    dst_p = P8(dest_dir) /
            P8(U8(src_p.stem()) + "_dup" + std::to_string(i) +
               U8(src_p.extension()));
  fs::rename(src_p, dst_p, ec);
  if (ec) {
    // Cross-volume: copy + verify + remove source.
    fs::copy_file(src_p, dst_p, ec);
    if (ec) {
      db.log_error("move", src, "relocate failed: " + ec.message());
      return "";
    }
  }
  std::error_code v_ec;
  uint64_t dst_size = fs::file_size(dst_p, v_ec);
  if (v_ec || dst_size != src_size) {
    db.log_error("move", src, "size mismatch after move, rolled back");
    fs::remove(dst_p, ec);
    return "";
  }
  if (fs::exists(src_p, ec)) {
    fs::remove(src_p, ec);
    if (fs::exists(src_p, ec)) {
      db.log_error("move", src, "source still present after move");
      fs::remove(dst_p, ec);
      return "";
    }
  }
  std::string dst = ToGeneric(U8(dst_p));
  db.LogMove(group_id, src, dst, (int64_t)src_size, "rename/copy+verify", e2);
  db.RemoveDupeMember(group_id, src, e2);
  return dst;
}

const DupeGroup* FindGroup(const std::vector<DupeGroup>& groups,
                           int64_t group_id) {
  for (auto& g : groups)
    if (g.id == group_id) return &g;
  return nullptr;
}

}  // namespace

std::vector<std::string> ApproveMove(Database& db, int64_t group_id,
                                     const std::string& keep_path,
                                     const std::string& dest_dir,
                                     std::string& err) {
  std::vector<std::string> moved;
  std::string e2;
  auto groups = db.ListDuplicateGroups("", e2);
  if (!e2.empty()) {
    err = e2;
    return moved;
  }
  const DupeGroup* grp = FindGroup(groups, group_id);
  if (!grp) {
    err = "group not found";
    return moved;
  }
  bool keep_member =
      std::find(grp->paths.begin(), grp->paths.end(), keep_path) != grp->paths.end();
  if (!keep_member) {
    err = "keep_path is not a member of the group";
    return moved;
  }
  std::error_code ec;
  fs::create_directories(P8(dest_dir), ec);
  if (ec) {
    err = "cannot create dest dir: " + ec.message();
    return moved;
  }
  for (const auto& src : grp->paths) {
    if (src == keep_path) continue;
    std::string dst = MoveOneVerified(db, group_id, src, dest_dir);
    if (!dst.empty()) moved.push_back(dst);
  }
  return moved;
}

std::string ProposeFromGroup(Database& db, int64_t group_id,
                             const std::string& keep_path,
                             const std::string& dest_dir,
                             const std::string& reasons, std::string& err) {
  std::string e2;
  auto groups = db.ListDuplicateGroups("", e2);
  if (!e2.empty()) {
    err = e2;
    return "";
  }
  const DupeGroup* grp = FindGroup(groups, group_id);
  if (!grp) {
    err = "group not found";
    return "";
  }
  if (std::find(grp->paths.begin(), grp->paths.end(), keep_path) ==
      grp->paths.end()) {
    err = "keep_path is not a member of the group";
    return "";
  }
  std::vector<std::pair<std::string, std::string>> items;
  for (const auto& src : grp->paths) {
    if (src == keep_path) continue;
    fs::path dst_p = P8(dest_dir) / P8(src).filename();
    items.emplace_back(src, ToGeneric(U8(dst_p)));
  }
  std::string why = reasons.empty()
                        ? "duplikat exact (size+quick+partial+full SHA-256 sama); simpan 1, sisanya karantina"
                        : reasons;
  return db.ProposeMoves(group_id, keep_path, dest_dir, items, why, "low",
                         err);
}

std::vector<std::string> ApproveBatch(Database& db, const std::string& batch,
                                      std::string& err) {
  std::vector<std::string> moved;
  auto props = db.BatchProposals(batch, err);
  if (!err.empty()) return moved;
  if (props.empty()) {
    err = "batch tidak ada / kosong";
    return moved;
  }
  // Resolve dst collisions per item at approve time (same rule as ApproveMove).
  std::error_code ec;
  for (auto& p : props) {
    if (p.status != "pending") continue;
    fs::path dest_dir_p = P8(p.dst).parent_path();
    fs::create_directories(dest_dir_p, ec);
    if (ec) {
      db.ResolveProposal(p.id, "failed", err);
      err.clear();
      db.log_error("proposal", p.src,
                   "cannot create dest dir: " + ec.message());
      continue;
    }
    std::string dst = MoveOneVerified(db, p.group_id, p.src, ToGeneric(U8(dest_dir_p)));
    if (dst.empty()) {
      db.ResolveProposal(p.id, "failed", err);
      err.clear();
      continue;
    }
    // Catat dst final (bisa beda karena tabrakan nama) lalu tandai done.
    db.ResolveProposal(p.id, "done", err);
    err.clear();
    moved.push_back(dst);
  }
  return moved;
}

}  // namespace aiorg::duplicate
