// server.mjs — bridge REST AIOrganizerPro (stdlib Node saja, tanpa npm install).
//   GUI web (../gui)  ->  http://127.0.0.1:8471/api/*  ->  core C++ / sidecar Python
//
//   GET  /api/health          -> {ok, core, sidecar, db}
//   GET  /api/stats           -> DbStats (via `aiorganizer stats --json`)
//   POST /api/scan            {folder} -> job: core scan (sinkron, output ringkas)
//   POST /api/duplicates      {folder, minSize?, workers?} -> {groups}
//   POST /api/move-approved   {group, keep, to} -> {moved}
//   POST /api/ai              {argv:[...]} -> sidecar engine (analyze/scan/karantina/...)
//   GET  /api/recommend       -> rekomendasi behavior (sidecar)
//   POST /api/reason          {path}
//   POST /api/jobs/enqueue|claim|finish
//   GET  /api/docs?limit=N    -> doc_index terbaru (baca via python3 sqlite3 stdlib)
//   GET  /                      -> serve GUI statis
//
// Env: AIORG_DB (default <pro>/data/aiorganizer.db), AIORG_CORE (default
// <pro>/build/src/aiorganizer.exe), AIORG_PORT (default 8471).
import { createServer } from "node:http";
import { spawn, spawnSync } from "node:child_process";
import { readFile, appendFile, mkdir, writeFile } from "node:fs/promises";
import { readFileSync, existsSync, statSync } from "node:fs";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PRO = path.resolve(HERE, "..");
const PORT = Number(process.env.AIORG_PORT || 8471);
const DEFAULT_DB = process.env.AIORG_DB || path.join(PRO, "data", "aiorganizer.db");
const DBSTATE = path.join(PRO, "data", "db.json");
const FFPROBE = path.join(PRO, "engine-py", "app", "ffmpeg", "bin", "ffprobe.exe");

// Saklar database: data/db.json {enabled, path}. Mati = :memory: (efemeral,
// tak ada yang tersimpan). File ini di luar DB agar saklar tetap ada saat mati.
function readDbState() {
  try {
    const s = JSON.parse(readFileSync(DBSTATE, "utf8"));
    return { enabled: s.enabled !== false, path: s.path || DEFAULT_DB };
  } catch {
    return { enabled: true, path: DEFAULT_DB };
  }
}
function resolveDb() {
  const s = readDbState();
  return s.enabled ? s.path : ":memory:";
}
const ACTIVITY = path.join(PRO, "data", "activity.log");
const CORE_CANDS = [
  process.env.AIORG_CORE || "",
  path.join(PRO, "aiorganizer.exe"),
  path.join(PRO, "build", "src", "aiorganizer.exe"),
  path.join(PRO, "build", "src", "aiorganizer"),
].filter(Boolean);
const SIDECAR = path.join(PRO, "engine-py", "sidecar.py");
const REPORTS = path.join(PRO, "engine-py", "results", "reports");
const GUI_DIR = path.join(PRO, "gui");

function findCore() {
  if (process.env.AIORG_CORE) return process.env.AIORG_CORE;
  for (const c of CORE_CANDS) {
    const r = spawnSync("cmd", ["/c", "if", "exist", `"${c}"`, "echo", "YA"], {
      encoding: "utf8",
    });
    if (r.stdout && r.stdout.includes("YA")) return c;
  }
  return CORE_CANDS[0];
}
let CORE = findCore();

function runCore(args, timeoutMs = 10 * 60 * 1000) {
  return new Promise((resolve) => {
    const p = spawn(CORE, args, {
      windowsHide: true,
      env: { ...process.env, AIORG_FFPROBE: FFPROBE },
    });
    let out = "", err = "";
    const t = setTimeout(() => { p.kill(); }, timeoutMs);
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => (err += d));
    p.on("error", (e) => { clearTimeout(t); resolve({ code: 127, out, err: String(e) }); });
    p.on("close", (code) => { clearTimeout(t); resolve({ code, out, err }); });
  });
}

function parseJsonLine(out) {
  const lines = out.trim().split(/\r?\n/);
  for (let i = lines.length - 1; i >= 0; i--) {
    try { return JSON.parse(lines[i]); } catch { /* lanjut */ }
  }
  return null;
}

