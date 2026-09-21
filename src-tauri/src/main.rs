// Backend Rust AIOrganizerPro (Tauri v2) — aplikasi Windows native.
//   - core C++  : <pro>/aiorganizer(.exe)  (scan/duplicates/stats/jobs)
//   - engine-py : <pro>/engine-py/sidecar.py via `python` (AI/broken/analyze/docs)
// GUI (../gui) memanggil perintah ini via Tauri invoke — tanpa server, tanpa
// port. Build: `rustup toolchain install stable` lalu `tauri build` dari sini.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};

fn pro_root() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|x| x.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."))
}

fn core_bin() -> PathBuf {
    if let Ok(v) = std::env::var("AIORG_CORE") {
        return PathBuf::from(v);
    }
    let root = pro_root();
    for c in [
        root.join("aiorganizer.exe"),
        root.join("aiorganizer"),
        root.join("../aiorganizer.exe"),
        root.join("../build/src/aiorganizer.exe"),
    ] {
        if c.exists() {
            return c;
        }
    }
    PathBuf::from("aiorganizer")
}

fn unified_db() -> String {
    std::env::var("AIORG_DB").unwrap_or_else(|_| {
        pro_root()
            .join("../data/aiorganizer.db")
            .to_string_lossy()
            .into_owned()
    })
}

fn db_state_path() -> PathBuf {
    pro_root().join("../data/db.json")
}

// Saklar database (data/db.json). Mati = ":memory:" (efemeral).
fn read_db_state() -> (bool, String) {
    let def_path = unified_db();
    let Ok(text) = std::fs::read_to_string(db_state_path()) else {
        return (true, def_path);
    };
    let Ok(v) = serde_json::from_str::<serde_json::Value>(&text) else {
        return (true, def_path);
    };
    let enabled = v.get("enabled").and_then(|x| x.as_bool()).unwrap_or(true);
    let path = v
        .get("path")
        .and_then(|x| x.as_str())
        .unwrap_or("")
        .to_string();
    (enabled, if path.is_empty() { def_path } else { path })
}

fn active_db() -> String {
    let (enabled, path) = read_db_state();
    if enabled {
        path
    } else {
        ":memory:".into()
    }
}

fn activity_path() -> PathBuf {
    if let Ok(v) = std::env::var("AIORG_ACTIVITY") {
        return PathBuf::from(v);
    }
    pro_root().join("../data/activity.log")
}

// Log aktivitas user (JSONL). Best-effort: gagal tulis = abaikan.
fn log_activity(action: &str, detail: &str) {
    use std::io::Write as _;
    let entry = serde_json::json!({
        "ts": chrono_now_iso(),
        "action": action,
        "detail": detail.chars().take(500).collect::<String>(),
    });
    if let Some(parent) = activity_path().parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(activity_path())
    {
        let _ = writeln!(f, "{entry}");
    }
}

fn chrono_now_iso() -> String {
    // ISO-8601 UTC tanpa dep chrono: detik epoch -> format manual.
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    // 1970-01-01 + secs -> hitung tanggal (algoritma days-from-civil terbalik sederhana).
    let days = (secs / 86400) as i64;
    let tod = secs % 86400;
    let z = days + 719468;
    let era = z.div_euclid(146097);
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        y, m, d, tod / 3600, (tod % 3600) / 60, tod % 60
    )
}

fn run_core(args: Vec<String>) -> Result<serde_json::Value, String> {
    let ffprobe = pro_root().join("../engine-py/app/ffmpeg/bin/ffprobe.exe");
    let out = Command::new(core_bin())
        .args(&args)
        .env("AIORG_FFPROBE", ffprobe)
        .output()
        .map_err(|e| format!("core gagal dijalankan: {e}"))?;
    let text = String::from_utf8_lossy(&out.stdout).to_string();
    // Ambil baris JSON terakhir (abaikan progress text).
    for line in text.lines().rev() {
        if let Ok(v) = serde_json::from_str::<serde_json::Value>(line.trim()) {
            return Ok(v);
        }
    }
    if out.status.success() {
        Ok(serde_json::json!({"ok": true, "raw": text}))
    } else {
        Err(format!(
            "core exit {}: {}",
            out.status,
            String::from_utf8_lossy(&out.stderr)
        ))
    }
}

