#!/usr/bin/env python3
"""ai/jobs.py — antrean kerja dalam JSON (data/jobs.json, tanpa database).

Bentuk mirror perintah core (job-enqueue/claim/finish/list/pause/resume)
agar pemanggil (Qt) tak perlu berubah bentuk. Status: pending, running,
paused, done, failed, cancelled. Tulis atomik (tmp + replace).
"""
import json
import os
import subprocess
import sys
import time

JOBS_NAME = os.path.join("data", "jobs.json")
VALID = ("pending", "running", "paused", "done", "failed", "cancelled")


def _root(app_base):
    cur = os.path.abspath(app_base)
    for _ in range(7):
        if os.path.isfile(os.path.join(cur, "PRO.cmd")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(app_base)


def _path(app_base):
    return os.path.join(_root(app_base), JOBS_NAME)


def _load(app_base):
    try:
        with open(_path(app_base), encoding="utf-8") as f:
            d = json.load(f)
            if isinstance(d, dict) and isinstance(d.get("jobs"), list):
                d.setdefault("next_id", 1)
                return d
    except (OSError, ValueError):
        pass
    return {"next_id": 1, "jobs": []}


def _save(app_base, state):
    p = _path(app_base)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, p)


def enqueue(app_base, kind, payload=""):
    st = _load(app_base)
    job = {"id": int(st.get("next_id", 1)), "kind": str(kind or "scan"),
           "payload": str(payload or ""), "status": "pending",
           "created": int(time.time()), "started": 0, "ended": 0, "result": ""}
    st["jobs"].append(job)
    st["next_id"] = job["id"] + 1
    _save(app_base, st)
    return {"ok": True, "id": job["id"]}


def claim(app_base):
    st = _load(app_base)
    pend = [j for j in st["jobs"] if j.get("status") == "pending"]
    pend.sort(key=lambda j: (j.get("created", 0), j.get("id", 0)))
    if not pend:
        return {"ok": False}
    job = pend[0]
    job["status"] = "running"
    job["started"] = int(time.time())
    _save(app_base, st)
    return {"ok": True, "id": job["id"], "kind": job["kind"],
            "payload": job["payload"]}


def finish(app_base, job_id, status="done", result=""):
    if status not in VALID:
        status = "done"
    st = _load(app_base)
    for j in st["jobs"]:
        if j.get("id") == int(job_id):
            j["status"] = status
            j["ended"] = int(time.time())
            j["result"] = str(result or "")[:4000]
            _save(app_base, st)
            return {"ok": True}
    return {"ok": False, "error": "job tidak ada"}


def set_status(app_base, job_id, status):
    st = _load(app_base)
    for j in st["jobs"]:
        if j.get("id") == int(job_id):
            cur = j.get("status")
            allowed = {"pause": ("pending", "running"),
                       "resume": ("paused",),
                       "cancel": ("pending", "running", "paused")}
            if cur not in allowed.get(status, ()):
                return {"ok": False,
                        "error": f"status {cur} tak bisa di-{status}"}
            j["status"] = {"pause": "paused", "resume": "pending",
                           "cancel": "cancelled"}[status]
            j["ended"] = int(time.time()) if j["status"] == "cancelled" else j.get("ended", 0)
            _save(app_base, st)
            return {"ok": True}
    return {"ok": False, "error": "job tidak ada"}


def list_jobs(app_base, status="", limit=50):
    st = _load(app_base)
    jobs = sorted(st["jobs"], key=lambda j: -j.get("id", 0))
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    return {"ok": True, "jobs": jobs[:max(1, min(int(limit or 50), 500))]}


def _core_bin(app_base):
    root = _root(app_base)
    for c in (os.path.join(root, "aiorganizer.exe"),
              os.path.join(root, "build", "src", "aiorganizer.exe")):
        if os.path.isfile(c):
            return c
    return "aiorganizer"


def _db(app_base):
    env = os.environ.get("AIORG_DB", "").strip()
    if env:
        return env
    return os.path.join(_root(app_base), "data", "aiorganizer.db")


def _run_core(app_base, args, timeout=1800):
    try:
        p = subprocess.run(
            [_core_bin(app_base)] + args, capture_output=True, text=True,
            errors="replace", timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = (p.stdout or "").strip().splitlines()
        for line in reversed(out):
            try:
                return json.loads(line)
            except ValueError:
                continue
        return {"ok": p.returncode == 0, "raw": (p.stdout or "")[-2000:]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def run_once(app_base, engine_fn):
    """Ambil 1 job pending -> eksekusi -> finish. engine_fn(argv)->dict."""
    claimed = claim(app_base)
    if not claimed.get("ok"):
        return {"ok": True, "ran": False, "message": "tidak ada job pending"}
    jid, kind = claimed["id"], claimed.get("kind", "")
    try:
        payload = json.loads(claimed.get("payload") or "{}")
    except ValueError:
        payload = {"value": claimed.get("payload") or ""}
    try:
        if kind in ("scan", "duplicates"):
            folder = payload.get("folder") or payload.get("root") or payload.get("value")
            if not folder:
                raise RuntimeError(f"payload {kind} harus punya folder/root")
            args = [kind, folder, "--db", _db(app_base), "--json",
                    "--actor", "gui"]
            if kind == "duplicates":
                args += ["--min-size", str(payload.get("min_size", 1)),
                         "--workers", "4"]
            res = _run_core(app_base, args)
        elif kind in ("ai", "organize"):
            argv = payload.get("argv")
            if not argv and kind == "organize" and payload.get("folder"):
                argv = ["organize-videos", payload["folder"], "--dry-run"]
            if not argv:
                raise RuntimeError("payload harus punya argv[]")
            argv = list(argv)
            if "--out" not in argv:
                argv += ["--out", _root(app_base)]
            res = engine_fn(argv) or {}
        else:
            raise RuntimeError(f"jenis job tak didukung: {kind}")
        ok = bool(res.get("ok", True))
        finish(app_base, jid, "done" if ok else "failed",
               json.dumps(res, ensure_ascii=False)[:4000])
        return {"ok": ok, "ran": True, "id": jid, "kind": kind, "result": res}
    except Exception as e:
        finish(app_base, jid, "failed", str(e)[:1000])
        return {"ok": False, "ran": True, "id": jid, "kind": kind,
                "error": str(e)[:500]}


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../..")
    from app.ai import jobs as _j  # noqa: F401  (self-check import)
    print("jobs.py OK")
