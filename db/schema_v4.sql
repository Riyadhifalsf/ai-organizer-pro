-- schema_v4.sql — database terpadu AIOrganizerPro (SQLite, WAL).
-- Dibuat otomatis oleh core C++ saat open(); file ini = referensi + dipakai
-- tools/migrate_unified.py untuk menggabungkan behavior.db lama.
-- user_version = 4. Tidak menyimpan isi file, hanya metadata + hasil AI.
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE,
  filename TEXT NOT NULL, extension TEXT NOT NULL,
  size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
  volume_serial INTEGER NOT NULL DEFAULT 0,
  file_index INTEGER NOT NULL DEFAULT 0,
  file_type TEXT NOT NULL DEFAULT '',
  hash_status TEXT NOT NULL DEFAULT 'pending',
  scan_status TEXT NOT NULL DEFAULT 'new',
  ai_status TEXT NOT NULL DEFAULT 'pending',
  last_seen_ms INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_files_size ON files(size);
CREATE INDEX IF NOT EXISTS idx_files_scan ON files(scan_status);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash_status);
CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type);

CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, root TEXT NOT NULL,
  started_ms INTEGER NOT NULL, ended_ms INTEGER NOT NULL DEFAULT 0,
  summary TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS errors(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL, stage TEXT NOT NULL,
  path TEXT NOT NULL, message TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_errors_stage ON errors(stage);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hashes(
  path TEXT PRIMARY KEY, size INTEGER NOT NULL, sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hash_stages(
  path TEXT NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
  stage INTEGER NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(path, stage));
CREATE INDEX IF NOT EXISTS idx_hash_stages ON hash_stages(stage, sha256);

-- v3: duplikat (grup confirmed, member aktif; move menghapus baris member).
CREATE TABLE IF NOT EXISTS duplicate_groups(
  id INTEGER PRIMARY KEY, size INTEGER NOT NULL,
  sha256 TEXT NOT NULL DEFAULT '', created_ms INTEGER NOT NULL,
  UNIQUE(size, sha256));
CREATE TABLE IF NOT EXISTS dupe_members(
  group_id INTEGER NOT NULL REFERENCES duplicate_groups(id) ON DELETE CASCADE,
  path TEXT NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
  PRIMARY KEY(group_id, path));
CREATE INDEX IF NOT EXISTS idx_dupe_members_path ON dupe_members(path);

-- v3: audit semua move (rollback = cara mengembalikan).
CREATE TABLE IF NOT EXISTS moves(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL,
  group_id INTEGER NOT NULL DEFAULT 0, src TEXT NOT NULL, dst TEXT NOT NULL,
  size INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'moved',
  rollback TEXT NOT NULL DEFAULT '');

-- v3: antrean kerja (GUI/daemon klaim via ClaimJob atomik).
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending', created_ms INTEGER NOT NULL,
  started_ms INTEGER NOT NULL DEFAULT 0, ended_ms INTEGER NOT NULL DEFAULT 0,
  result TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, id);

-- v3: perilaku (mirror dari engine-py Behavior; t_ms milidetik epoch).
CREATE TABLE IF NOT EXISTS behavior_events(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL, kind TEXT NOT NULL,
  path TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_behavior_kind ON behavior_events(kind, t_ms);
CREATE TABLE IF NOT EXISTS behavior_prefs(key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- v3: hasil Dokumen AI (diisi sidecar dari doc_report_*.csv).
CREATE TABLE IF NOT EXISTS doc_index(
  path TEXT PRIMARY KEY, kategori TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0, ringkasan TEXT NOT NULL DEFAULT '',
  saran_nama TEXT NOT NULL DEFAULT '', updated_ms INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_doc_kat ON doc_index(kategori);
CREATE TABLE IF NOT EXISTS doc_feedback(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL, path TEXT NOT NULL,
  kategori TEXT NOT NULL, teks_hash TEXT NOT NULL DEFAULT '');

-- v4: proposal organizer (master #150: list/preview/approve) + audit + checkpoint.
CREATE TABLE IF NOT EXISTS proposals(
  id INTEGER PRIMARY KEY, created_ms INTEGER NOT NULL,
  batch TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'move',
  action TEXT NOT NULL DEFAULT 'move', group_id INTEGER NOT NULL DEFAULT 0,
  src TEXT NOT NULL, dst TEXT NOT NULL,
  reasons TEXT NOT NULL DEFAULT '', risk TEXT NOT NULL DEFAULT 'low',
  status TEXT NOT NULL DEFAULT 'pending');
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status, batch);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, src TEXT NOT NULL DEFAULT '',
  dst TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT 'ok',
  detail TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, t_ms);
CREATE TABLE IF NOT EXISTS job_checkpoints(
  job_id INTEGER PRIMARY KEY, state TEXT NOT NULL DEFAULT '',
  updated_ms INTEGER NOT NULL DEFAULT 0);

PRAGMA user_version=4;