fn call_sidecar(cmd: &str, extra: serde_json::Value) -> Result<serde_json::Value, String> {
    let sidecar = pro_root().join("../engine-py/sidecar.py");
    let mut req = serde_json::json!({"id": 1, "cmd": cmd});
    for (k, v) in extra.as_object().cloned().unwrap_or_default() {
        req[k] = v;
    }
    let mut child = Command::new("python")
        .arg(&sidecar)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .env("AIORG_DB", active_db())
        .spawn()
        .map_err(|e| format!("sidecar gagal: {e}"))?;
    {
        let stdin = child.stdin.as_mut().ok_or("stdin sidecar?")?;
        writeln!(stdin, "{}", req).map_err(|e| e.to_string())?;
    }
    let stdout = child.stdin.take();
    drop(stdout);
    let reader = BufReader::new(child.stdout.take().ok_or("stdout sidecar?")?);
    for line in reader.lines().take(50) {
        let line = line.map_err(|e| e.to_string())?;
        if let Ok(v) = serde_json::from_str::<serde_json::Value>(line.trim()) {
            let _ = child.wait();
            return Ok(v);
        }
    }
    let _ = child.wait();
    Err("sidecar tanpa respon JSON".into())
}

#[tauri::command]
fn core_scan(folder: String) -> Result<serde_json::Value, String> {
    let r = run_core(vec!["scan".into(), folder.clone(), "--db".into(), active_db(), "--json".into(), "--actor".into(), "gui".into()]);
    if let Ok(v) = &r {
        log_activity("scan", &format!("{} -> {} files", folder, v.get("files").and_then(|x| x.as_i64()).map(|x| x.to_string()).unwrap_or("?".into())));
    }
    r
}

#[tauri::command]
fn core_duplicates(folder: String, min_size: i64) -> Result<serde_json::Value, String> {
    let r = run_core(vec![
        "duplicates".into(), folder.clone(), "--db".into(), active_db(),
        "--json".into(), "--actor".into(), "gui".into(),
        "--min-size".into(), min_size.to_string(),
    ]);
    if let Ok(v) = &r {
        let n = v.get("groups").and_then(|g| g.as_array()).map(|a| a.len()).unwrap_or(0);
        log_activity("duplicates", &format!("{folder} -> {n} grup"));
    }
    r
}

#[tauri::command]
fn core_move_approved(group: i64, keep: String, to: String) -> Result<serde_json::Value, String> {
    // Kontrak aman: move terverifikasi + rollback tercatat (di core C++).
    let r = run_core(vec![
        "move-approved".into(), "--db".into(), active_db(),
        "--group".into(), group.to_string(), "--keep".into(), keep.clone(),
        "--to".into(), to, "--json".into(), "--actor".into(), "gui".into(),
    ]);
    if let Ok(v) = &r {
        let n = v.get("moved").and_then(|m| m.as_array()).map(|a| a.len()).unwrap_or(0);
        log_activity("move-approved", &format!("grup {group}: {n} dipindah, simpan {keep}"));
    }
    r
}

#[tauri::command]
fn core_stats() -> Result<serde_json::Value, String> {
    run_core(vec!["stats".into(), "--db".into(), active_db(), "--json".into()])
}

#[tauri::command]
fn ai_engine(argv: Vec<String>) -> Result<serde_json::Value, String> {
    let dry = argv.iter().any(|a| a == "--dry-run");
    let r = call_sidecar("engine", serde_json::json!({"argv": argv.clone()}));
    log_activity(
        &format!("ai:{}", argv.first().cloned().unwrap_or("?".into())),
        &format!("{}{}", argv.get(1).cloned().unwrap_or_default(), if dry { " (dry-run)" } else { "" }),
    );
    r
}

#[tauri::command]
fn ai_reason(path: String) -> Result<serde_json::Value, String> {
    call_sidecar("reason", serde_json::json!({"path": path}))
}

#[tauri::command]
fn ai_recommend() -> Result<serde_json::Value, String> {
    call_sidecar("recommend", serde_json::json!({}))
}

