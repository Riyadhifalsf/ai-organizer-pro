// app.js — GUI AIOrganizerPro (vanilla JS, tanpa framework / tanpa Python).
const $ = (id) => document.getElementById(id);
const STR = {
  id: { sub: "duplikat • broken • dokumen AI • database terpadu", dry: "Dry-run" },
  en: { sub: "duplicates • broken • doc AI • unified database", dry: "Dry-run" },
};
let lang = "id";
$("lang").onclick = () => {
  lang = lang === "id" ? "en" : "id";
  $("lang").textContent = lang === "id" ? "EN" : "ID";
  $("t-sub").textContent = STR[lang].sub;
  refreshHelp();
  loadActivity();
};
document.querySelectorAll("#tabs button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("#tabs button").forEach((x) => x.classList.remove("on"));
    document.querySelectorAll(".view").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    $("v-" + b.dataset.v).classList.add("on");
  };
});
const NATIVE = !!(window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke);
const invoke = (cmd, args) => window.__TAURI__.core.invoke(cmd, args || {});
// Transport ganda: aplikasi Windows native (Tauri invoke, tanpa server/port)
// atau website via server Node (fetch REST). Satu GUI untuk dua mode.
async function apiNative(m, p, b) {
  const qi = p.indexOf("?");
  const q = qi < 0 ? {} : Object.fromEntries(new URLSearchParams(p.slice(qi + 1)));
  if (p === "/api/health") { const v = await invoke("app_info"); return { ok: true, db: v.db, core: v.core_version }; }
  if (p === "/api/stats") return invoke("core_stats");
  if (p === "/api/recommend") return invoke("ai_recommend");
  if (p === "/api/docs" || p.startsWith("/api/docs?")) return invoke("docs_list", { limit: Number(q.limit || 200) });
  if (p === "/api/scan") return invoke("core_scan", { folder: b.folder });
  if (p === "/api/duplicates") return invoke("core_duplicates", { folder: b.folder, min_size: Number(b.minSize || 1) });
  if (p === "/api/move-approved") return invoke("core_move_approved", { group: Number(b.group), keep: b.keep, to: b.to });
  if (p === "/api/ai") { const r = await invoke("ai_engine", { argv: b.argv }); r.output = (r.output || "").slice(-8000); return r; }
  if (p === "/api/jobs/enqueue") return invoke("job_enqueue", { kind: b.kind || "scan", payload: b.payload || "" });
  if (p === "/api/jobs/claim") return invoke("job_claim");
  if (p === "/api/jobs/list" || p.startsWith("/api/jobs/list?")) return invoke("job_list", { status: q.status || "", limit: Number(q.limit || 50) });
  if (p === "/api/jobs/pause") return invoke("job_pause", { id: Number(b.id) });
  if (p === "/api/jobs/resume") return invoke("job_resume", { id: Number(b.id) });
  if (p === "/api/jobs/cancel") return invoke("job_cancel", { id: Number(b.id) });
  if (p === "/api/activity") return invoke("activity_list", { limit: Number(q.limit || 200) });
  if (p === "/api/activity/clear") return invoke("activity_clear");
  if (p === "/api/db-state" && m === "GET") return invoke("db_state");
  if (p === "/api/db-state") return invoke("db_set_enabled", { enabled: !!b.enabled });
  if (p === "/api/doctor" || p.startsWith("/api/doctor?")) return invoke("core_doctor", { root: q.root || "" });
  if (p === "/api/audit" || p.startsWith("/api/audit?")) return invoke("audit_list", { action: q.action || "", limit: Number(q.limit || 100) });
  if (p === "/api/proposals/propose") return invoke("prop_propose", { group: Number(b.group), keep: b.keep, to: b.to, reasons: b.reasons || "" });
  if (p === "/api/proposals/list" || p.startsWith("/api/proposals/list?")) return invoke("prop_list", { status: q.status || "pending" });
  if (p === "/api/proposals/preview" || p.startsWith("/api/proposals/preview?")) return invoke("prop_preview", { target: q.target || "" });
  if (p === "/api/proposals/approve") return invoke("prop_approve", { batch: b.batch });
  if (p === "/api/proposals/reject") return invoke("prop_reject", { target: b.batch || b.target });
  if (p === "/api/videos/list" || p.startsWith("/api/videos/list?")) return invoke("videos_list", { root: q.root || "", limit: Number(q.limit || 2000), kind: q.kind || "videos" });
  if (p === "/api/organize") return invoke("org_run", { kind: b.kind || "videos", folder: b.folder, files: b.files || [], dest: b.dest || "", content: b.content || [], copy: !!b.copy, dated: !!b.dated, junk: !!b.junk, prune: !!b.prune, limit: Number(b.limit || 0), apply: !!b.apply });
  if (p === "/api/activity/export") return invoke("activity_export");
  if (p === "/api/reports/get" || p.startsWith("/api/reports/get?")) return invoke("report_export", { name: q.name || "" });
  if (p === "/api/video/inspect") return invoke("video_inspect", { path: b.path || q.path || "" });
  if (p === "/api/video/open") return invoke("video_open", { path: b.path || "" });
  if (p === "/api/video/folder") return invoke("video_show_folder", { path: b.path || "" });
  if (p === "/api/video/rename") return invoke("video_rename", { path: b.path || "", newName: b.newName || "" });
  if (p === "/api/video/move") return invoke("video_move", { path: b.path || "", destination: b.destination || "" });
  if (p === "/api/video/quarantine") return invoke("video_quarantine", { path: b.path || "" });
  if (p === "/api/video/annotation") return invoke("video_save_annotation", { path: b.path || "", tags: b.tags || [], note: b.note || "" });
  throw new Error("endpoint tak dikenal: " + p);
}
const api = async (m, p, b) => {
  if (NATIVE) return apiNative(m, p, b || {});
  const r = await fetch(p, { method: m, headers: { "content-type": "application/json" }, body: b ? JSON.stringify(b) : undefined });
  return r.json();
};
// Unduh file: mode web pakai blob, mode native pakai export ke data/exports.
async function downloadExport(kind, name) {
  if (NATIVE) {
    const r = kind === "activity"
      ? await api("GET", "/api/activity/export")
      : await api("GET", "/api/reports/get?name=" + encodeURIComponent(name || ""));
    alert(r.ok ? (lang === "id" ? `Tersimpan di:\n${r.path}` : `Saved to:\n${r.path}`) : ("Gagal: " + (r.error || "")));
    return;
  }
  const url = kind === "activity" ? "/api/activity/export" : "/api/reports/get?name=" + encodeURIComponent(name || "");
  const a = document.createElement("a");
  a.href = url;
  a.download = name || "activity.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
const fmtBytes = (n) => n > 1e9 ? (n / 1e9).toFixed(2) + " GB" : n > 1e6 ? (n / 1e6).toFixed(1) + " MB" : n > 1e3 ? (n / 1e3).toFixed(1) + " KB" : n + " B";
const dryArg = () => ($("dry").checked ? ["--dry-run"] : []);
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const fmtTs = (ts) => { try { const d = new Date(ts); return d.toLocaleString(lang === "id" ? "id-ID" : "en-US", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" }); } catch { return ts; } };

// ---- panel video desktop ----
// Operasi file dilakukan oleh backend Tauri. Hapus selalu berarti karantina ke
// folder 99_To-Delete, sehingga file masih dapat dipulihkan.
let activeVideoPath = "", activeVideoTags = ["Event", "Pemandangan", "Danau", "2025", "05-01"];
let activeVideoNote = "Video ini diambil saat perjalanan ke danau pada tanggal 1 Mei 2025.\nKondisi cuaca cerah dan pemandangannya bagus.";
const videoDuration = (seconds) => {
  if (!Number.isFinite(seconds)) return "—";
  const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = Math.floor(seconds % 60);
  return h ? `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `00:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
};
function renderVideoAnnotation() {
  $("tag-list").innerHTML = activeVideoTags.map((tag, i) => `<span class="${i === 0 ? "purple" : ""}">${esc(tag)}</span>`).join("");
  $("note-text").innerHTML = esc(activeVideoNote).replace(/\n/g, "<br>");
}
function showVideoInPlayer(path) {
  const player = $("video-player"), scene = document.querySelector(".placeholder-scene");
  player.src = `file:///${path.replace(/\\/g, "/")}`;
  player.hidden = false;
  scene.hidden = true;
  player.onloadedmetadata = () => { $("video-duration").textContent = videoDuration(player.duration); };
  player.onerror = () => { player.hidden = true; scene.hidden = false; };
}
function setVideoAnalysis(r) {
  const probe = r.probe || {}, video = probe.video || {}, audio = probe.audio || {};
  $("video-resolution").textContent = video.width ? `${video.width} × ${video.height} (${video.height >= 1080 ? "FHD" : "HD"})` : "—";
  $("video-codec").textContent = video.codec || "—";
  $("audio-codec").textContent = audio.codec || "Tidak ada";
  $("video-fps").textContent = video.fps ? `${video.fps} fps` : "—";
  $("video-aspect").textContent = video.aspect || "—";
  $("check-health").textContent = probe.ok ? "Normal" : "Perlu diperiksa";
  $("check-metadata").textContent = probe.ok ? "Lengkap" : "Terbatas";
  $("check-size").textContent = fmtBytes(r.size);
  $("check-type").textContent = (r.extension || "video").toUpperCase();
  $("analysis-status").innerHTML = probe.ok ? "✓ <b>File normal</b>" : "! <b>Metadata tidak lengkap</b>";
  $("analysis-list").innerHTML = (probe.ok
    ? ["Stream video dapat dibaca", video.codec ? `Codec ${video.codec}` : "Codec tidak tersedia", audio.codec ? `Audio ${audio.codec}` : "Tanpa stream audio"]
    : [probe.error || "Tidak dapat membaca metadata", "Coba buka dengan player untuk memastikan file", "Periksa instalasi ffprobe bila masalah berlanjut"])
    .map((item) => `<li>${esc(item)}</li>`).join("");
}
async function loadVideo() {
  const path = $("video-path").value.trim();
  if (!path) return alert("Tempel path video lokal terlebih dahulu.");
  if (!NATIVE) return alert("Panel video aktif tersedia pada aplikasi desktop AIOrganizerPro.");
  try {
    const r = await api("POST", "/api/video/inspect", { path });
    activeVideoPath = r.path;
    $("video-path").value = r.path;
    $("video-title").textContent = r.name;
    $("video-name").textContent = r.name;
    $("video-size").textContent = fmtBytes(r.size);
    $("video-modified").textContent = r.modified || "—";
    $("video-duration").textContent = r.probe?.duration ? videoDuration(r.probe.duration) : "—";
    setVideoAnalysis(r);
    if (r.annotation) { activeVideoTags = r.annotation.tags || []; activeVideoNote = r.annotation.note || ""; }
    renderVideoAnnotation();
    showVideoInPlayer(r.path);
  } catch (e) { alert("Tidak dapat memuat video: " + (e.message || e)); }
}
function requireVideo() {
  if (!activeVideoPath) { alert("Muat video terlebih dahulu dengan memasukkan path lokalnya."); return false; }
  return true;
}
async function updateVideoPath(r) {
  if (r && r.path) { activeVideoPath = r.path; $("video-path").value = r.path; await loadVideo(); }
}
async function doVideoAction(action) {
  if (action === "load") return loadVideo();
  if (!requireVideo()) return;
  try {
    if (action === "open") await api("POST", "/api/video/open", { path: activeVideoPath });
    else if (action === "folder") await api("POST", "/api/video/folder", { path: activeVideoPath });
    else if (action === "rename") {
      const newName = prompt("Nama file baru (ekstensi boleh dikosongkan):", activeVideoPath.split(/[/\\]/).pop());
      if (!newName) return;
      await updateVideoPath(await api("POST", "/api/video/rename", { path: activeVideoPath, newName }));
    } else if (action === "move") {
      const destination = prompt("Folder tujuan:", activeVideoPath.replace(/[\\/][^\\/]+$/, ""));
      if (!destination) return;
      await updateVideoPath(await api("POST", "/api/video/move", { path: activeVideoPath, destination }));
    } else if (action === "delete") {
      if (!confirm("Pindahkan video ini ke folder 99_To-Delete? File tidak dihapus permanen.")) return;
      await updateVideoPath(await api("POST", "/api/video/quarantine", { path: activeVideoPath }));
    } else if (action === "tags") {
      const value = prompt("Tag, pisahkan dengan koma:", activeVideoTags.join(", "));
      if (value === null) return;
      activeVideoTags = value.split(",").map((tag) => tag.trim()).filter(Boolean);
      await api("POST", "/api/video/annotation", { path: activeVideoPath, tags: activeVideoTags, note: activeVideoNote }); renderVideoAnnotation();
    } else if (action === "note") {
      const value = prompt("Catatan video:", activeVideoNote);
      if (value === null) return;
      activeVideoNote = value;
      await api("POST", "/api/video/annotation", { path: activeVideoPath, tags: activeVideoTags, note: activeVideoNote }); renderVideoAnnotation();
    }
  } catch (e) { alert("Aksi video gagal: " + (e.message || e)); }
}
document.querySelectorAll("[data-video-action]").forEach((button) => { button.onclick = () => doVideoAction(button.dataset.videoAction); });
$("video-path").addEventListener("keydown", (event) => { if (event.key === "Enter") loadVideo(); });

// Teks bantuan per bagian (tombol ?). Ditampilkan saat diklik.
const HELP = {
  id: {
    rec: "Rekomendasi otomatis dari kebiasaanmu (behavior AI). Makin sering dipakai, makin pintar sarannya. Tidak ada data yang keluar dari PC ini.",
    jobs: "Antrean kerja latar. + Job = daftarkan tugas (mis. scan folder). Claim = ambil 1 tugas untuk dikerjakan worker/daemon. Status tersimpan di database.",
    scan: "Cara pakai: isi folder (mis. D:\\Foto) lalu ▶ Mulai. Scan hanya MEMBACA dan mencatat ke database (ukuran, waktu, identitas NTFS). Aman — tidak ada file yang diubah. Scan kedua dst. jauh lebih cepat karena file tak berubah di-skip.",
    ai: "Cara pakai: pilih mode, isi folder, lalu ▶ Jalan. video-broken butuh ffprobe; image-broken butuh Pillow; analyze membaca isi dokumen lalu menebak kategori. Centang Dry-run (atas) untuk simulasi tanpa mengubah file. karantina MEMINDAH duplikat — cek hasil dry-run dulu.",
    dup: "Cara pakai: isi folder lalu ▶ Cari. Sistem mengelompokkan file berukuran sama, lalu membandingkan hash bertahap (cepat→pasti). Tombol ✓ = pilih file yang DISIMPAN, sisanya dipindah ke folder karantina dengan catatan rollback.",
    doc: "Hasil analisis dokumen AI (kategori, confidence 0–1, saran nama). Confidence < 0.30 = jangan jadikan acuan rename. Klik Muat ulang setelah analyze. Ketik di kolom cari untuk filter.",
    db: "Satu file SQLite (mode WAL): index file, cache hash, grup duplikat, riwayat move, jobs, behavior, doc_index, proposals, audit. Lokasi file tampil di footer. Tombol Muat ulang menampilkan ringkasan JSON-nya.",
    dbswitch: "Saklar database. ON = semua hasil tersimpan di data/aiorganizer.db. OFF = mode efemeral :memory: — scan/duplikat tetap jalan tapi hasilnya hilang saat proses selesai. Cocok untuk coba-coba tanpa mengotori database. Pengaturan tersimpan di data/db.json.",
    audit: "Jejak audit tahan lama di database (beda dengan Log aktivitas yang berupa file). Mencatat aktor (cli/gui/daemon), aksi, hasil, dan detail. Tidak bisa diubah — hanya dibaca. Saring berdasarkan nama aksi.",
    prop: "Alur aman sesuai master doc: Usulkan (◔) → Pratinjau → Setujui/Tolak. Proposal hanya catatan di database; TIDAK ADA file yang pindah sebelum kamu tekan Setujui. Setiap eksekusi terverifikasi + rollback tercatat + masuk audit.",
    jobs: "Antrean kerja latar. + Job = daftarkan tugas (mis. scan folder). Claim = ambil 1 tugas untuk dikerjakan worker/daemon. Daftar = lihat semua + jeda/lanjut/batalkan. Status tersimpan di database.",
    act: "Semua aksimu tercatat otomatis di sini (tersimpan di data/activity.log, format JSONL). Berguna untuk audit: kapan scan/move/analyze dilakukan. Hapus log tidak menghapus data di database.",
    orgv: "Pilih 🎥 Video atau 📷 Foto dulu, lalu isi folder. Tujuan default = path yang sama (in-place); isi kolom Tujuan untuk path lain. Pilih file = centang file yang diproses (semua bila panel tak dibuka). Junk = pindahkan file non-media ke 99_To-Delete (TIDAK PERNAH hapus permanen). Hapus folder kosong = bersihkan sisa folder kosong. Centang Terapkan untuk eksekusi, default hanya Rencana.",
  },
  en: {
    rec: "Automatic recommendations from your habits (behavior AI). The more you use it, the smarter it gets. No data ever leaves this PC.",
    jobs: "Background work queue. + Job = register a task (e.g. scan a folder). Claim = take 1 task for a worker/daemon. Status is stored in the database.",
    scan: "How to use: enter a folder (e.g. D:\\Photos) then ▶ Start. Scan only READS and records into the database (size, time, NTFS identity). Safe — no file is modified. Later scans are much faster because unchanged files are skipped.",
    ai: "How to use: pick a mode, enter a folder, then ▶ Run. video-broken needs ffprobe; image-broken needs Pillow; analyze reads document contents and guesses categories. Tick Dry-run (top) to simulate without changing files. karantina MOVES duplicates — check the dry-run first.",
    dup: "How to use: enter a folder then ▶ Find. The system groups same-size files, then compares hashes in stages (fast→certain). The ✓ button = file to KEEP; the rest move to quarantine with a rollback record.",
    doc: "Document AI results (category, confidence 0–1, suggested name). Confidence < 0.30 = don't use for renaming. Click Reload after analyze. Type in the search box to filter.",
    db: "A single SQLite file (WAL mode): file index, hash cache, duplicate groups, move history, jobs, behavior, doc_index, proposals, audit. Path shown in the footer. Reload shows its JSON summary.",
    dbswitch: "Database switch. ON = all results persist in data/aiorganizer.db. OFF = ephemeral :memory: mode — scans/duplicates still run but results vanish when done. Good for experiments without dirtying the database. Stored in data/db.json.",
    audit: "Durable audit trail in the database (unlike the file-based Activity log). Records actor (cli/gui/daemon), action, result, detail. Immutable — read-only. Filter by action name.",
    prop: "Safe flow per master doc: Propose (◔) → Preview → Approve/Reject. Proposals are only database records; NO file moves until you press Approve. Every execution is verified + rollback-logged + audited.",
    jobs: "Background work queue. + Job = register a task (e.g. scan a folder). Claim = take 1 task for a worker/daemon. List = view all + pause/resume/cancel. Status is stored in the database.",
    act: "All your actions are logged here automatically (stored in data/activity.log, JSONL format). Useful for auditing when scans/moves/analyzes ran. Clearing the log does not delete database data.",
    orgv: "Pick 🎥 Video or 📷 Photo first, then enter the folder. Default destination = same path (in-place); fill Destination for another path. Pick files = check files to process (all if panel never opened). Junk = move non-media files to 99_To-Delete (NEVER permanently deleted). Prune = remove leftover empty folders. Tick Apply to execute, default is Plan only.",
  },
};
function refreshHelp() {
  document.querySelectorAll(".help-pop").forEach((el) => { if (!el.hidden) el.textContent = HELP[lang][el.dataset.for] || ""; });
}
function showHelp(b) {
  const card = b.closest(".card");
  const pop = card ? card.querySelector(".help-pop") : null;
  if (!pop) return;
  pop.dataset.for = b.dataset.h;
  pop.textContent = HELP[lang][b.dataset.h] || "";
  pop.hidden = false;
  b.classList.add("on");
}
function hideHelp(b) {
  const card = b.closest(".card");
  const pop = card ? card.querySelector(".help-pop") : null;
  if (!pop) return;
  pop.hidden = true;
  b.classList.remove("on");
}
document.querySelectorAll(".help-btn").forEach((b) => {
  // Tampilkan saat hover/fokus; klik tetap didukung untuk layar sentuh.
  b.addEventListener("mouseenter", () => showHelp(b));
  b.addEventListener("mouseleave", () => hideHelp(b));
  b.addEventListener("focus", () => showHelp(b));
  b.addEventListener("blur", () => hideHelp(b));
  b.onclick = () => {
    const card = b.closest(".card");
    const pop = card ? card.querySelector(".help-pop") : null;
    if (!pop) return;
    if (pop.hidden) showHelp(b); else hideHelp(b);
  };
});

async function health() {
  try {
    const h = await api("GET", "/api/health");
    $("health").textContent = h.ok ? "● online" : "● error";
    $("db-path").textContent = h.db || "";
  } catch { $("health").textContent = "● server mati?"; }
}
async function stats() {
  const s = await api("GET", "/api/stats");
  if (!s.ok) { $("stat-cards").innerHTML = `<div class="mut">DB kosong / core belum build. Jalankan Scan dulu.</div>`; $("db-out").textContent = JSON.stringify(s, null, 2); return; }
  const cards = [["Files", s.files], ["Duplikat grup", s.dup_groups], ["File duplikat", s.dup_files], ["Pending jobs", s.pending_jobs], ["Errors", s.errors], ["Sessions", s.sessions]];
  $("stat-cards").innerHTML = cards.map(([k, v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join("");
  $("db-out").textContent = JSON.stringify(s, null, 2);
  const r = await api("GET", "/api/recommend");
  $("recs").innerHTML = (r.recommendations || []).length
    ? r.recommendations.map((x) => `<div class="rec">${x.text}</div>`).join("")
    : `<span class="mut">Belum ada rekomendasi. Daemon + pemakaian rutin akan mengisi ini.</span>`;
}
$("scan-go").onclick = async () => {
  const folder = $("scan-folder").value.trim();
  if (!folder) return alert("Isi folder dulu");
  $("scan-out").textContent = "berjalan…";
  $("scan-out").textContent = JSON.stringify(await api("POST", "/api/scan", { folder }), null, 2);
  stats(); loadActivity();
};
$("org-go").onclick = async () => {
  const kind = $("org-kind").value;
  const folder = $("org-folder").value.trim() || (kind === "images" ? "D:\\results\\Images" : "D:\\results\\Videos");
  const apply = $("org-apply").checked;
  const body = {
    kind,
    folder, dest: $("org-dest").value.trim(),
    files: orgSel.size ? [...orgSel] : [],
    content: $("org-content").value.split(";").map((s) => s.trim()).filter((s) => s.includes("=>")),
    copy: $("org-copy").checked, dated: $("org-dated").checked,
    junk: $("org-junk").checked, prune: $("org-prune").checked,
    limit: Number($("org-limit").value) || 0, apply,
  };
  if (apply) {
    if (!confirm(lang === "id" ? `Terapkan penataan ke ${folder}? File akan DIPINDAH (terverifikasi).` : `Apply organization to ${folder}? Files will be MOVED (verified).`)) return;
  }
  $("org-go").disabled = true;
  $("org-out").textContent = "berjalan (baca metadata ExifTool)…";
  try {
    const r = await api("POST", "/api/organize", body);
    $("org-out").textContent = (r.output || r.error || JSON.stringify(r)).slice(0, 8000) + (r.report ? `\n\nLaporan: ${r.report}` : "");
    lastOrgReport = r.report || "";
    $("org-dl").disabled = !lastOrgReport;
  } finally { $("org-go").disabled = false; }
  stats(); loadActivity();
};
let lastOrgReport = "";
$("org-dl").onclick = async () => {
  if (!lastOrgReport) return;
  await downloadExport("report", lastOrgReport.split(/[/\\]/).pop());
};
let orgSel = new Set(), orgFiles = [], orgJunk = 0;
function renderOrgList() {
  const q = ($("org-q").value || "").toLowerCase();
  const rows = orgFiles.filter((f) => !q || f.rel.toLowerCase().includes(q));
  $("org-list").innerHTML = rows.slice(0, 500).map((f, i) =>
    `<label class="pick"><input type="checkbox" data-p="${esc(f.path)}"${orgSel.has(f.path) ? " checked" : ""}> <span>${esc(f.rel)}</span> <span class="mut">${fmtBytes(f.size)}</span></label>`).join("")
    + (rows.length > 500 ? `<div class="mut">… +${rows.length - 500} (saring untuk persempit)</div>` : "");
  $("org-list").querySelectorAll("input[data-p]").forEach((c) => {
    c.onchange = () => { c.checked ? orgSel.add(c.dataset.p) : orgSel.delete(c.dataset.p); updOrgCount(); };
  });
  updOrgCount();
}
function updOrgCount() {
  $("org-count").textContent = `${orgSel.size}/${orgFiles.length} dipilih` + (orgJunk ? ` • ${orgJunk} non-video` : "");
}
$("org-files").onclick = async () => {
  const kind = $("org-kind").value;
  const folder = $("org-folder").value.trim() || (kind === "images" ? "D:\\results\\Images" : "D:\\results\\Videos");
  $("org-sel").hidden = false;
  $("org-list").textContent = "memuat daftar…";
  try {
    const r = await api("GET", "/api/videos/list?root=" + encodeURIComponent(folder) + "&kind=" + kind);
    if (!r.ok) { $("org-list").textContent = "gagal: " + (r.error || ""); return; }
    orgFiles = r.videos || []; orgJunk = r.junk_count || 0;
    orgSel = new Set(orgFiles.map((f) => f.path));
    renderOrgList();
  } catch (e) { $("org-list").textContent = "gagal: " + (e.message || e); }
};
$("org-q").oninput = renderOrgList;
$("org-all").onclick = () => { orgFiles.forEach((f) => orgSel.add(f.path)); renderOrgList(); };
$("org-none").onclick = () => { orgSel.clear(); renderOrgList(); };
$("ai-go").onclick = async () => {
  const folder = $("ai-folder").value.trim();
  if (!folder) return alert("Isi folder dulu");
  const mode = $("ai-mode").value;
  const argv = [mode, folder, ...dryArg()];
  if ((mode === "analyze" || mode === "yolo-classify") && Number($("ai-limit").value) > 0) argv.push("--limit", $("ai-limit").value);
  if (mode === "yolo-classify" && !$("dry").checked) argv.push("--apply");
  $("ai-out").textContent = "berjalan (LLM bisa menit)…";
  const r = await api("POST", "/api/ai", { argv });
  $("ai-out").textContent = (r.output || r.error || JSON.stringify(r)).slice(0, 8000) + (r.report ? `\n\nLaporan: ${r.report}` : "");
  stats(); loadActivity();
};
let lastGroups = [];
$("dup-go").onclick = async () => {
  const folder = $("dup-folder").value.trim();
  if (!folder) return alert("Isi folder dulu");
  $("dup-list").textContent = "menghitung hash bertahap…";
  const r = await api("POST", "/api/duplicates", { folder, minSize: Number($("dup-min").value) || 1 });
  if (!r.ok) { $("dup-list").textContent = "gagal: " + (r.error || r.raw || ""); return; }
  lastGroups = r.groups || [];
  $("dup-list").innerHTML = lastGroups.length ? lastGroups.map((g) => `
    <div class="dup"><b>[${g.id}] ${fmtBytes(g.size)}</b> <code>${g.sha256.slice(0, 16)}…</code>
    ${g.paths.map((p) => `<div class="mut">${p}</div>`).join("")}
    <div class="row" style="margin-top:6px"><span class="mut">Simpan:</span>
    ${g.paths.map((p) => `<button class="btn" data-g="${g.id}" data-k="${p.replace(/"/g, "&quot;")}">✓ ${p.split("/").pop()}</button>`).join("")}
    <button class="btn ghost" data-pg="${g.id}" title="Buat proposal (aman: belum pindah)">◔ Usulkan</button>
    </div></div>`).join("")
    : "Tidak ada duplikat exact. 🎉";
  $("dup-list").querySelectorAll("button[data-g]").forEach((b) => {
    b.onclick = async () => {
      const to = prompt("Folder karantina:", folder + "/__duplikat__");
      if (!to) return;
      const rr = await api("POST", "/api/move-approved", { group: Number(b.dataset.g), keep: b.dataset.k, to });
      alert(rr.ok ? `Dipindah ${rr.moved.length} file` : "Gagal: " + (rr.error || ""));
      $("dup-go").click(); stats(); loadActivity();
    };
  });
  $("dup-list").querySelectorAll("button[data-pg]").forEach((b) => {
    b.onclick = async () => {
      const g = lastGroups.find((x) => String(x.id) === b.dataset.pg);
      if (!g) return;
      const keep = prompt("File yang DISIMPAN (kosongkan = pertama):\n" + g.paths.join("\n"), g.paths[0]);
      if (keep === null) return;
      const to = prompt("Folder karantina:", folder + "/__duplikat__");
      if (!to) return;
      const rr = await api("POST", "/api/proposals/propose", { group: g.id, keep: keep || g.paths[0], to });
      alert(rr.ok ? `Proposal ${rr.batch}: ${rr.items} item (belum pindah)` : "Gagal: " + (rr.error || ""));
      loadProps(); loadActivity();
    };
  });
  loadActivity();
};
let docs = [];
async function loadDocs() {
  const r = await api("GET", "/api/docs?limit=200");
  docs = r.docs || [];
  renderDocs();
}
function renderDocs() {
  const q = ($("doc-q").value || "").toLowerCase();
  $("doc-rows").innerHTML = docs.filter((d) => !q || (d.kategori + d.saran_nama + d.path).toLowerCase().includes(q)).slice(0, 200)
    .map((d) => `<tr><td>${d.kategori}</td><td>${Number(d.confidence).toFixed(2)}</td><td>${d.saran_nama || "—"}</td><td class="mut">${d.path}</td></tr>`).join("");
}
$("doc-reload").onclick = loadDocs;
$("doc-q").oninput = renderDocs;
$("db-reload").onclick = stats;
$("job-add").onclick = async () => {
  $("job-out").textContent = JSON.stringify(await api("POST", "/api/jobs/enqueue", { kind: $("job-kind").value, payload: $("job-payload").value }), null, 2);
  stats();
};
$("job-claim").onclick = async () => {
  $("job-out").textContent = JSON.stringify(await api("POST", "/api/jobs/claim", {}), null, 2);
  loadJobs();
};
async function loadJobs() {
  try {
    const r = await api("GET", "/api/jobs/list?limit=20");
    const jobs = r.jobs || [];
    $("job-list").innerHTML = jobs.length
      ? `<table class="tbl"><thead><tr><th>#</th><th>Status</th><th>Kind</th><th>Aksi</th></tr></thead><tbody>` +
        jobs.map((j) => `<tr><td>#${j.id}</td><td><span class="tag">${esc(j.status)}</span></td><td>${esc(j.kind)}</td>` +
          `<td class="nowrap"><button class="btn ghost sm" data-jact="pause" data-jid="${j.id}">⏸</button> ` +
          `<button class="btn ghost sm" data-jact="resume" data-jid="${j.id}">▶</button> ` +
          `<button class="btn ghost sm" data-jact="cancel" data-jid="${j.id}">✕</button></td></tr>`).join("") +
        `</tbody></table>`
      : `<span class="mut">Tidak ada job.</span>`;
    $("job-list").querySelectorAll("button[data-jact]").forEach((b) => {
      b.onclick = async () => {
        const rr = await api("POST", "/api/jobs/" + b.dataset.jact, { id: Number(b.dataset.jid) });
        if (!rr.ok) alert("Gagal: " + (rr.error || ""));
        loadJobs(); stats();
      };
    });
  } catch (e) { $("job-list").innerHTML = `<span class="mut">Gagal: ${esc(e.message || e)}</span>`; }
}
$("job-reload").onclick = loadJobs;
// ---- saklar database ----
async function loadDbState() {
  try {
    const s = await api("GET", "/api/db-state");
    $("db-toggle").checked = !!s.enabled;
    $("db-state-label").textContent = s.enabled ? "ON" : "OFF";
    $("db-state-label").style.color = s.enabled ? "var(--ok)" : "var(--warn)";
    const sz = s.file && s.file.exists ? ` • ${(s.file.size / 1048576).toFixed(1)} MB` : "";
    $("db-path-label").textContent = (s.enabled ? s.path : ":memory: (efemeral)") + sz;
  } catch (e) { $("db-path-label").textContent = "Gagal: " + (e.message || e); }
}
$("db-toggle").onchange = async () => {
  const on = $("db-toggle").checked;
  const msg = on ? "Aktifkan database? Hasil scan/index akan tersimpan."
    : "Matikan database? Mode efemeral: hasil TIDAK tersimpan ke mana pun.";
  if (!confirm(lang === "id" ? msg : (on ? "Enable database? Results will persist." : "Disable database? Ephemeral mode: nothing is stored."))) {
    $("db-toggle").checked = !on;
    return;
  }
  await api("POST", "/api/db-state", { enabled: on });
  loadDbState(); stats();
};
// ---- doctor ----
$("doctor-go").onclick = async () => {
  $("doctor-out").textContent = "memeriksa…";
  try {
    const r = await api("GET", "/api/doctor");
    $("doctor-out").innerHTML = (r.checks || []).map((c) =>
      `<div class="check ${c.status}"><b>[${esc(c.status)}]</b> ${esc(c.name)} <span class="mut">${esc(c.detail)}</span></div>`).join("")
      || `<span class="mut">Gagal: ${esc(r.raw || "")}</span>`;
  } catch (e) { $("doctor-out").textContent = "Gagal: " + (e.message || e); }
};
// ---- audit ----
async function loadAudit() {
  try {
    const f = $("audit-q").value.trim();
    const r = await api("GET", "/api/audit?limit=100" + (f ? "&action=" + encodeURIComponent(f) : ""));
    const rows = r.audit || [];
    $("audit-rows").innerHTML = rows.length
      ? rows.map((a) => `<tr><td>#${a.id}</td><td>${esc(a.actor)}</td><td><span class="tag">${esc(a.action)}</span></td>` +
        `<td>${esc(a.result)}</td><td class="mut">${esc(a.src)}${a.dst ? " → " + esc(a.dst) : ""} ${a.detail ? "· " + esc(a.detail) : ""}</td></tr>`).join("")
      : `<tr><td colspan="5" class="mut">Belum ada jejak audit.</td></tr>`;
  } catch (e) { $("audit-rows").innerHTML = `<tr><td colspan="5" class="mut">Gagal: ${esc(e.message || e)}</td></tr>`; }
}
$("audit-reload").onclick = loadAudit;
$("audit-q").oninput = loadAudit;
// ---- proposals ----
async function loadProps() {
  try {
    const r = await api("GET", "/api/proposals/list?status=pending");
    const ps = r.proposals || [];
    const byBatch = {};
    ps.forEach((p) => { (byBatch[p.batch] = byBatch[p.batch] || []).push(p); });
    const batches = Object.keys(byBatch);
    $("prop-list").innerHTML = batches.length ? batches.map((bb) => {
      const items = byBatch[bb];
      return `<div class="dup"><b>batch ${esc(bb)}</b> <span class="mut">(${items.length} item)</span>` +
        items.map((p) => `<div class="mut">◉ ${esc(p.src)} → ${esc(p.dst)}<br><span class="why">${esc(p.reasons)}</span></div>`).join("") +
        `<div class="row" style="margin-top:6px"><button class="btn acc" data-pact="approve" data-batch="${esc(bb)}">✓ Setujui</button>` +
        `<button class="btn ghost" data-pact="preview" data-batch="${esc(bb)}">Pratinjau</button>` +
        `<button class="btn ghost" data-pact="reject" data-batch="${esc(bb)}">Tolak</button></div>` +
        `<div class="mut" id="prev-${esc(bb)}"></div></div>`;
    }).join("") : "Tidak ada proposal pending. Buat dari grup duplikat (tombol ◔).";
    $("prop-list").querySelectorAll("button[data-pact]").forEach((b) => {
      b.onclick = async () => {
        const bb = b.dataset.batch, act = b.dataset.pact;
        if (act === "preview") {
          const rr = await api("GET", "/api/proposals/preview?target=" + encodeURIComponent(bb));
          const el = document.getElementById("prev-" + bb);
          if (el) el.innerHTML = "<pre class=\"log\">" + esc(JSON.stringify(rr.proposals || rr, null, 2)).slice(0, 3000) + "</pre>";
          return;
        }
        if (act === "approve" && !confirm(lang === "id" ? `Setujui batch ${bb}? File akan DIPINDAH (terverifikasi).` : `Approve batch ${bb}? Files will be MOVED (verified).`)) return;
        const rr = await api("POST", "/api/proposals/" + act, { batch: bb });
        alert(rr.ok ? (act === "approve" ? `Dipindah ${(rr.moved || []).length} file` : `Ditolak ${rr.rejected} item`) : "Gagal: " + (rr.error || ""));
        loadProps(); stats(); loadActivity();
      };
    });
  } catch (e) { $("prop-list").innerHTML = `<span class="mut">Gagal: ${esc(e.message || e)}</span>`; }
}
$("prop-reload").onclick = loadProps;
async function loadActivity() {
  try {
    const r = await api("GET", "/api/activity?limit=200");
    const items = r.items || [];
    $("act-rows").innerHTML = items.length
      ? items.map((a) => `<tr><td class="nowrap">${esc(fmtTs(a.ts))}</td><td><span class="tag">${esc(a.action)}</span></td><td class="mut">${esc(a.detail)}</td></tr>`).join("")
      : `<tr><td colspan="3" class="mut">Belum ada aktivitas tercatat.</td></tr>`;
  } catch (e) { $("act-rows").innerHTML = `<tr><td colspan="3" class="mut">Gagal memuat: ${esc(e.message || e)}</td></tr>`; }
}
$("act-reload").onclick = loadActivity;
$("act-export").onclick = async () => { await downloadExport("activity", "activity.json"); };
$("act-clear").onclick = async () => {
  if (!confirm(lang === "id" ? "Hapus seluruh log aktivitas? (data database tetap aman)" : "Clear the whole activity log? (database data stays safe)")) return;
  await api("POST", "/api/activity/clear", {});
  loadActivity();
};
health(); stats(); loadDocs(); loadActivity(); loadJobs(); loadDbState(); loadAudit(); loadProps();
setInterval(health, 15000);