// Satu proses sidecar persisten (JSON per baris). Di-restart saat saklar DB berubah.
let sidecar = null, sidecarSeq = 0;
let sidecarDb = null;
const sidecarWaiters = new Map();
let sidecarBuf = "";
function ensureSidecar() {
  const wantDb = resolveDb();
  if (sidecar && !sidecar.killed && sidecarDb === wantDb) return sidecar;
  if (sidecar && !sidecar.killed) { try { sidecar.kill(); } catch { /* abaikan */ } sidecar = null; }
  sidecarDb = wantDb;
  sidecar = spawn("python", [SIDECAR], {
    stdio: ["pipe", "pipe", "inherit"],
    windowsHide: true,
    env: { ...process.env, AIORG_DB: wantDb, PYTHONIOENCODING: "utf-8" },
  });
  sidecar.stdout.setEncoding("utf8");
  sidecar.stdout.on("data", (d) => {
    sidecarBuf += d;
    let i;
    while ((i = sidecarBuf.indexOf("\n")) >= 0) {
      const line = sidecarBuf.slice(0, i).trim();
      sidecarBuf = sidecarBuf.slice(i + 1);
      if (!line) continue;
      try {
        const msg = JSON.parse(line);
        const w = sidecarWaiters.get(msg.id);
        if (w) { sidecarWaiters.delete(msg.id); w(msg); }
      } catch { /* abaikan */ }
    }
  });
  sidecar.on("exit", () => {
    for (const [, w] of sidecarWaiters) w({ ok: false, error: "sidecar mati" });
    sidecarWaiters.clear();
    sidecar = null;
  });
  return sidecar;
}
function callSidecar(req, timeoutMs = 10 * 60 * 1000) {
  return new Promise((resolve) => {
    const sc = ensureSidecar();
    const id = ++sidecarSeq;
    const t = setTimeout(() => {
      sidecarWaiters.delete(id);
      resolve({ id, ok: false, error: "sidecar timeout" });
    }, timeoutMs);
    sidecarWaiters.set(id, (m) => { clearTimeout(t); resolve(m); });
    sc.stdin.write(JSON.stringify({ id, ...req }) + "\n", (e) => {
      if (e) { clearTimeout(t); sidecarWaiters.delete(id); resolve({ id, ok: false, error: String(e) }); }
    });
  });
}

function bodyJson(req) {
  return new Promise((resolve) => {
    let b = "";
    req.on("data", (d) => (b += d));
    req.on("end", () => {
      try { resolve(b ? JSON.parse(b) : {}); } catch { resolve({}); }
    });
  });
}
function send(res, code, obj) {
  res.writeHead(code, { "content-type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(obj));
}

// Log aktivitas user (JSONL, 1 baris = 1 kejadian). Best-effort: gagal tulis = abaikan.
async function logActivity(action, detail) {
  try {
    await mkdir(path.dirname(ACTIVITY), { recursive: true });
    await appendFile(ACTIVITY, JSON.stringify({
      ts: new Date().toISOString(), action, detail: String(detail ?? "").slice(0, 500),
    }) + "\n", "utf8");
  } catch { /* abaikan */ }
}
async function readActivity(limit) {
  try {
    const text = await readFile(ACTIVITY, "utf8");
    const lines = text.split("\n").filter((l) => l.trim());
    const n = Math.max(1, Math.min(Number(limit) || 200, 1000));
    return lines.slice(-n).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean).reverse();
  } catch { return []; }
}
const MIME = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".png": "image/png", ".ico": "image/x-icon", ".svg": "image/svg+xml" };