#[tauri::command]
fn docs_list(limit: i64) -> Result<serde_json::Value, String> {
    call_sidecar("docs", serde_json::json!({"limit": limit}))
}

#[tauri::command]
fn videos_list(root: String, limit: i64, kind: String) -> Result<serde_json::Value, String> {
    call_sidecar("list-videos", serde_json::json!({"root": root, "limit": limit, "kind": kind}))
}

#[tauri::command]
fn org_run(kind: String, folder: String, files: Vec<String>, dest: String, content: Vec<String>,
           copy: bool, dated: bool, junk: bool, prune: bool, limit: i64,
           apply: bool) -> Result<serde_json::Value, String> {
    let mode = if kind == "images" { "organize-images" } else { "organize-videos" };
    let mut argv = vec![mode.to_string(), folder.clone()];
    if !files.is_empty() {
        let list_path = std::env::temp_dir().join(format!(
            "orgsel-{}.txt",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_millis())
                .unwrap_or(0)
        ));
        std::fs::write(&list_path, files.join("\n")).map_err(|e| e.to_string())?;
        argv.push("--file-list".into());
        argv.push(list_path.to_string_lossy().into_owned());
    }
    if !dest.is_empty() {
        argv.push("--dest-root".into());
        argv.push(dest);
    }
    for c in content {
        argv.push("--content".into());
        argv.push(c);
    }
    if copy { argv.push("--apply-copy".into()); }
    if dated { argv.push("--rename-dated".into()); }
    if junk { argv.push("--junk-to-delete".into()); }
    if prune { argv.push("--prune-empty".into()); }
    if limit > 0 {
        argv.push("--limit".into());
        argv.push(limit.to_string());
    }
    if apply { argv.push("--apply".into()); } else { argv.push("--dry-run".into()); }
    let r = call_sidecar("engine", serde_json::json!({"argv": argv}));
    log_activity(&format!("ai:{mode}"), &format!("{folder}{}", if apply { "" } else { " (dry-run)" }));
    r
}

#[tauri::command]
fn app_info() -> Result<serde_json::Value, String> {
    let ver = match run_core(vec!["version".into()]) {
        Ok(v) => v
            .get("raw")
            .and_then(|r| r.as_str())
            .unwrap_or("")
            .trim()
            .to_string(),
        Err(e) => return Err(e),
    };
    Ok(serde_json::json!({
        "ok": true, "core_version": ver,
        "db": active_db(), "db_enabled": read_db_state().0, "mode": "native",
    }))
}

#[tauri::command]
fn job_enqueue(kind: String, payload: String) -> Result<serde_json::Value, String> {
    let r = run_core(vec![
        "job-enqueue".into(), kind.clone(), payload,
        "--db".into(), active_db(), "--json".into(), "--actor".into(), "gui".into(),
    ]);
    if let Ok(v) = &r {
        log_activity("job-enqueue", &format!("{} #{}", kind, v.get("id").and_then(|x| x.as_i64()).map(|x| x.to_string()).unwrap_or("?".into())));
    }
    r
}

#[tauri::command]
fn job_claim() -> Result<serde_json::Value, String> {
    let r = run_core(vec!["job-claim".into(), "--db".into(), active_db(), "--json".into()]);
    if let Ok(v) = &r {
        if v.get("ok").and_then(|x| x.as_bool()).unwrap_or(false) {
            log_activity("job-claim", &format!("#{} {}", v.get("id").and_then(|x| x.as_i64()).unwrap_or(0), v.get("kind").and_then(|x| x.as_str()).unwrap_or("")));
        }
    }
    r
}

#[tauri::command]
fn job_finish(id: i64, status: String, result: String) -> Result<serde_json::Value, String> {
    let r = run_core(vec![
        "job-finish".into(), id.to_string(), status.clone(), result,
        "--db".into(), active_db(), "--json".into(),
    ]);
    if r.as_ref().map(|v| v.get("ok").and_then(|x| x.as_bool()).unwrap_or(false)).unwrap_or(false) {
        log_activity("job-finish", &format!("#{id} {status}"));
    }
    r
}

