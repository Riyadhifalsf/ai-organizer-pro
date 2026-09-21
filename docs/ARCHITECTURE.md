# AIOrganizer — Architecture

Production-grade desktop organizer (Windows). Local only. **Never deletes.**

## Layers

```
aiorganizer.exe (CLI today; Qt GUI later consumes the same core lib)
        |
   aiorg_core (static lib, no GUI, no Python)
   ├── database/  SQLite index (WAL). Schema versioned (user_version).
   ├── filesystem/ UTF-8 path layer. NO narrow std::filesystem conversions
   │                  on Windows (MSVC ANSI conversion crashed: 0xC0000409,
   │                  and corrupts CJK names). Wide APIs + explicit UTF-8.
   ├── scanner/   Single traversal thread, batched commits, SKIP/RESCAN/PROCESS
   │              vs index, pause/cancel, progress+error callbacks.
   ├── hashing/   size -> quick(64K) -> partial(1M) -> full SHA-256 (BCrypt).
   │              Per-stage SQLite cache keyed (path,size,mtime).
   ├── duplicate/ (next) groups by (size,hash); display + approved MOVE only.
   ├── video/     (next) libav* native; NORMAL/LIGHT_BROKEN/HEAVY_BROKEN; MOVE.
   ├── organizer/ (next) Scan->Analyze->Propose->Preview->Approve->MOVE->index.
   ├── jobs/      (next) priority queue, cancellation, retry, resume.
   ├── metadata/  (next) fast header parsing.
   └── ai/        (next) ONNX vision (own module) + llama.cpp LLM (own module).
```

## Key invariants

1. DB stores UTF-8 generic paths (`C:/x/y`). All fs calls use wide paths.
2. Gone-detection is clock-granularity-proof: `cutoff = MAX(last_seen)` under
   root; seen rows stamped `max(now, cutoff+1)`; gone = `last_seen <= cutoff`.
3. Hashing never re-reads unchanged files (stage cache). Full SHA-256 only for
   candidates that survived size+quick+partial.
4. MOVE uses native rename when same filesystem (no re-read of 20 GB files).
   Every MOVE logged with source/dest/timestamp/status/rollback info.
5. One CRT (/MD) everywhere. All third-party built from source in-tree.
6. Errors never abort a run: counted, logged to DB, surfaced to GUI.

## Measured (this machine, Release)

- 48,287 files full scan: ~29 s (~1,700 f/s incl. NTFS identity + SQLite).
- Rescan unchanged: ~3.7 s, 100% SKIP, ~0 disk reads of content.
- 12 GoogleTest cases green (scanner, UTF-8/CJK regression, hashing, cache).
