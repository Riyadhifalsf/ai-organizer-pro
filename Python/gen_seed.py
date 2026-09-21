import json, os
BASE = r"D:\development\project-coding\aplication-japanese-language-study\backend\data"
OUT = r"D:\development\project-coding\databases\japanese-study-seed.sql"

def jt(*parts):
    out = []
    for p in parts:
        if not p:
            continue
        if isinstance(p, list):
            p = " ".join(str(x) for x in p if x)
        s = str(p).strip()
        if s:
            out.append(s)
    return " ".join(out).lower()

def sq(v):
    """SQL string literal escape."""
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"

def jq(obj):
    """JSONB literal: '...'::jsonb with escaping."""
    s = json.dumps(obj, ensure_ascii=False)
    return "'" + s.replace("'", "''") + "'::jsonb"

lines = []
lines.append("-- Japanese Study seed data (generated from backend/data JSON)")
lines.append("-- Restore di server: psql -U japanese_study -d japanese_study -f japanese-study-seed.sql")
lines.append("-- Aman diulang: semua INSERT pakai ON CONFLICT DO NOTHING.")
lines.append("")

def emit(table, cols, rows, conflict):
    # rows: list of tuple of SQL literals
    BATCH = 500
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i+BATCH]
        vals = ",".join("(" + ",".join(r) + ")" for r in batch)
        lines.append(f"INSERT INTO {table} ({','.join(cols)}) VALUES {vals} ON CONFLICT {conflict} DO NOTHING;")

# --- kanji ---
d = json.load(open(os.path.join(BASE, "kanji.json"), encoding="utf-8"))
rows = []
for e in d:
    search = jt(e.get("char"), e.get("meaning"), e.get("on"), e.get("kun"), e.get("themes"))
    rows.append((str(int(e["id"])), sq(e.get("level") or "N5"), sq(search), jq(e)))
emit("content_kanji", ["id", "level", "search_text", "raw"], rows, "(id)")
print(f"kanji: {len(rows)}")

# --- vocabulary (content + vocabularies) ---
d = json.load(open(os.path.join(BASE, "vocabulary.json"), encoding="utf-8"))
rows = []
vrows = []
for e in d:
    search = jt(e.get("word"), e.get("reading"), e.get("meaning"))
    rows.append((str(int(e["id"])), sq(e.get("level") or "N5"), sq(e.get("word") or ""),
                 sq(e.get("reading") or ""), sq(e.get("meaning") or ""), sq(search), jq(e)))
    vrows.append((sq(e.get("word") or ""), sq(e.get("reading") or ""), sq(e.get("meaning") or ""), sq(e.get("level") or "N5")))
emit("content_vocabulary", ["id", "level", "word", "reading", "meaning", "search_text", "raw"], rows, "(id)")
# vocabularies has BIGSERIAL id so no conflict target on id; use DO NOTHING without target is invalid -> use ON CONFLICT DO NOTHING requires inference; table has no unique except id, so just plain INSERT guarded by count check
lines.append("-- vocabularies: only insert when empty (seed.js behaviour)")
lines.append("DO $$ BEGIN IF (SELECT count(*) FROM vocabularies) = 0 THEN")
BATCH = 500
for i in range(0, len(vrows), BATCH):
    batch = vrows[i:i+BATCH]
    vals = ",".join("(" + ",".join(r) + ")" for r in batch)
    lines.append(f"  INSERT INTO vocabularies (word,reading,meaning,level) VALUES {vals};")
lines.append("END IF; END $$;")
print(f"vocabulary: {len(rows)}")

# --- grammar ---
d = json.load(open(os.path.join(BASE, "grammar.json"), encoding="utf-8"))
rows = []
for e in d:
    search = jt(e.get("pattern"), e.get("title"), e.get("explanation"))
    rows.append((sq(str(e["id"])), sq(e.get("level") or "N5"), sq(e.get("pattern") or ""), sq(search), jq(e)))
emit("content_grammar", ["id", "level", "pattern", "search_text", "raw"], rows, "(id)")
print(f"grammar: {len(rows)}")

# --- phrases ---
d = json.load(open(os.path.join(BASE, "phrases.json"), encoding="utf-8"))
rows = []
for e in d:
    search = jt(e.get("category"), e.get("japanese"), e.get("reading"), e.get("meaning"), e.get("politeness"), e.get("note"), e.get("tags"))
    rows.append((sq(str(e["id"])), sq(e.get("category") or ""), sq(search), jq(e)))
emit("content_phrases", ["id", "category", "search_text", "raw"], rows, "(id)")
print(f"phrases: {len(rows)}")

# --- sentences ---
d = json.load(open(os.path.join(BASE, "sentences.json"), encoding="utf-8"))
rows = []
for e in d:
    search = jt(e.get("level"), e.get("category"), e.get("japanese"), e.get("reading"), e.get("meaning"), e.get("pattern"), e.get("note"))
    rows.append((sq(str(e["id"])), sq(e.get("level") or "N5"), sq(e.get("category") or ""), sq(search), jq(e)))
emit("content_sentences", ["id", "level", "category", "search_text", "raw"], rows, "(id)")
print(f"sentences: {len(rows)}")

# --- culture ---
d = json.load(open(os.path.join(BASE, "culture.json"), encoding="utf-8"))
rows = []
for e in d:
    search = jt(e.get("category"), e.get("title"), e.get("summary"), e.get("detail"), e.get("example"), e.get("tips"))
    rows.append((sq(str(e["id"])), sq(e.get("category") or ""), sq(search), jq(e)))
emit("content_culture", ["id", "category", "search_text", "raw"], rows, "(id)")
print(f"culture: {len(rows)}")

# --- readings ---
d = json.load(open(os.path.join(BASE, "readings.json"), encoding="utf-8"))
rows = []
for e in d:
    search = jt(e.get("level"), e.get("category"), e.get("title"), e.get("japanese"), e.get("reading"), e.get("meaning"))
    rows.append((sq(str(e["id"])), sq(e.get("level") or "N5"), sq(e.get("category") or ""), sq(search), jq(e)))
emit("content_readings", ["id", "level", "category", "search_text", "raw"], rows, "(id)")
print(f"readings: {len(rows)}")

# --- admin seed (same as seed.js) ---
lines.append("-- admin seed")
lines.append("INSERT INTO admin_users (id,name,email,role,level,online,created_at) VALUES ('u-admin','Administrator','admin@example.com','admin','N1',true,now()),('u-001','User Pertama','user@example.com','user','N5',false,now()) ON CONFLICT (id) DO NOTHING;")
lines.append("INSERT INTO admin_activities (id,label,type,created_at) VALUES ('act-1','Dashboard admin dibuat','system',now()) ON CONFLICT (id) DO NOTHING;")

open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("WROTE", OUT, os.path.getsize(OUT))