#[tauri::command]
fn activity_list(limit: i64) -> Result<serde_json::Value, String> {
    let n = limit.clamp(1, 1000) as usize;
    let items: Vec<serde_json::Value> = std::fs::read_to_string(activity_path())
        .unwrap_or_default()
        .lines()
        .filter(|l| !l.trim().is_empty())
        .filter_map(|l| serde_json::from_str(l).ok())
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .take(n)
        .collect();
    Ok(serde_json::json!({"ok": true, "items": items}))
}

#[tauri::command]
fn activity_clear() -> Result<serde_json::Value, String> {
    let _ = std::fs::write(activity_path(), "");
    Ok(serde_json::json!({"ok": true}))
}

fn exports_dir() -> PathBuf {
    pro_root().join("../data/exports")
}

// Simpan salinan log aktivitas ke data/exports (untuk tombol Unduh di native).
#[tauri::command]
fn activity_export() -> Result<serde_json::Value, String> {
    let _ = std::fs::create_dir_all(exports_dir());
    let name = format!("activity-{}.json", chrono_now_iso().replace(':', "-"));
    let dst = exports_dir().join(&name);
    match std::fs::copy(activity_path(), &dst) {
        Ok(_) => {
            log_activity("export", &format!("{name} diunduh"));
            Ok(serde_json::json!({"ok": true, "path": dst.to_string_lossy()}))
        }
        Err(e) => Ok(serde_json::json!({"ok": false, "error": e.to_string()})),
    }
}

fn reports_dir() -> PathBuf {
    pro_root().join("../engine-py/results/reports")
}

// Salin 1 file laporan (basename saja, anti path-traversal) ke data/exports.
#[tauri::command]
fn report_export(name: String) -> Result<serde_json::Value, String> {
    if name.is_empty() || name.contains("..") || name.contains('/') || name.contains('\\') {
        return Ok(serde_json::json!({"ok": false, "error": "nama file tidak valid"}));
    }
    let src = reports_dir().join(&name);
    if !src.is_file() {
        return Ok(serde_json::json!({"ok": false, "error": "file tidak ada"}));
    }
    let _ = std::fs::create_dir_all(exports_dir());
    let dst = exports_dir().join(&name);
    match std::fs::copy(&src, &dst) {
        Ok(_) => {
            log_activity("export", &format!("{name} diunduh"));
            Ok(serde_json::json!({"ok": true, "path": dst.to_string_lossy()}))
        }
        Err(e) => Ok(serde_json::json!({"ok": false, "error": e.to_string()})),
    }
}

// ---- saklar database (data/db.json) ----
#[tauri::command]
fn db_state() -> Result<serde_json::Value, String> {
    let (enabled, path) = read_db_state();
    let (exists, size) = if enabled && path != ":memory:" {
        std::fs::metadata(&path)
            .map(|m| (true, m.len() as i64))
            .unwrap_or((false, 0))
    } else {
        (false, 0)
    };
    Ok(serde_json::json!({
        "ok": true, "enabled": enabled, "path": path,
        "file": {"exists": exists, "size": size},
    }))
}

#[tauri::command]
fn db_set_enabled(enabled: bool) -> Result<serde_json::Value, String> {
    let (_, path) = read_db_state();
    if let Some(parent) = db_state_path().parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let text = serde_json::json!({"enabled": enabled, "path": path}).to_string();
    std::fs::write(db_state_path(), text).map_err(|e| e.to_string())?;
    log_activity("db-switch", if enabled { "ON" } else { "OFF (efemeral :memory:)" });
    Ok(serde_json::json!({"ok": true, "enabled": enabled, "path": path}))
}

// ---- doctor / audit (master doc #85) ----
#[tauri::command]
fn core_doctor(root: String) -> Result<serde_json::Value, String> {
    let mut args = vec!["doctor".into(), "--db".into(), active_db(), "--json".into()];
    if !root.is_empty() {
        args.push("--root".into());
        args.push(root);
    }
    run_core(args)
}

#[tauri::command]
fn audit_list(action: String, limit: i64) -> Result<serde_json::Value, String> {
    run_core(vec![
        "audit".into(), "--db".into(), active_db(), "--json".into(),
        "--action".into(), action, "--limit".into(), limit.to_string(),
    ])
}