const server = createServer(async (req, res) => {
  const u = new URL(req.url, "http://x");
  try {
    if (req.method === "GET" && u.pathname === "/api/health") {
      const core = await runCore(["version"]);
      const sc = await callSidecar({ cmd: "ping" }, 15000);
      const st = readDbState();
      return send(res, 200, { ok: true, core: core.out.trim(), sidecar: sc, db: st.path, dbEnabled: st.enabled });
    }
    if (req.method === "GET" && u.pathname === "/api/stats") {
      const r = await runCore(["stats", "--db", resolveDb(), "--json"]);
      return send(res, 200, parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-2000), err: r.err.slice(-500) });
    }
    if (req.method === "POST" && u.pathname === "/api/scan") {
      const b = await bodyJson(req);
      if (!b.folder) return send(res, 400, { ok: false, error: "folder wajib" });
      const r = await runCore(["scan", b.folder, "--db", resolveDb(), "--json", "--actor", "gui"]);
      const out = parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-2000) };
      await logActivity("scan", `${b.folder} -> ${out.files ?? "?"} files`);
      return send(res, 200, out);
    }
    if (req.method === "POST" && u.pathname === "/api/duplicates") {
      const b = await bodyJson(req);
      if (!b.folder) return send(res, 400, { ok: false, error: "folder wajib" });
      const args = ["duplicates", b.folder, "--db", resolveDb(), "--json", "--actor", "gui",
        "--min-size", String(b.minSize ?? 1), "--workers", String(b.workers ?? 4)];
      const r = await runCore(args, 30 * 60 * 1000);
      const out = parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-4000) };
      await logActivity("duplicates", `${b.folder} -> ${(out.groups || []).length} grup`);
      return send(res, 200, out);
    }
    if (req.method === "POST" && u.pathname === "/api/move-approved") {
      const b = await bodyJson(req);
      if (!b.group || !b.keep || !b.to) return send(res, 400, { ok: false, error: "group/keep/to wajib" });
      const r = await runCore(["move-approved", "--db", resolveDb(), "--group", String(b.group),
        "--keep", b.keep, "--to", b.to, "--json", "--actor", "gui"]);
      const out = parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-2000) };
      await logActivity("move-approved", `grup ${b.group}: ${(out.moved || []).length} dipindah, simpan ${b.keep}`);
      return send(res, 200, out);
    }
    if (req.method === "POST" && u.pathname === "/api/ai") {
      const b = await bodyJson(req);
      if (!Array.isArray(b.argv)) return send(res, 400, { ok: false, error: "argv[] wajib" });
      // kontrak aman: cegah penulisan ke folder output terpadu? engine sudah
      // punya DirLock + dry-run; teruskan apa adanya.
      const r = await callSidecar({ cmd: "engine", argv: b.argv }, 30 * 60 * 1000);
      r.output = (r.output || "").slice(-8000); // batasi payload
      await logActivity(`ai:${b.argv[0] || "?"}`, `${b.argv[1] || ""}${b.argv.includes("--dry-run") ? " (dry-run)" : ""}`);
      return send(res, 200, r);
    }
    if (req.method === "GET" && u.pathname === "/api/videos/list") {
      const r = await callSidecar({ cmd: "list-videos", root: u.searchParams.get("root") || "", limit: 2000, kind: u.searchParams.get("kind") || "videos" }, 120000);
      return send(res, 200, r);
    }
    if (req.method === "POST" && u.pathname === "/api/organize") {
      const b = await bodyJson(req);
      if (!b.folder) return send(res, 400, { ok: false, error: "folder wajib" });
      const mode = b.kind === "images" ? "organize-images" : "organize-videos";
      const argv = [mode, b.folder];
      if (Array.isArray(b.files) && b.files.length) {
        const listPath = path.join(os.tmpdir(), `orgsel-${Date.now()}.txt`);
        await writeFile(listPath, b.files.join("\n"), "utf8");
        argv.push("--file-list", listPath);
      }
      if (b.dest) argv.push("--dest-root", b.dest);
      for (const c of b.content || []) argv.push("--content", c);
      if (b.copy) argv.push("--apply-copy");
      if (b.dated) argv.push("--rename-dated");
      if (b.junk) argv.push("--junk-to-delete");
      if (b.prune) argv.push("--prune-empty");
      if (b.limit) argv.push("--limit", String(b.limit));
      if (b.apply) argv.push("--apply"); else argv.push("--dry-run");
      const r = await callSidecar({ cmd: "engine", argv }, 30 * 60 * 1000);
      r.output = (r.output || "").slice(-8000);
      await logActivity(`ai:${mode}`, `${b.folder}${b.apply ? "" : " (dry-run)"}`);
      return send(res, 200, r);
    }
    if (req.method === "GET" && u.pathname === "/api/recommend") {
      return send(res, 200, await callSidecar({ cmd: "recommend" }, 30000));
    }
    if (req.method === "POST" && u.pathname === "/api/reason") {
      const b = await bodyJson(req);
      return send(res, 200, await callSidecar({ cmd: "reason", path: b.path || "" }, 60000));
    }
    if (req.method === "POST" && u.pathname === "/api/jobs/enqueue") {
      const b = await bodyJson(req);
      const r = await runCore(["job-enqueue", b.kind || "scan", b.payload || "", "--db", resolveDb(), "--json", "--actor", "gui"]);
      const out = parseJsonLine(r.out) || { ok: false, raw: r.out };
      await logActivity("job-enqueue", `${b.kind || "scan"} #${out.id ?? "?"}`);
      return send(res, 200, out);
    }
    if (req.method === "POST" && u.pathname === "/api/jobs/claim") {
      const r = await runCore(["job-claim", "--db", resolveDb(), "--json"]);
      const out = parseJsonLine(r.out) || { ok: false };
      if (out.ok) await logActivity("job-claim", `#${out.id} ${out.kind || ""}`);
      return send(res, 200, out);
    }
    if (req.method === "POST" && u.pathname === "/api/jobs/finish") {
      const b = await bodyJson(req);
      const r = await runCore(["job-finish", String(b.id), b.status || "done", b.result || "", "--db", resolveDb(), "--json"]);
      const out = parseJsonLine(r.out) || { ok: false };
      if (out.ok) await logActivity("job-finish", `#${b.id} ${b.status || "done"}`);
      return send(res, 200, out);
    }
    if (req.method === "GET" && u.pathname === "/api/activity") {
      return send(res, 200, { ok: true, items: await readActivity(u.searchParams.get("limit")) });
    }
    if (req.method === "POST" && u.pathname === "/api/activity/clear") {
      try { await writeFile(ACTIVITY, "", "utf8"); } catch { /* abaikan */ }
      return send(res, 200, { ok: true });
    }
    if (req.method === "GET" && u.pathname === "/api/activity/export") {
      await logActivity("export", "activity.json diunduh");
      try {
        const data = await readFile(ACTIVITY);
        res.writeHead(200, {
          "content-type": "application/json; charset=utf-8",
          "content-disposition": 'attachment; filename="activity.json"',
        });
        return res.end(data);
      } catch { return send(res, 404, { ok: false, error: "log kosong/belum ada" }); }
    }
    if (req.method === "GET" && u.pathname === "/api/reports/get") {
      const name = path.basename(u.searchParams.get("name") || "");
      if (!name || name.includes("..")) return send(res, 400, { ok: false, error: "nama file wajib" });
      const fp = path.join(REPORTS, name);
      try {
        const data = await readFile(fp);
        await logActivity("export", `${name} diunduh`);
        res.writeHead(200, {
          "content-type": name.endsWith(".zip") ? "application/zip" : "text/csv; charset=utf-8",
          "content-disposition": `attachment; filename="${name}"`,
        });
        return res.end(data);
      } catch { return send(res, 404, { ok: false, error: "file tidak ada" }); }
    }
    // ---- saklar + kesehatan database ----
    if (req.method === "GET" && u.pathname === "/api/db-state") {
      const st = readDbState();
      let file = { exists: false, size: 0 };
      try {
        if (st.enabled && st.path !== ":memory:" && existsSync(st.path)) {
          file = { exists: true, size: statSync(st.path).size };
        }
      } catch { /* abaikan */ }
      return send(res, 200, { ok: true, enabled: st.enabled, path: st.path, file });
    }
    if (req.method === "POST" && u.pathname === "/api/db-state") {
      const b = await bodyJson(req);
      const st = { enabled: b.enabled !== false, path: b.path || readDbState().path || DEFAULT_DB };
      await mkdir(path.dirname(DBSTATE), { recursive: true });
      await writeFile(DBSTATE, JSON.stringify(st, null, 2), "utf8");
      await logActivity("db-switch", st.enabled ? `ON -> ${st.path}` : "OFF (efemeral :memory:)");
      return send(res, 200, { ok: true, ...st });
    }
    if (req.method === "GET" && u.pathname === "/api/doctor") {
      const root = u.searchParams.get("root") || "";
      const args = ["doctor", "--db", resolveDb(), "--json"];
      if (root) args.push("--root", root);
      const r = await runCore(args, 60000);
      return send(res, 200, parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-2000) });
    }
    if (req.method === "GET" && u.pathname === "/api/audit") {
      const args = ["audit", "--db", resolveDb(), "--json",
        "--action", u.searchParams.get("action") || "",
        "--limit", u.searchParams.get("limit") || "100"];
      const r = await runCore(args, 60000);
      return send(res, 200, parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-2000) });
    }
    // ---- jobs: list / pause / resume / cancel ----
    if (req.method === "GET" && u.pathname === "/api/jobs/list") {
      const r = await runCore(["job-list", "--db", resolveDb(), "--json",
        "--status", u.searchParams.get("status") || "",
        "--limit", u.searchParams.get("limit") || "50"]);
      return send(res, 200, parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-2000) });
    }
    for (const act of ["pause", "resume", "cancel"]) {
      if (req.method === "POST" && u.pathname === `/api/jobs/${act}`) {
        const b = await bodyJson(req);
        if (b.id == null) return send(res, 400, { ok: false, error: "id wajib" });
        const r = await runCore([`job-${act}`, String(b.id), "--db", resolveDb(), "--json", "--actor", "gui"]);
        const out = parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-500) };
        if (out.ok) await logActivity(`job-${act}`, `#${b.id}`);
        return send(res, 200, out);
      }
    }
    // ---- proposals: propose / list / preview / approve / reject ----
    if (req.method === "POST" && u.pathname === "/api/proposals/propose") {
      const b = await bodyJson(req);
      if (!b.group || !b.keep || !b.to) return send(res, 400, { ok: false, error: "group/keep/to wajib" });
      const args = ["proposals", "propose", "--group", String(b.group), "--keep", b.keep,
        "--to", b.to, "--db", resolveDb(), "--json", "--actor", "gui"];
      if (b.reasons) args.push("--reasons", b.reasons);
      const r = await runCore(args);
      const out = parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-2000) };
      if (out.ok) await logActivity("proposal", `batch ${out.batch}: ${out.items} item dari grup ${b.group}`);
      return send(res, 200, out);
    }
    if (req.method === "GET" && u.pathname === "/api/proposals/list") {
      const r = await runCore(["proposals", "list", "--db", resolveDb(), "--json",
        "--status", u.searchParams.get("status") || "pending"]);
      return send(res, 200, parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-2000) });
    }
    if (req.method === "GET" && u.pathname === "/api/proposals/preview") {
      const t = u.searchParams.get("target") || "";
      if (!t) return send(res, 400, { ok: false, error: "target wajib" });
      const r = await runCore(["proposals", "preview", t, "--db", resolveDb(), "--json"]);
      return send(res, 200, parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-2000) });
    }
    for (const act of ["approve", "reject"]) {
      if (req.method === "POST" && u.pathname === `/api/proposals/${act}`) {
        const b = await bodyJson(req);
        if (!b.batch) return send(res, 400, { ok: false, error: "batch wajib" });
        const r = await runCore(["proposals", act, b.batch, "--db", resolveDb(), "--json", "--actor", "gui"]);
        const out = parseJsonLine(r.out) || { ok: false, raw: r.out.slice(-2000) };
        if (out.ok) await logActivity(`proposal-${act}`, `${b.batch}`);
        return send(res, 200, out);
      }
    }
    if (req.method === "GET" && u.pathname === "/api/docs") {
      const limit = Math.min(Number(u.searchParams.get("limit") || 100), 500);
      const py = "import json,os,sqlite3,sys;db=sys.argv[1];n=int(sys.argv[2]);" +
        "c=sqlite3.connect('file:'+db+'?mode=ro',uri=True);" +
        "rows=c.execute('SELECT path,kategori,confidence,ringkasan,saran_nama FROM doc_index ORDER BY updated_ms DESC LIMIT ?', (n,)).fetchall();" +
        "print(json.dumps([{'path':a,'kategori':b,'confidence':c,'ringkasan':d,'saran_nama':e} for a,b,c,d,e in rows], ensure_ascii=False))";
      const r = spawnSync("python", ["-c", py, resolveDb(), String(limit)], { encoding: "utf8", timeout: 30000 });
      try { return send(res, 200, { ok: true, docs: JSON.parse(r.stdout || "[]") }); }
      catch { return send(res, 200, { ok: false, error: (r.stderr || "db belum ada").slice(-500) }); }
    }
    // file statis GUI
    if (req.method === "GET") {
      let p = u.pathname === "/" ? "/index.html" : u.pathname;
      if (p.includes("..")) return send(res, 400, { ok: false });
      try {
        const data = await readFile(path.join(GUI_DIR, p.slice(1)));
        res.writeHead(200, { "content-type": MIME[path.extname(p).toLowerCase()] || "application/octet-stream" });
        return res.end(data);
      } catch { return send(res, 404, { ok: false, error: "tidak ada" }); }
    }
    return send(res, 404, { ok: false });
  } catch (e) {
    return send(res, 500, { ok: false, error: String(e).slice(0, 1000) });
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`AIOrganizerPro server: http://127.0.0.1:${PORT}/  db=${resolveDb()}  core=${CORE}`);
});