// ---- jobs: list / pause / resume / cancel ----
#[tauri::command]
fn job_list(status: String, limit: i64) -> Result<serde_json::Value, String> {
    run_core(vec![
        "job-list".into(), "--db".into(), active_db(), "--json".into(),
        "--status".into(), status, "--limit".into(), limit.to_string(),
    ])
}

#[tauri::command]
fn job_pause(id: i64) -> Result<serde_json::Value, String> {
    let r = run_core(vec!["job-pause".into(), id.to_string(), "--db".into(), active_db(), "--json".into(), "--actor".into(), "gui".into()]);
    if r.as_ref().map(|v| v.get("ok").and_then(|x| x.as_bool()).unwrap_or(false)).unwrap_or(false) {
        log_activity("job-pause", &format!("#{id}"));
    }
    r
}

#[tauri::command]
fn job_resume(id: i64) -> Result<serde_json::Value, String> {
    let r = run_core(vec!["job-resume".into(), id.to_string(), "--db".into(), active_db(), "--json".into(), "--actor".into(), "gui".into()]);
    if r.as_ref().map(|v| v.get("ok").and_then(|x| x.as_bool()).unwrap_or(false)).unwrap_or(false) {
        log_activity("job-resume", &format!("#{id}"));
    }
    r
}

#[tauri::command]
fn job_cancel(id: i64) -> Result<serde_json::Value, String> {
    let r = run_core(vec!["job-cancel".into(), id.to_string(), "--db".into(), active_db(), "--json".into(), "--actor".into(), "gui".into()]);
    if r.as_ref().map(|v| v.get("ok").and_then(|x| x.as_bool()).unwrap_or(false)).unwrap_or(false) {
        log_activity("job-cancel", &format!("#{id}"));
    }
    r
}

// ---- proposals: propose / list / preview / approve / reject (master #150) ----
#[tauri::command]
fn prop_propose(group: i64, keep: String, to: String, reasons: String) -> Result<serde_json::Value, String> {
    let mut args = vec![
        "proposals".into(), "propose".into(), "--group".into(), group.to_string(),
        "--keep".into(), keep, "--to".into(), to,
        "--db".into(), active_db(), "--json".into(), "--actor".into(), "gui".into(),
    ];
    if !reasons.is_empty() {
        args.push("--reasons".into());
        args.push(reasons);
    }
    let r = run_core(args);
    if let Ok(v) = &r {
        if let Some(b) = v.get("batch").and_then(|x| x.as_str()) {
            log_activity("proposal", &format!("batch {b} dari grup {group}"));
        }
    }
    r
}

#[tauri::command]
fn prop_list(status: String) -> Result<serde_json::Value, String> {
    run_core(vec![
        "proposals".into(), "list".into(), "--db".into(), active_db(), "--json".into(),
        "--status".into(), status,
    ])
}

#[tauri::command]
fn prop_preview(target: String) -> Result<serde_json::Value, String> {
    run_core(vec![
        "proposals".into(), "preview".into(), target,
        "--db".into(), active_db(), "--json".into(),
    ])
}

#[tauri::command]
fn prop_approve(batch: String) -> Result<serde_json::Value, String> {
    let r = run_core(vec![
        "proposals".into(), "approve".into(), batch.clone(),
        "--db".into(), active_db(), "--json".into(), "--actor".into(), "gui".into(),
    ]);
    if let Ok(v) = &r {
        let n = v.get("moved").and_then(|m| m.as_array()).map(|a| a.len()).unwrap_or(0);
        log_activity("proposal-approve", &format!("{batch}: {n} dipindah"));
    }
    r
}

#[tauri::command]
fn prop_reject(target: String) -> Result<serde_json::Value, String> {
    let r = run_core(vec![
        "proposals".into(), "reject".into(), target.clone(),
        "--db".into(), active_db(), "--json".into(), "--actor".into(), "gui".into(),
    ]);
    if r.as_ref().map(|v| v.get("ok").and_then(|x| x.as_bool()).unwrap_or(false)).unwrap_or(false) {
        log_activity("proposal-reject", &target);
    }
    r
}

// ---- operasi panel video desktop ----
// Semua aksi diselesaikan di native backend, bukan lewat shell JavaScript.
// "Hapus" pada UI dipetakan ke 99_To-Delete agar tetap dapat dipulihkan.
fn checked_video_path(path: &str) -> Result<PathBuf, String> {
    let p = PathBuf::from(path);
    if !p.is_file() { return Err("file video tidak ditemukan".into()); }
    std::fs::canonicalize(p).map_err(|e| e.to_string())
}

fn video_annotation_path() -> PathBuf { pro_root().join("data").join("video-annotations.json") }

fn video_annotation_for(path: &str) -> serde_json::Value {
    let all: serde_json::Value = std::fs::read_to_string(video_annotation_path())
        .ok().and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_else(|| serde_json::json!({}));
    all.get(path).cloned().unwrap_or_else(|| serde_json::json!({"tags": [], "note": ""}))
}

#[tauri::command]
fn video_inspect(path: String) -> Result<serde_json::Value, String> {
    let p = checked_video_path(&path)?;
    let meta = std::fs::metadata(&p).map_err(|e| e.to_string())?;
    let modified = meta.modified().ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_secs().to_string()).unwrap_or_else(|| "—".into());
    let path = p.to_string_lossy().into_owned();
    let ffprobe = pro_root().join("engine-py/app/ffmpeg/bin/ffprobe.exe");
    let probe_result = Command::new(ffprobe)
        .args(["-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,profile,width,height,avg_frame_rate,display_aspect_ratio", "-of", "json"])
        .arg(&p).output();
    let mut probe = serde_json::json!({"ok": false, "error": "ffprobe tidak tersedia"});
    if let Ok(out) = probe_result {
        if out.status.success() {
            if let Ok(raw) = serde_json::from_slice::<serde_json::Value>(&out.stdout) {
                let streams = raw.get("streams").and_then(|x| x.as_array()).cloned().unwrap_or_default();
                let vs = streams.iter().find(|s| s.get("codec_type").and_then(|x| x.as_str()) == Some("video"));
                let aus = streams.iter().find(|s| s.get("codec_type").and_then(|x| x.as_str()) == Some("audio"));
                let rate = vs.and_then(|s| s.get("avg_frame_rate")).and_then(|x| x.as_str()).unwrap_or("0/0");
                let fps = rate.split_once('/').and_then(|(a,b)| a.parse::<f64>().ok().zip(b.parse::<f64>().ok()))
                    .and_then(|(a,b)| if b > 0.0 { Some((a / b * 100.0).round() / 100.0) } else { None });
                probe = serde_json::json!({
                    "ok": vs.is_some(),
                    "duration": raw.get("format").and_then(|f| f.get("duration")).and_then(|x| x.as_str()).and_then(|x| x.parse::<f64>().ok()),
                    "video": {"codec": vs.and_then(|s| s.get("codec_name")).and_then(|x| x.as_str()).unwrap_or("—"),
                        "width": vs.and_then(|s| s.get("width")).and_then(|x| x.as_i64()), "height": vs.and_then(|s| s.get("height")).and_then(|x| x.as_i64()),
                        "fps": fps, "aspect": vs.and_then(|s| s.get("display_aspect_ratio")).and_then(|x| x.as_str()).unwrap_or("—")},
                    "audio": {"codec": aus.and_then(|s| s.get("codec_name")).and_then(|x| x.as_str()).unwrap_or("Tidak ada")}
                });
            }
        } else { probe = serde_json::json!({"ok": false, "error": String::from_utf8_lossy(&out.stderr).trim()}); }
    }
    Ok(serde_json::json!({
        "ok": true, "path": path, "name": p.file_name().and_then(|x| x.to_str()).unwrap_or("video"),
        "size": meta.len(), "modified": modified, "extension": p.extension().and_then(|x| x.to_str()).unwrap_or("video"),
        "probe": probe, "annotation": video_annotation_for(&path),
    }))
}

#[tauri::command]
fn video_open(path: String) -> Result<serde_json::Value, String> {
    let p = checked_video_path(&path)?;
    Command::new("rundll32.exe").arg("url.dll,FileProtocolHandler").arg(&p)
        .spawn().map_err(|e| e.to_string())?;
    log_activity("video-open", &p.to_string_lossy());
    Ok(serde_json::json!({"ok": true}))
}

#[tauri::command]
fn video_show_folder(path: String) -> Result<serde_json::Value, String> {
    let p = checked_video_path(&path)?;
    Command::new("explorer.exe").arg(format!("/select,{}", p.to_string_lossy()))
        .spawn().map_err(|e| e.to_string())?;
    Ok(serde_json::json!({"ok": true}))
}

fn move_video_file(source: &PathBuf, target: PathBuf, action: &str) -> Result<serde_json::Value, String> {
    if target.exists() { return Err("file tujuan sudah ada".into()); }
    std::fs::rename(source, &target).map_err(|e| e.to_string())?;
    let path = target.to_string_lossy().into_owned();
    log_activity(action, &format!("{} -> {}", source.to_string_lossy(), path));
    Ok(serde_json::json!({"ok": true, "path": path}))
}

#[tauri::command]
fn video_rename(path: String, new_name: String) -> Result<serde_json::Value, String> {
    let source = checked_video_path(&path)?;
    if new_name.is_empty() || new_name.contains(['\\', '/', ':', '*', '?', '"', '<', '>', '|']) {
        return Err("nama file tidak valid".into());
    }
    let mut name = new_name;
    if PathBuf::from(&name).extension().is_none() {
        if let Some(ext) = source.extension().and_then(|x| x.to_str()) { name.push('.'); name.push_str(ext); }
    }
    let target = source.parent().ok_or("folder sumber tidak ada")?.join(name);
    move_video_file(&source, target, "video-rename")
}

#[tauri::command]
fn video_move(path: String, destination: String) -> Result<serde_json::Value, String> {
    let source = checked_video_path(&path)?;
    let folder = PathBuf::from(destination);
    if !folder.is_dir() { return Err("folder tujuan tidak ditemukan".into()); }
    let target = folder.join(source.file_name().ok_or("nama file tidak valid")?);
    move_video_file(&source, target, "video-move")
}

#[tauri::command]
fn video_quarantine(path: String) -> Result<serde_json::Value, String> {
    let source = checked_video_path(&path)?;
    let folder = source.parent().ok_or("folder sumber tidak ada")?.join("99_To-Delete");
    std::fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
    let mut target = folder.join(source.file_name().ok_or("nama file tidak valid")?);
    let mut n = 1;
    while target.exists() {
        let stem = source.file_stem().and_then(|x| x.to_str()).unwrap_or("video");
        let ext = source.extension().and_then(|x| x.to_str()).map(|x| format!(".{x}")).unwrap_or_default();
        target = folder.join(format!("{stem}-{n}{ext}")); n += 1;
    }
    move_video_file(&source, target, "video-quarantine")
}

#[tauri::command]
fn video_save_annotation(path: String, tags: Vec<String>, note: String) -> Result<serde_json::Value, String> {
    let p = checked_video_path(&path)?;
    let key = p.to_string_lossy().into_owned();
    let store = video_annotation_path();
    if let Some(parent) = store.parent() { std::fs::create_dir_all(parent).map_err(|e| e.to_string())?; }
    let mut all: serde_json::Map<String, serde_json::Value> = std::fs::read_to_string(&store).ok()
        .and_then(|s| serde_json::from_str(&s).ok()).unwrap_or_default();
    all.insert(key.clone(), serde_json::json!({"tags": tags, "note": note}));
    std::fs::write(store, serde_json::to_string_pretty(&all).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    log_activity("video-annotation", &key);
    Ok(serde_json::json!({"ok": true}))
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            core_scan, core_duplicates, core_move_approved, core_stats, ai_engine,
            ai_reason, ai_recommend, docs_list, app_info, job_enqueue, job_claim,
            job_finish, activity_list, activity_clear, db_state, db_set_enabled,
            activity_export, report_export,
            core_doctor, audit_list, job_list, job_pause, job_resume, job_cancel,
            prop_propose, prop_list, prop_preview, prop_approve, prop_reject,
            videos_list, org_run,
            video_inspect, video_open, video_show_folder, video_rename, video_move,
            video_quarantine, video_save_annotation
        ])
        .run(tauri::generate_context!())
        .expect("Tauri gagal jalan");
}
