 # AIOrganizer — Master Documentation, Architecture, Roadmap, Setup, and Development Plan

> **Project name:** AIOrganizer  
> **Current core version:** `0.1.0`  
> **Document role:** single source of truth for architecture, setup, dependencies, development order, testing, performance, safety, and long-term expansion  
> **Primary target:** Windows 10/11 x64 desktop application  
> **Primary implementation language:** C++20  
> **UI direction:** Qt 6 / Qt Quick (QML) over the same native core  
> **Core principle:** local-first, safe-by-default, modular, incremental, resumable, storage-aware, and extensible  
> **Data safety principle:** never delete files automatically; destructive operations must not be part of the default workflow

---

## 1. Tujuan dokumen ini

Dokumen ini sengaja dibuat sebagai **satu file dokumentasi induk**. Semua penjelasan besar yang dibutuhkan untuk melanjutkan pengembangan AIOrganizer dikumpulkan di sini agar proyek tidak berubah menjadi kumpulan catatan yang tersebar di banyak file.

Dokumen ini berisi:

- kondisi proyek saat ini;
- apa yang sudah benar-benar tersedia di source code;
- apa yang masih berupa rancangan;
- arsitektur target jangka panjang;
- pembagian modul dan tanggung jawabnya;
- bahasa pemrograman yang digunakan dan alasan pemilihannya;
- dependency wajib, dependency opsional, dan dependency masa depan;
- setup development machine;
- build, test, benchmark, dan troubleshooting;
- desain database dan aturan migrasi;
- desain scanner, hashing, duplicate detection, metadata, video, AI, job system, organizer, dan GUI;
- strategi performa untuk HDD, SATA SSD, NVMe, dan koleksi file yang sangat besar;
- strategi recovery dan crash-safety;
- strategi packaging/release;
- security dan privacy model;
- roadmap implementasi bertahap;
- aturan engineering agar aplikasi bisa bertambah fitur tanpa membongkar fondasi.

Dokumen ini membedakan secara tegas antara **IMPLEMENTED**, **PARTIALLY IMPLEMENTED**, dan **PLANNED**. Jangan menganggap sesuatu sebagai selesai hanya karena modulnya sudah disebut di architecture.

---

## 2. Status proyek saat ini

### 2.1 Yang sudah tersedia

Komponen yang benar-benar ada di source saat dokumen ini dibuat:

| Komponen | Status | Keterangan |
|---|---|---|
| C++ core library | IMPLEMENTED | `aiorg_core` static library |
| CLI | IMPLEMENTED | `scan`, `hash`, `version` |
| SQLite database | IMPLEMENTED | local metadata/index database |
| SQLite WAL | IMPLEMENTED | WAL + `synchronous=NORMAL` |
| Schema migration | IMPLEMENTED | `PRAGMA user_version` |
| Filesystem UTF-8 layer | IMPLEMENTED | UTF-8 metadata + wide Windows filesystem calls |
| Recursive scanner | IMPLEMENTED | recursive traversal + metadata |
| Skip directory rules | IMPLEMENTED | termasuk `$RECYCLE.BIN` dan `System Volume Information` |
| Incremental scan | IMPLEMENTED | new / changed / unchanged |
| Gone detection | IMPLEMENTED | memakai `last_seen_ms` dan cutoff |
| Pause/cancel signaling | IMPLEMENTED | atomic flags |
| Quick hash | IMPLEMENTED | 64 KiB |
| Partial hash | IMPLEMENTED | 1 MiB |
| Full SHA-256 | IMPLEMENTED | BCrypt pada Windows |
| Hash cache | IMPLEMENTED | per-stage cache di SQLite |
| Hash worker pool | IMPLEMENTED | 1–8 workers |
| Error logging | IMPLEMENTED | DB + callback |
| GoogleTest suite | IMPLEMENTED | scanner, UTF-8, hashing, cache, cancellation |
| Benchmarks source area | PRESENT | perlu terus dikembangkan |
| Duplicate engine | PLANNED | belum implemented |
| Metadata extraction | PLANNED | belum implemented |
| Video analyzer | PLANNED | belum implemented |
| AI vision classifier | PLANNED | belum implemented |
| LLM module | PLANNED | belum implemented |
| Job manager | PLANNED | belum implemented |
| Organizer/move engine | PLANNED | belum implemented |
| Qt GUI | PLANNED | belum implemented |

### 2.2 Kesimpulan status

Proyek saat ini lebih tepat disebut:

> **AIOrganizer Core / Foundation 0.1.0**

bukan aplikasi AI Organizer final.

Fondasi filesystem, indexing, scanner, staged hashing, dan cache sudah ada. Lapisan yang mengubah engine ini menjadi organizer pintar masih harus dibangun secara modular.

---

## 3. Visi akhir aplikasi

Target aplikasi bukan sekadar program pencari duplicate.

Target jangka panjang adalah desktop organizer yang dapat:

1. mengindeks file secara cepat;
2. memahami perubahan file tanpa melakukan scan berat berulang-ulang;
3. mengelompokkan file berdasarkan hash dan similarity;
4. membaca metadata;
5. memeriksa media yang rusak;
6. mengenali kategori konten dengan model vision;
7. memakai model bahasa untuk membantu penjelasan, klasifikasi, atau pembuatan proposal organizer;
8. memberikan proposal tindakan yang bisa direview;
9. memindahkan/rename file dengan aman;
10. melanjutkan pekerjaan setelah restart;
11. membatalkan pekerjaan tanpa merusak state;
12. menjaga database tetap konsisten dengan filesystem;
13. bekerja offline/local-first;
14. memisahkan engine inti dari GUI dan model AI;
15. memungkinkan fitur baru ditambahkan tanpa membongkar sistem lama.

Prinsip utamanya:

```text
Filesystem
    ↓
Index
    ↓
Analyze
    ↓
Evidence
    ↓
Proposal
    ↓
Preview
    ↓
User Approval
    ↓
Action
    ↓
Verify
    ↓
Update Index
```

Jangan mengubah alur menjadi:

```text
AI → langsung memindahkan file
```

AI harus menghasilkan **evidence + confidence + alasan + proposal**, bukan hak mutlak untuk mengubah filesystem.

---

# 4. Prinsip engineering utama

## 4.1 Local-first

Aplikasi harus bisa bekerja tanpa server cloud. Database lokal, hashing, metadata, duplicate detection, dan model lokal harus bisa dijalankan tanpa mengirim isi file ke internet.

Network hanya boleh menjadi fitur tambahan, bukan ketergantungan inti.

## 4.2 Safe-by-default

Default behavior:

- tidak menghapus file;
- tidak menimpa file tanpa pemeriksaan;
- tidak overwrite destination tanpa policy eksplisit;
- tidak memindahkan file hanya berdasarkan klasifikasi AI tanpa review;
- menyimpan audit log untuk setiap tindakan;
- melakukan verification setelah move/copy;
- dapat melakukan rollback metadata/plan bila operasi belum sepenuhnya committed.

## 4.3 Idempotent

Menjalankan scan dua kali dengan state yang sama harus menghasilkan hasil yang sama, dan scan kedua tidak boleh membaca ulang isi file tanpa alasan.

## 4.4 Incremental

Perubahan kecil tidak boleh menyebabkan seluruh dataset diproses ulang.

## 4.5 Resumable

Job panjang seperti hashing jutaan file atau AI classification harus bisa dilanjutkan setelah:

- restart aplikasi;
- crash;
- pause;
- cancel;
- sleep/hibernate;
- drive sementara unavailable.

## 4.6 Storage-aware

Bottleneck utama organizer file besar sering kali I/O, bukan CPU.

Karena itu worker count tidak boleh sekadar mengikuti jumlah core CPU.

## 4.7 Evidence before action

Semua keputusan organizer harus memiliki data pendukung.

Contoh duplicate exact:

```text
same size
+ same full SHA-256
= exact duplicate candidate
```

Contoh image similarity:

```text
same visual embedding region
+ perceptual similarity
+ metadata context
= similar image candidate
```

## 4.8 Modular

Modul tidak boleh mengetahui detail implementasi modul lain lebih dari yang diperlukan.

Target dependency graph:

```text
                 ┌─────────────┐
                 │ filesystem  │
                 └──────┬──────┘
                        │
      ┌─────────────────┼─────────────────┐
      │                 │                 │
   scanner            hashing          metadata
      │                 │                 │
      └────────────┬────┴─────┬───────────┘
                   │          │
               database    duplicate
                   │          │
                   └────┬─────┘
                        │
                     analysis
                   ┌────┴────┐
                   │         │
                 AI        video
                   │         │
                   └────┬────┘
                        │
                    organizer
                        │
                     jobs
                        │
                       GUI
```

GUI tidak boleh menjadi tempat logic scanner, hashing, database, atau move.

---

# 5. Struktur proyek saat ini

Struktur source penting:

```text
AIOrganizer/
├── CMakeLists.txt
├── ARCHITECTURE.md
├── BUILD.md
├── AIOrganizer_MASTER_DOCUMENTATION.md
│
├── src/
│   ├── CMakeLists.txt
│   ├── main.cpp
│   │
│   └── core/
│       ├── database/
│       ├── filesystem/
│       ├── scanner/
│       ├── hashing/
│       ├── duplicate/       # planned
│       ├── metadata/        # planned
│       ├── video/           # planned
│       ├── organizer/       # planned
│       └── jobs/             # planned
│
├── ai/
│   ├── classifier/          # planned
│   ├── vision/              # planned
│   └── llm/                 # planned
│
├── gui/                      # future Qt/QML application
│
├── tests/
├── benchmarks/
├── resources/
│
└── third_party/
    ├── sqlite-src/
    ├── googletest/
    └── spdlog/
```

**Catatan:** folder planned boleh belum memiliki source. Struktur folder adalah target arsitektur, bukan tanda bahwa fitur tersebut sudah selesai.

---

# 6. Bahasa pemrograman yang dibutuhkan

## 6.1 C++20 — WAJIB / bahasa utama

C++20 digunakan untuk:

- filesystem engine;
- scanner;
- database layer;
- hashing;
- worker/job engine;
- duplicate engine;
- metadata parser;
- video integration;
- AI inference adapter;
- organizer/action engine;
- CLI;
- integration layer dengan Qt.

Alasan:

- native performance;
- kontrol I/O;
- Windows API access;
- multithreading;
- memory control;
- integrasi library native seperti SQLite, FFmpeg, ONNX Runtime, dan llama.cpp;
- dapat membuat core tanpa runtime Python.

Jangan pindahkan core filesystem menjadi Python hanya karena AI nantinya menggunakan Python.

---

## 6.2 QML / JavaScript ringan — UI saja

Untuk GUI Qt Quick, QML digunakan untuk:

- layout;
- animation;
- model/view;
- dashboard;
- progress UI;
- settings;
- preview proposal;
- file detail view.

Business logic tetap di C++.

QML tidak boleh memiliki logic seperti:

```text
scan disk
hash file
move file
write database
run SQL
```

QML hanya meminta service C++ melakukan pekerjaan tersebut.

---

## 6.3 SQL — database schema/query

SQLite menggunakan SQL untuk:

- schema;
- index;
- migration;
- query candidate;
- transaction;
- reporting.

Schema harus versioned.

---

## 6.4 Python — opsional, bukan dependency runtime inti

Python cocok untuk:

- training model;
- dataset preparation;
- benchmark analysis;
- model conversion;
- developer tooling;
- offline evaluation;
- data labeling tools;
- generating fixtures;
- release automation tertentu.

Python **tidak perlu menjadi dependency runtime utama** aplikasi desktop.

Ini penting agar pengguna tidak dipaksa menginstall Python hanya untuk menjalankan AIOrganizer.

---

## 6.5 PowerShell — setup/build Windows

PowerShell cocok untuk:

- environment bootstrap;
- setup toolchain;
- build script;
- packaging;
- smoke test;
- CI helper.

---

## 6.6 Bash — opsional untuk CI/Linux

Dipakai jika project nantinya memiliki:

- Linux CI;
- packaging helper;
- benchmark runner;
- development workstation Linux.

---

# 7. Dependency saat ini

## 7.1 Build toolchain

### Wajib

- Windows 10/11 x64
- MSVC / Visual C++ toolchain
- Windows SDK
- CMake `>= 3.26` karena root `CMakeLists.txt` menetapkan minimum tersebut
- build tool seperti Ninja (direkomendasikan)

### Yang dipakai pada environment build proyek saat ini

Build cache yang sudah ada menunjukkan environment yang pernah digunakan:

```text
MSVC: D:/tools/VS/VC/Tools/MSVC/14.44.35207
Generator: Ninja
CMake: 4.4.3
```

Versi ini adalah **fakta dari build tree yang tersedia**, bukan keharusan untuk semua mesin.

Prinsip penting: gunakan satu toolchain C++ yang konsisten untuk seluruh build release, terutama CRT/runtime.

---

## 7.2 SQLite

Saat ini SQLite divendorkan ke project:

```text
third_party/sqlite-src/sqlite-amalgamation-3530400/
```

Versi source yang ada adalah **SQLite 3.53.4**.

SQLite sangat cocok untuk aplikasi lokal karena:

- single-file database;
- transactional;
- tidak perlu server;
- mature;
- bisa memakai WAL;
- cocok untuk index lokal.

Jangan menganggap SQLite sebagai tempat penyimpanan isi file. SQLite hanya menyimpan metadata, index, state, job state, analysis result, dan audit information.

---

## 7.3 spdlog

Versi yang terdapat di tree saat ini:

```text
spdlog 1.17.0
```

Perannya:

- structured logging dasar;
- warning/error;
- diagnostic;
- runtime troubleshooting.

Gunakan logging dengan level:

```text
trace
 debug
 info
 warn
 error
 critical
```

Untuk release, hindari logging isi sensitif file secara berlebihan.

---

## 7.4 GoogleTest

Versi vendored:

```text
GoogleTest 1.18.0
```

Digunakan untuk:

- unit test;
- regression test;
- filesystem edge cases;
- hashing test;
- database migration test;
- cancellation test.

---

# 8. Dependency masa depan

Dependency berikut **jangan dipasang semuanya sekarang**. Integrasikan hanya ketika modul yang membutuhkannya sudah akan dibangun.

---

## 8.1 Qt 6 — GUI

Target GUI:

```text
Qt 6
Qt Quick
QML
Qt Core
Qt Gui
Qt Qml
Qt Quick Controls
```

Qt harus hidup di luar core.

Arsitektur:

```text
QML
 ↓
ViewModel / Controller
 ↓
Application Services
 ↓
aiorg_core
```

Qt saat ini menyediakan alur build CMake dan penggunaan `CMAKE_PREFIX_PATH` untuk menemukan instalasi Qt. Gunakan konfigurasi Qt yang cocok dengan MSVC toolchain yang dipakai project. Lihat dokumentasi resmi Qt untuk build berbasis CMake. 

---

## 8.2 FFmpeg — video/audio inspection

FFmpeg direncanakan untuk:

- container detection;
- codec detection;
- duration;
- resolution;
- frame sampling;
- audio stream inspection;
- corruption/error checks;
- thumbnail extraction.

Target penggunaan:

```text
libavformat
libavcodec
libavutil
libswscale
libswresample
```

Jangan memanggil CLI `ffmpeg.exe` untuk setiap file jika native library sudah cukup. Native library mengurangi process spawning dan memberi kontrol lebih baik.

FFmpeg menyediakan source resmi dan menunjuk ke build Windows pihak ketiga seperti BtbN dan gyan.dev untuk binary Windows. Gunakan build yang lisensi dan konfigurasi codec-nya sesuai kebutuhan distribusi aplikasi. 

---

## 8.3 ONNX Runtime — computer vision

ONNX Runtime cocok sebagai inference engine untuk:

- image classification;
- embedding extraction;
- image similarity;
- document classification;
- object detection;
- future multimodal models.

Arsitektur yang disarankan:

```text
ai/vision/
    ModelManager
    Preprocessor
    InferenceSession
    EmbeddingService
    ClassificationService
```

ONNX Runtime menyediakan C++ API dan artifact CPU/GPU untuk Windows/Linux/macOS serta opsi DirectML pada Windows. Pilihan provider sebaiknya diputuskan berdasarkan hardware target, bukan dipaksa aktif pada semua mesin. 

---

## 8.4 llama.cpp — local LLM

llama.cpp digunakan sebagai adapter terpisah untuk model bahasa lokal, bukan untuk menggantikan classifier vision.

Contoh peran LLM:

- merangkum metadata;
- memberi penjelasan klasifikasi;
- menormalkan kategori;
- membantu membuat folder proposal;
- memahami rule organizer dalam bahasa manusia;
- query terhadap index dengan guardrail.

Jangan menggunakan LLM sebagai pengganti hashing.

Jangan menggunakan LLM untuk menentukan exact duplicate.

Jangan memberikan LLM akses file-write langsung.

llama.cpp mendukung build CMake dan konfigurasi CPU/GPU termasuk Windows. Pastikan model dan backend dipisahkan dari application core sehingga pengguna bisa mengganti model tanpa rebuild core. 

---

# 9. Dependency strategy: vendored vs external

Gunakan aturan berikut.

## Vendored

Cocok untuk:

- SQLite;
- small stable libraries;
- dependencies yang ingin build deterministik;
- library tanpa installer kompleks.

## External SDK

Cocok untuk:

- Qt;
- FFmpeg SDK/binaries;
- ONNX Runtime;
- GPU SDK;
- Visual Studio toolchain.

Alasannya ukuran dan update cadence dependency terlalu besar jika selalu dibawa ke repository utama.

## Model files

Model AI **jangan** dimasukkan langsung ke source ZIP.

Model berada di storage terpisah:

```text
models/
    vision/
    embedding/
    llm/
```

Database hanya menyimpan:

- model id;
- version;
- hash;
- path;
- provider;
- input shape;
- preprocessing revision.

---

# 10. Setup development machine — Windows

## 10.1 Prasyarat minimum

Install:

1. Visual Studio / Visual Studio Build Tools dengan workload C++ Desktop Development.
2. CMake.
3. Ninja.
4. Git.
5. Python hanya jika dibutuhkan untuk tooling.

Microsoft mendokumentasikan workload **Desktop development with C++** sebagai workload yang memasang toolchain C++ desktop, termasuk compiler/build components dan Windows SDK yang dibutuhkan. 

---

## 10.2 Folder setup yang disarankan

Gunakan drive dengan ruang yang cukup untuk build dan dependency.

Contoh:

```text
D:\Dev\AIOrganizer\
D:\Tools\VS\
D:\Tools\Qt\
D:\Tools\FFmpeg\
D:\Tools\ONNXRuntime\
D:\Models\AIOrganizer\
D:\Datasets\AIOrganizer\
```

Jangan membuat build directory di folder data yang sedang dianalisis.

---

# 11. Setup toolchain dasar

Contoh konsep setup PowerShell:

```powershell
winget install --id Kitware.CMake --silent
winget install --id Git.Git --silent
python -m pip install --upgrade pip
python -m pip install ninja
```

Install Visual Studio/Build Tools melalui installer resmi Microsoft dan pastikan workload C++ Desktop Development aktif. 

Setelah instalasi, cek:

```powershell
cmake --version
ninja --version
git --version
```

Lalu buka **Developer Command Prompt / Developer PowerShell** dari Visual Studio environment agar MSVC, Windows SDK, linker, dan library path siap digunakan.

---

# 12. Build current core

Dari root project:

```powershell
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

Pada toolchain yang membutuhkan initialization khusus, jalankan perintah dari Developer Command Prompt/PowerShell Visual Studio.

Untuk Debug:

```powershell
cmake -S . -B build-debug -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build-debug
```

---

# 13. Testing

Setelah build:

```powershell
ctest --test-dir build --output-on-failure
```

Atau langsung menjalankan executable test yang dihasilkan.

Target development jangka panjang:

```text
unit tests
+ integration tests
+ filesystem fixtures
+ crash/restart tests
+ performance tests
+ fuzz tests
+ migration tests
+ end-to-end tests
```

---

# 14. Build modes yang harus tersedia

Project target seharusnya memiliki setidaknya:

```text
Debug
RelWithDebInfo
Release
ASan/UBSan experimental
Benchmark
```

### Debug

Untuk debugging logic.

### RelWithDebInfo

Untuk profiling dan laporan crash.

### Release

Untuk user.

### Sanitizer

Digunakan pada CI/development tertentu untuk mendeteksi:

- use-after-free;
- buffer overflow;
- undefined behavior;
- lifetime bug.

### Benchmark

Jangan mengukur performa dari Debug build.

---

# 15. Scanner architecture

Scanner adalah entry point pertama setelah root folder dipilih.

Alur target:

```text
Root
 ↓
Directory traversal
 ↓
Skip-rule check
 ↓
Native stat / file identity
 ↓
Normalize UTF-8 path
 ↓
Metadata snapshot
 ↓
Compare with DB
 ↓
NEW / CHANGED / UNCHANGED
 ↓
Update index
```

Scanner tidak boleh melakukan:

- full SHA-256 untuk semua file;
- AI inference;
- video decode penuh;
- file move;
- delete.

Scanner hanya mengumpulkan state ringan.

---

# 16. Scanner status model

Status dasar:

```text
new
indexed
changed
gone
error
```

Makna:

### new
Belum pernah ada di index.

### indexed
Sudah tercatat dan sesuai dengan snapshot terakhir.

### changed
Metadata berubah sehingga downstream analysis mungkin diperlukan.

### gone
Ada di index tetapi tidak ditemukan pada scan terbaru.

### error
Ada masalah saat membaca metadata atau state file.

---

# 17. File identity

Saat ini database menggunakan:

```text
path
size
mtime_ns
volume_serial
file_index
```

Target berikutnya adalah memperkuat konsep **stable file identity**.

Idealnya satu file memiliki:

```text
file_identity = volume_id + native_file_id
```

sedangkan path adalah atribut yang dapat berubah.

Contoh:

```text
D:\Foto\a.jpg
```

rename menjadi:

```text
D:\Foto\Liburan\a.jpg
```

harus sebisa mungkin dikenali sebagai file yang sama.

Jangan menggunakan path saja sebagai satu-satunya identitas logis jangka panjang jika filesystem menyediakan native file identity.

---

# 18. UTF-8 / Windows filesystem

Aturan penting:

```text
Database / logical model
        ↓
UTF-8
        ↓
Windows adapter
        ↓
UTF-16 / wide API
```

Jangan mengubah path Windows menjadi ANSI untuk melakukan operasi filesystem.

Hal ini penting untuk:

- Jepang;
- China;
- Korea;
- Arab;
- emoji;
- karakter Unicode lainnya.

Regression test CJK yang sudah ada harus tetap dipertahankan selamanya.

---

# 19. Hash architecture

Pipeline saat ini:

```text
metadata/size grouping
        ↓
quick 64 KiB
        ↓
partial 1 MiB
        ↓
full SHA-256
```

Tujuan utama:

> membaca sesedikit mungkin data untuk mendapatkan kepastian yang diperlukan.

---

# 20. Exact duplicate detection

Rule dasar:

```text
same size
    ↓
same quick hash
    ↓
same partial hash
    ↓
same full SHA-256
    ↓
exact duplicate group
```

Tidak boleh langsung menganggap:

```text
same filename = duplicate
```

Tidak boleh juga menganggap:

```text
same size = duplicate
```

Ukuran dan staged hash hanya digunakan sebagai filter.

---

# 21. Duplicate engine target

Modul:

```text
src/core/duplicate/
```

Sub-komponen yang disarankan:

```text
DuplicateIndexer
CandidateGrouper
ExactDuplicateDetector
SimilarityDetector
DuplicatePolicy
DuplicateGroupRepository
DuplicateDecisionEngine
```

Output sebaiknya berupa struktur data, bukan langsung memindahkan file.

Contoh:

```text
Group #1024

canonical candidate:
D:\Photos\2026\a.jpg

candidates:
D:\Downloads\a.jpg
D:\Backup\a.jpg
D:\Temp\a-copy.jpg

reason:
size + full SHA-256 match

confidence:
exact
```

---

# 22. Similar / near-duplicate engine

Exact duplicate berbeda dari similar image.

Untuk gambar:

```text
file A = crop / resize / re-encode dari B
```

SHA-256 akan berbeda.

Karena itu perlu:

- perceptual hash;
- dHash/pHash/aHash;
- image embedding;
- optional OCR similarity;
- metadata context.

Pipeline yang disarankan:

```text
exact duplicate
    ↓
perceptual hash
    ↓
embedding similarity
    ↓
optional semantic classifier
```

Jangan langsung menjalankan embedding AI untuk seluruh jutaan file tanpa candidate reduction.

---

# 23. Metadata engine

Target:

```text
src/core/metadata/
```

Metadata berbeda berdasarkan file class.

## Image

- width;
- height;
- pixel format;
- EXIF;
- camera make/model;
- capture time;
- orientation;
- GPS jika tersedia;
- ICC/profile;
- animation frames jika format mendukung.

## Audio

- duration;
- codec;
- bitrate;
- sample rate;
- channels;
- artist;
- album;
- title;
- date.

## Video

- duration;
- width/height;
- fps;
- codec;
- audio streams;
- subtitle streams;
- bitrate.

## Document

- page count;
- MIME/type;
- title/author jika tersedia;
- text extract summary;
- creation time;
- modification time.

Metadata extractor harus memiliki batas resource agar tidak membaca seluruh isi file jika hanya header yang dibutuhkan.

---

# 24. Video analyzer

Target module:

```text
src/core/video/
```

Gunakan native FFmpeg libraries.

Output minimum:

```text
NORMAL
LIGHT_BROKEN
HEAVY_BROKEN
UNKNOWN
```

Periksa:

- container validity;
- stream discovery;
- codec support;
- timestamp consistency;
- decodeability sample;
- selected frame decode.

Jangan decode seluruh video hanya untuk melakukan smoke test.

Strategi:

```text
header probe
 ↓
stream probe
 ↓
sample decode
 ↓
optional deeper scan
```

---

# 25. Image AI classification

Target module:

```text
src/ai/vision/
```

Tujuan contoh:

```text
photo
anime
illustration
screenshot
document
meme
scan
artwork
UI screenshot
receipt
identity-like document
unknown
```

Kategori harus configurable.

Jangan mengunci kategori sebagai enum permanen di source code jika nantinya user ingin membuat kategori custom.

---

# 26. Vision inference architecture

```text
Image file
   ↓
Image decoder
   ↓
Resize / normalize
   ↓
Model input tensor
   ↓
ONNX Runtime
   ↓
Classification / embedding
   ↓
Postprocessor
   ↓
AI evidence
```

Database menyimpan hasil, bukan runtime session.

Contoh record:

```text
file_id
model_id
model_version
class_id
score
embedding_version
created_at
```

---

# 27. AI confidence rules

AI result jangan hanya:

```text
anime = true
```

Lebih baik:

```text
class = anime
score = 0.93
model = vision-2026-01
preprocess = v3
```

Untuk hasil yang meragukan:

```text
0.51
```

jangan diperlakukan sama dengan:

```text
0.99
```

Gunakan policy threshold configurable.

Contoh:

```text
>= 0.95  → strong suggestion
0.75-0.95 → suggestion
0.50-0.75 → uncertain
< 0.50 → unknown
```

Angka tersebut hanya contoh desain, bukan nilai universal. Threshold harus dievaluasi berdasarkan dataset nyata.

---

# 28. LLM module

LLM berada di:

```text
src/ai/llm/
```

Peran yang cocok:

- natural language explanation;
- metadata summarization;
- user-defined organization rules;
- folder naming proposal;
- semantic search helper;
- query translation menjadi structured filters.

Contoh user:

```text
"pisahkan foto anime tahun 2025 yang duplicate"
```

LLM boleh membantu memetakan menjadi query plan:

```text
content = anime
AND year = 2025
AND exact_duplicate = true
```

Tetapi query yang sebenarnya tetap harus dieksekusi oleh deterministic engine.

---

# 29. LLM safety boundary

LLM tidak boleh punya API seperti:

```text
delete_file(path)
move_file(path)
rename_file(path)
```

secara langsung.

LLM hanya boleh menghasilkan structured intent:

```json
{
  "intent": "find",
  "filters": {
    "type": "anime",
    "year": 2025,
    "duplicate": true
  }
}
```

Application layer memvalidasi hasil tersebut.

---

# 30. Organizer engine

Target module:

```text
src/core/organizer/
```

Alur:

```text
Evidence
 ↓
Rule evaluation
 ↓
Proposal
 ↓
Conflict detection
 ↓
Preview
 ↓
Approval
 ↓
Execute
 ↓
Verify
 ↓
Commit index
```

---

# 31. Proposal model

Sebelum file dipindahkan, buat object proposal.

Contoh:

```text
Proposal #9001

Source:
D:\Downloads\img001.jpg

Destination:
D:\Pictures\Anime\2026\img001.jpg

Reasons:
- classified as anime: 0.98
- file type: image
- date: 2026-02-14
- no conflict

Action:
MOVE

Risk:
LOW
```

User dapat melihat semua detail sebelum approve.

---

# 32. Move engine

Aturan penting:

### Same filesystem

Gunakan native rename/move jika memungkinkan.

Keuntungan:

- tidak perlu membaca seluruh file;
- tidak perlu menghitung ulang hash hanya untuk memindahkan;
- sangat cepat untuk file besar.

### Cross filesystem

Move menjadi:

```text
copy
 ↓
flush
 ↓
verify
 ↓
update index
 ↓
only then optional source cleanup policy
```

Karena aplikasi ini never-delete secara default, source cleanup harus menjadi policy terpisah dan tidak otomatis aktif.

---

# 33. Verification setelah move

Jangan menganggap API move sukses berarti state database otomatis benar.

Setelah move:

```text
check destination exists
check size
check file identity where meaningful
optional verify hash for high-value operation
update DB path
append audit log
```

Jika verification gagal:

```text
operation = PARTIAL/FAILED
```

dan jangan menandai database sebagai sukses final.

---

# 34. Conflict handling

Contoh:

```text
source:
D:\A\photo.jpg

destination already exists:
D:\B\photo.jpg
```

Policy harus configurable:

```text
SKIP
RENAME
MERGE
KEEP_SOURCE
KEEP_DESTINATION
COMPARE_FIRST
```

Default aman:

```text
COMPARE_FIRST / SKIP
```

Jangan overwrite otomatis.

---

# 35. Job system

Target module:

```text
src/core/jobs/
```

Job system adalah komponen penting agar aplikasi benar-benar siap digunakan untuk dataset besar.

Jenis job:

```text
SCAN
HASH
METADATA
DUPLICATE_ANALYSIS
VISION_ANALYSIS
VIDEO_ANALYSIS
MOVE
VERIFY
INDEX_REPAIR
```

Setiap job memiliki:

```text
job_id
job_type
status
priority
created_at
started_at
completed_at
progress
checkpoint
retry_count
error_count
cancel_requested
pause_requested
```

---

# 36. Job lifecycle

```text
QUEUED
  ↓
RUNNING
  ↓
PAUSED ←────┐
  ↓         │
RESUMING ───┘
  ↓
COMPLETED
```

Alternatif terminal state:

```text
CANCELLED
FAILED
PARTIAL
```

Job system harus menyimpan checkpoint agar restart tidak mengulang semuanya.

---

# 37. Worker architecture

Jangan membuat semua pekerjaan dengan satu pool global.

Target:

```text
IO workers
CPU workers
AI workers
DB writer
```

Contoh:

```text
Scanner
  ↓
Job Queue
  ↓
I/O worker
  ↓
Result Queue
  ↓
CPU / AI worker
  ↓
Result Queue
  ↓
DB writer
```

Tujuannya mengurangi lock contention SQLite.

---

# 38. Database architecture target

Tabel masa depan yang disarankan:

```text
files
file_identities
file_paths
scan_sessions
scan_errors
hash_results
metadata_results
media_analysis
ai_models
ai_predictions
embeddings
duplicate_groups
duplicate_members
jobs
job_items
job_checkpoints
proposals
proposal_items
operations
audit_log
settings
```

Jangan menambahkan semua tabel sekaligus.

Schema harus berkembang melalui migration:

```text
v1
v2
v3
v4
...
```

---

# 39. Database migration rules

Setiap migration harus:

1. mempunyai version;
2. transaction-safe;
3. backward behavior diketahui;
4. bisa gagal tanpa meninggalkan schema setengah jadi;
5. diverifikasi setelah apply;
6. tercatat di log.

Contoh:

```text
migration 3
add table duplicate_groups

migration 4
add ai_model table

migration 5
split file path from file identity
```

Jangan pernah mengubah schema secara manual di production database lalu melupakannya di source.

---

# 40. Hash cache jangka panjang

Cache sekarang menggunakan kombinasi:

```text
path + size + mtime + stage
```

Ini cepat, tetapi target jangka panjang lebih baik menggunakan file identity saat tersedia.

Contoh:

```text
file_id
content_state
stage
algorithm
hash
```

Content state dapat berupa:

```text
size
mtime
native identity
optional content fingerprint
```

Tujuannya agar rename tidak selalu menyebabkan seluruh pipeline dianggap file baru.

---

# 41. Handling file yang berubah saat proses

Kasus penting:

```text
hash mulai
↓
user mengedit file
↓
hash selesai
```

Jangan menyimpan hasil sebagai trusted tanpa verifikasi.

Target:

```text
stat_before
↓
read/hash
↓
stat_after
↓
compare
```

Jika state berubah:

```text
result = INVALIDATED
```

dan ulangi pada job berikutnya.

---

# 42. Crash safety

Setiap operasi penting harus memiliki state machine.

Contoh move:

```text
PLANNED
↓
STARTED
↓
DESTINATION_CREATED
↓
VERIFIED
↓
INDEX_UPDATED
↓
COMMITTED
```

Jika aplikasi crash setelah `VERIFIED` tetapi sebelum `INDEX_UPDATED`, startup recovery dapat mendeteksi mismatch filesystem vs database.

---

# 43. Startup recovery

Pada startup, aplikasi harus dapat melakukan:

```text
load unfinished jobs
 ↓
inspect filesystem
 ↓
compare expected state
 ↓
resume / rollback metadata / mark partial
```

Jangan mengandalkan aplikasi selalu ditutup dengan normal.

---

# 44. Filesystem reconciliation

Aplikasi harus memiliki mode:

```text
RECONCILE
```

Tujuannya mencari perbedaan antara:

```text
Database
vs
Filesystem
```

Contoh:

```text
DB says path A exists
filesystem says missing

DB says path B is there
filesystem says path B is same native file at another path

DB says destination was moved
filesystem says operation incomplete
```

Reconciliation adalah fitur penting untuk aplikasi yang berjalan bertahun-tahun.

---

# 45. Storage strategy

## HDD

Prioritas:

- sedikit concurrent reads;
- sequential access bila memungkinkan;
- batching;
- avoid random hashing;
- cache.

## SATA SSD

Bisa meningkatkan concurrency, tetapi tetap terikat latency dan queue depth.

## NVMe

Dapat memakai worker lebih banyak, tetapi jangan mengasumsikan lebih banyak worker selalu lebih cepat.

## Network share

Harus diperlakukan berbeda:

- latency tinggi;
- disconnect;
- timeout;
- permissions;
- unstable timestamps;
- file lock.

Network share sebaiknya menjadi backend filesystem terpisah pada fase lanjut.

---

# 46. Performance strategy

Target bukan hanya:

```text
maksimum throughput
```

tetapi:

```text
minimum unnecessary I/O
+ stable latency
+ resumability
+ predictable resource usage
```

Metrics yang harus diukur:

```text
files/sec
bytes/sec
hashes/sec
CPU usage
RAM usage
SQLite write rate
queue depth
cache hit ratio
AI inference/sec
mean job latency
error rate
```

---

# 47. Benchmark plan

Dataset benchmark minimum:

```text
10k files
100k files
500k files
1M files
```

Komposisi harus bervariasi:

```text
small files < 1 MB
medium files 1–100 MB
large files 100 MB–10 GB+
```

Dan storage:

```text
HDD
SATA SSD
NVMe
```

---

# 48. Benchmark scenarios

### Cold scan

Database kosong.

### Warm scan

Semua file unchanged.

### 1% changed

Hanya 1% file berubah.

### 10% changed

Menilai scaling incremental.

### Hash cold cache

Tidak ada stage hash cache.

### Hash warm cache

Semua cache hit.

### Partial failure

Sebagian file tidak bisa dibaca.

### Large file

Test 1 GB, 5 GB, 20 GB, 50 GB bila environment memungkinkan.

---

# 49. Memory strategy

Jangan menyimpan semua file record sebagai object besar di RAM jika dataset sangat besar.

Lebih baik:

```text
paged query
streamed traversal
bounded queues
```

Gunakan limit untuk:

- pending job items;
- AI batch;
- metadata extraction queue;
- duplicate candidate lists.

Target aplikasi tetap stabil pada dataset besar.

---

# 50. Resource budgets

Setiap subsystem idealnya memiliki budget.

Contoh:

```text
scanner queue <= N
hash queue <= N
AI queue <= N
RAM <= target
GPU VRAM <= target
```

Jangan membuat antrian tak terbatas.

---

# 51. Configuration

Settings harus dibagi menjadi:

```text
application
scanner
hashing
AI
video
organizer
jobs
UI
logging
```

Jangan menaruh semua configuration sebagai environment variable.

Environment variables cocok untuk:

- developer override;
- CI;
- test environment.

User settings sebaiknya berada dalam app config/database.

---

# 52. Cache directories

Pisahkan:

```text
source data
index DB
analysis cache
model cache
thumbnail cache
logs
```

Contoh:

```text
AIOrganizerData/
├── index/
├── cache/
│   ├── thumbnails/
│   ├── embeddings/
│   └── previews/
├── logs/
├── models/
└── jobs/
```

Jangan menyimpan cache di dalam folder yang sedang dianalisis.

---

# 53. Thumbnail strategy

Thumbnail harus lazy-loaded.

Jangan generate thumbnail 1 juta gambar saat scan pertama.

Lebih baik:

```text
scan
 ↓
index
 ↓
UI requests preview
 ↓
thumbnail job
 ↓
cache
```

Gunakan bounded worker queue.

---

# 54. OCR strategy

OCR juga harus dianggap analysis job berat.

Pipeline:

```text
candidate document/image
 ↓
OCR eligibility filter
 ↓
OCR worker
 ↓
text result
 ↓
optional indexing
```

Jangan OCR semua file tanpa filter.

---

# 55. Search system

Target jangka panjang:

```text
metadata filters
+ filename search
+ full-text text search
+ semantic embedding search
+ duplicate group search
```

SQLite FTS dapat dipakai untuk text indexing lokal.

Semantic search boleh menggunakan vector storage/database layer pada fase lanjut jika skala benar-benar membutuhkannya. Jangan menambahkan vector database eksternal terlalu awal.

---

# 56. Rules engine

Organizer yang kuat harus mendukung rule terstruktur.

Contoh:

```text
IF file.type == image
AND ai.class == anime
AND ai.score >= 0.90
AND duplicate == false
THEN propose move to Pictures/Anime/{year}/
```

Rule engine harus deterministic.

LLM hanya boleh membantu membuat atau menjelaskan rule, bukan menjalankan operasi filesystem langsung.

---

# 57. Custom category system

Kategori user harus configurable.

Contoh:

```text
Pictures
├── Real Photo
├── Anime
├── Illustration
├── Screenshot
├── Meme
└── Scan
```

Kemudian kategori lain dapat ditambahkan tanpa rebuild aplikasi.

---

# 58. Explainability

Setiap AI classification harus bisa menjawab:

```text
Apa hasilnya?
Model apa?
Versi apa?
Confidence berapa?
Kapan dihitung?
Input pipeline apa?
```

Untuk proposal organizer:

```text
Why this file is proposed here?
```

harus bisa ditampilkan di GUI.

---

# 59. Privacy model

Default:

```text
NO CLOUD UPLOAD
```

Jika suatu saat cloud AI integration ditambahkan, harus ada:

- explicit opt-in;
- indication clearly visible;
- provider selection;
- data transfer policy;
- ability to disable;
- audit/logging.

Aplikasi lokal sebaiknya tidak diam-diam mengirim thumbnail, text, metadata, atau file ke internet.

---

# 60. Security model

Risiko utama aplikasi ini bukan hanya jaringan, tetapi juga filesystem.

Risiko:

- path traversal;
- symlink/junction surprises;
- destination escape;
- corrupted file;
- malformed media;
- malicious archives;
- parser vulnerabilities;
- model file tampering;
- unsafe LLM tool calling.

Aturan:

1. validate normalized paths;
2. treat archives as untrusted;
3. limit decompression;
4. avoid automatic extraction during scan;
5. sandbox risky decoders when practical;
6. do not trust AI output as a filesystem command;
7. validate every destination.

---

# 61. Symlink / junction policy

Default scanner:

```text
follow_symlinks = false
```

Ini adalah keputusan yang benar untuk menghindari:

- infinite recursion;
- scanning same data through multiple paths;
- accidental crossing into protected locations.

Jika nanti support symlink diaktifkan, harus ada:

- loop detection;
- maximum depth;
- target identity tracking;
- policy per root.

---

# 62. Protected locations

Default skip list saat ini mencakup:

```text
$RECYCLE.BIN
System Volume Information
.ai_organizer.lock
```

Ke depan tambahkan policy configurable untuk:

- OS directories;
- application data;
- hidden/system directories;
- virtual filesystem mounts.

Jangan hard-code terlalu banyak lokasi yang mungkin valid di environment user.

---

# 63. Logging architecture target

Log file sebaiknya dipisahkan berdasarkan severity atau subsystem.

Contoh:

```text
app.log
scanner.log
jobs.log
ai.log
operations.log
```

Tetapi untuk user-facing package, jangan membuat puluhan log file tanpa alasan.

Default bisa tetap satu log file dengan structured fields:

```text
timestamp
level
module
job_id
file_id
path
message
```

---

# 64. Audit log

Audit log berbeda dengan application log.

Application log:

```text
scan started
```

Audit log:

```text
user approved move
source=A
destination=B
result=verified
```

Audit log harus lebih durable dan queryable.

---

# 65. GUI architecture target

Target project layout masa depan:

```text
src/gui/
├── app/
├── controllers/
├── viewmodels/
├── models/
├── qml/
└── resources/
```

GUI screens yang disarankan:

```text
Dashboard
Sources
Scan
Jobs
Duplicates
Similar Files
AI Categories
File Browser
Proposals
Operations
History
Settings
Diagnostics
```

---

# 66. Dashboard

Dashboard tidak boleh hanya berisi angka kosmetik.

Gunakan metrics yang berasal dari DB/job engine:

```text
indexed files
new files
changed files
duplicates
AI processed
pending jobs
failed jobs
storage analyzed
last scan
```

Tambahkan warning bila ada:

```text
unreadable files
stale index
unfinished operations
missing model
low disk space
```

---

# 67. Job UI

GUI harus menunjukkan:

```text
job type
progress
speed
ETA if meaningful
current path
errors
pause
resume
cancel
retry
```

Untuk operasi besar, jangan mengandalkan progress berdasarkan jumlah item saja jika item memiliki ukuran sangat berbeda.

Contoh hashing:

```text
progress by bytes
```

lebih bermakna daripada:

```text
progress by file count
```

---

# 68. Duplicate UI

Tampilan duplicate harus memperlihatkan:

```text
Group
Size
Hash
Number of copies
Paths
Preview
Metadata
Recommended canonical candidate
Reason
```

Tetapi "recommended canonical" harus tetap menjadi proposal, bukan tindakan otomatis.

---

# 69. Similarity UI

Untuk image similarity:

```text
thumbnail A
thumbnail B
similarity score
model/version
reason
```

Berikan threshold yang bisa diubah user.

---

# 70. Testing strategy

Testing harus tumbuh seiring fitur.

## Unit

Test setiap class/function kecil.

## Integration

Test kombinasi:

```text
scanner + DB
hash + DB
metadata + file
AI + cache
organizer + DB
```

## End-to-end

Contoh:

```text
create dataset
 ↓
scan
 ↓
hash
 ↓
classify
 ↓
generate proposal
 ↓
approve
 ↓
move
 ↓
verify
 ↓
rescan
```

## Regression

Setiap bug production harus mendapatkan test regression bila masuk akal.

---

# 71. Test dataset

Buat fixture resmi:

```text
fixtures/
├── unicode/
├── duplicates/
├── changed/
├── gone/
├── large_files/
├── corrupt/
├── images/
├── videos/
├── audio/
└── documents/
```

Dataset pengujian harus dapat dibuat ulang.

---

# 72. Fuzz testing

Target fuzz:

- filename;
- path normalization;
- metadata parser;
- media headers;
- database migration inputs;
- rule parser;
- LLM structured output parser.

Jangan hanya mengandalkan happy path.

---

# 73. Corrupt-file handling

Aplikasi organizer harus menganggap corruption sebagai kondisi normal yang mungkin terjadi.

Contoh:

```text
read error
unexpected EOF
invalid header
unsupported codec
permission denied
sharing violation
file locked
```

Aturan:

> satu file bermasalah tidak boleh menghentikan seluruh job.

Kecuali storage layer menunjukkan kondisi system-level yang membuat seluruh operasi tidak aman.

---

# 74. Hardware failure awareness

Jika drive mengeluarkan banyak I/O error:

```text
error_count meningkat tajam
```

aplikasi harus:

- memperlambat job;
- melaporkan warning;
- optional pause;
- tidak melakukan operasi write berbahaya ke sumber;
- menyimpan state agar dapat dilanjutkan.

Aplikasi organizer tidak boleh mencoba "memperbaiki" filesystem secara otomatis.

---

# 75. Low-disk-space handling

Sebelum job tertentu:

```text
check free space
```

Cross-volume copy/move harus mengestimasi kebutuhan ruang.

Jika ruang tidak cukup:

```text
job = BLOCKED
reason = insufficient_storage
```

bukan gagal setelah setengah operasi selesai.

---

# 76. File locks

Windows sering memiliki file yang sedang dipakai aplikasi lain.

Policy:

```text
retry with backoff
 ↓
if still locked
 ↓
mark deferred/error
```

Jangan loop tanpa batas.

---

# 77. Archive handling

ZIP/RAR/7z dan archive lainnya sebaiknya tidak diekstrak otomatis ke disk saat scanning normal.

Untuk fase lanjut:

```text
archive metadata
member listing
optional content index
```

Tetap gunakan sandbox/resource limits untuk archive processing.

---

# 78. Backup strategy

Database index harus bisa di-backup.

Contoh:

```text
AIOrganizerData/index/
```

Backup tidak perlu menggandakan semua file sumber.

Simpan:

- SQLite DB;
- configuration;
- custom rules;
- model registry metadata;
- important audit logs.

Cache boleh rebuild.

---

# 79. Rebuildable vs persistent data

### Rebuildable

```text
thumbnail cache
embedding cache tertentu
quick hash cache
temporary job files
```

### Persistent

```text
user settings
approved rules
audit logs
operations
file index
job state
model registry
```

Dokumentasikan mana yang aman dihapus.

---

# 80. Database size management

Jika jutaan file di-index, SQLite database dapat menjadi besar.

Rencana:

- index hanya kolom yang sering dicari;
- batch transactions;
- vacuum policy hanya saat perlu;
- WAL checkpoint policy;
- retention policy untuk log detail;
- archive old audit logs jika dibutuhkan.

Jangan menjalankan `VACUUM` secara sembarang di tengah job besar.

---

# 81. Query optimization

Gunakan EXPLAIN QUERY PLAN untuk query besar.

Index candidate yang mungkin penting:

```text
files(size)
files(scan_status)
files(hash_status)
files(file_type)
files(sha256)
files(last_seen_ms)
```

Tetapi jangan membuat index untuk setiap kolom karena index juga menambah storage dan biaya write.

Index dibuat berdasarkan query nyata.

---

# 82. Current database design review

Schema sekarang memiliki:

```text
files
sessions
errors
settings
hashes
hash_stages
```

`hash_stages` adalah cache utama yang relevan untuk pipeline saat ini.

Tabel `hashes` lama/legacy harus dievaluasi pada migration berikutnya. Jika tidak lagi digunakan, lebih baik disingkirkan melalui migration terkontrol agar schema tidak membingungkan.

---

# 83. Current hashing concurrency review

Pipeline saat ini membuat worker pool maksimum 8 thread, tetapi SQLite connection diproteksi mutex.

Artinya throughput didapat dari:

```text
parallel file reads
```

sementara database write tetap serialized.

Itu bukan bug.

Tetapi untuk scale lebih tinggi, target berikutnya adalah:

```text
worker threads
 ↓
result queue
 ↓
single DB writer / batched transaction
```

Ini harus dibenchmark sebelum diadopsi.

---

# 84. Current CLI limitations

CLI saat ini menyediakan:

```text
aiorganizer version
aiorganizer scan <folder> --db <file>
aiorganizer hash <file> [--db <file>]
```

CLI target masa depan:

```text
aiorganizer scan
aiorganizer hash
aiorganizer analyze
aiorganizer duplicate
aiorganizer classify
aiorganizer jobs
aiorganizer proposals
aiorganizer apply
aiorganizer repair
aiorganizer doctor
aiorganizer export
aiorganizer version
```

Command tersebut harus menggunakan service layer yang sama dengan GUI.

---

# 85. CLI `doctor`

Command `doctor` sangat berguna.

Contoh pemeriksaan:

```text
compiler/runtime
SQLite
database integrity
storage accessibility
model availability
FFmpeg availability
ONNX Runtime
GPU backend
free space
write permission
```

Contoh hasil:

```text
[OK] database
[OK] source volume
[OK] SQLite
[OK] vision runtime
[WARN] FFmpeg unavailable
[WARN] GPU backend disabled
```

---

# 86. CLI `repair`

Repair tidak boleh langsung mengubah file secara agresif.

Tahapan:

```text
inspect
 ↓
report
 ↓
propose
 ↓
approve
 ↓
repair
 ↓
verify
```

Contoh repair:

- rebuild index from filesystem;
- repair broken DB paths;
- recover unfinished job state;
- refresh metadata.

---

# 87. Model registry

Jangan hard-code satu model AI.

Buat registry:

```text
model_id
name
version
format
provider
hash
input_spec
output_spec
category_schema
enabled
```

Dengan demikian:

```text
vision-v1
vision-v2
vision-v3
```

bisa dibandingkan atau dimigrasikan.

---

# 88. Model upgrade strategy

Saat model berubah:

```text
old predictions remain auditable
new model runs as new analysis version
```

Jangan overwrite hasil lama secara diam-diam.

Contoh:

```text
prediction(model=A, version=1)
prediction(model=A, version=2)
```

User dapat melihat hasil terbaru tanpa kehilangan histori.

---

# 89. AI cache invalidation

AI cache key harus memasukkan minimal:

```text
file identity/content state
model id
model version
preprocess version
```

Jika model berubah, hasil lama jangan dianggap valid untuk model baru.

---

# 90. Embedding storage

Embedding dapat berukuran besar.

Jangan menyimpan semua embedding sebagai JSON text jika skala besar.

Gunakan binary packed representation atau storage yang sesuai.

Untuk awal:

```text
float32 vector
```

Untuk skala lebih besar, pertimbangkan quantization dan vector indexing.

Jangan menambahkan vector DB eksternal sebelum ada kebutuhan nyata.

---

# 91. OCR/indexing architecture target

```text
file
 ↓
document/image eligibility
 ↓
OCR
 ↓
text
 ↓
normalize
 ↓
FTS index
 ↓
search
```

AI semantic search menjadi layer tambahan di atas deterministic text indexing.

---

# 92. Search UX target

User dapat mencari:

```text
filename
extension
size
folder
date
camera
resolution
exact duplicate
similar image
AI class
OCR text
video duration
```

Dan query natural language dapat diterjemahkan menjadi structured filter oleh LLM, lalu divalidasi deterministic engine.

---

# 93. Long-term plugin architecture

Jika jumlah fitur semakin besar, gunakan internal plugin/adaptor boundary.

Contoh interface:

```cpp
class IMetadataProvider;
class IVideoAnalyzer;
class IVisionProvider;
class ILanguageModel;
class IStorageBackend;
```

Plugin tidak perlu menjadi DLL sejak hari pertama.

Interface abstraction terlebih dahulu.

Actual dynamic plugin loading hanya ditambahkan saat kebutuhan benar-benar muncul.

---

# 94. Why not use microservices

Untuk desktop local-first app, jangan memecah semuanya menjadi service/network process hanya demi terlihat kompleks.

Lebih baik:

```text
modular monolith
```

dengan worker jobs dan interface yang jelas.

Microservice baru masuk akal jika:

- remote processing diperlukan;
- multi-user server version dibuat;
- GPU inference dipisah ke machine lain;
- distributed index diperlukan.

Untuk aplikasi desktop sekarang, service boundaries cukup berada di dalam satu process atau beberapa local worker process yang terkontrol.

---

# 95. Future server edition

Jika suatu hari AIOrganizer dibuat menjadi server/homelab service, core yang ada harus bisa direuse.

Target layering:

```text
aiorg_core
     ↑
 ┌───┴─────────┐
 │             │
Desktop GUI   Server API
 │             │
Qt/QML       HTTP/gRPC
```

Ini alasan core tidak boleh mengetahui Qt.

---

# 96. CI/CD target

Pipeline CI minimum:

```text
checkout
 ↓
configure
 ↓
build Debug
 ↓
build Release
 ↓
unit tests
 ↓
integration tests
 ↓
static analysis
 ↓
package artifact
```

Future:

```text
Windows x64
Windows ARM64
Linux x64
```

Portability baru ditingkatkan setelah Windows core stabil.

---

# 97. Static analysis

Tambahkan secara bertahap:

- clang-tidy;
- clang-format;
- compiler warnings as high;
- MSVC code analysis;
- sanitizer builds.

Target style:

```text
warning-free release build
```

Jangan membiarkan warning menumpuk bertahun-tahun.

---

# 98. Formatting rules

Tetapkan satu style C++.

Disarankan:

```text
clang-format
```

Jalankan di CI.

Jangan membiarkan satu file memakai style berbeda hanya karena dibuat pada waktu berbeda.

---

# 99. Error model

Error harus dibedakan:

```text
USER_ERROR
CONFIG_ERROR
FILESYSTEM_ERROR
DATABASE_ERROR
MEDIA_ERROR
AI_ERROR
RESOURCE_ERROR
CANCELLED
INTERNAL_ERROR
```

Jangan hanya mengembalikan string error mentah dari semua layer.

Target jangka panjang:

```cpp
ErrorCode
ErrorContext
Message
Retryable
Severity
```

---

# 100. Retry policy

Tidak semua error harus di-retry.

### Retryable

- sharing violation;
- temporary access issue;
- network timeout;
- transient device error.

### Non-retryable

- unsupported format;
- malformed file;
- permission denied yang permanen;
- invalid destination.

Retry harus memiliki limit dan backoff.

---

# 101. Event system

Modul besar akan membutuhkan event bus internal ringan.

Contoh event:

```text
ScanStarted
FileIndexed
HashCompleted
AnalysisCompleted
JobProgress
ProposalCreated
OperationStarted
OperationVerified
OperationFailed
```

GUI subscribe ke event tersebut.

Core tidak perlu tahu GUI.

---

# 102. Progress model

Progress minimal:

```text
current
completed
failed
skipped
total
bytes_completed
bytes_total
rate
```

ETA hanya ditampilkan bila estimasinya cukup berarti.

---

# 103. Pause vs cancel

### Pause

Job state tetap dipertahankan dan dapat dilanjutkan.

### Cancel

Job berhenti dan state ditandai cancelled.

Untuk operation job, cancel tidak selalu berarti rollback otomatis. Ini harus tergantung tahap operasi.

---

# 104. User approval policy

Tindakan berisiko tinggi harus membutuhkan approval.

Contoh:

```text
MOVE → approval
BULK RENAME → approval
CROSS-VOLUME COPY → approval
DELETE → disabled by default
```

Untuk tindakan yang benar-benar non-destructive seperti re-index atau read-only analysis, approval tidak diperlukan.

---

# 105. Never-delete policy

Default product policy:

```text
NO AUTOMATIC DELETE
```

Bahkan untuk duplicate.

Duplicate detector hanya menyatakan:

```text
These files are exact duplicates.
```

Kemudian user dapat memilih tindakan.

---

# 106. Canonical file policy

Jika user memiliki:

```text
A.jpg
B.jpg
C.jpg
```

dan semuanya exact duplicate, sistem boleh membantu menentukan candidate canonical berdasarkan rule seperti:

- lokasi;
- tanggal;
- filename quality;
- shortest path;
- user preference;
- protected directory;
- backup status.

Tetapi candidate canonical harus transparan dan dapat diubah user.

---

# 107. Rule priority

Jika rule bertabrakan:

```text
explicit user rule
    > protected folder policy
    > safety rule
    > organizer rule
    > AI suggestion
```

Safety rule tidak boleh dikalahkan AI.

---

# 108. Roadmap implementasi yang disarankan

Gunakan fase berikut dan jangan mengerjakan semuanya sekaligus.

## Phase 0 — Foundation cleanup

Tujuan:

- clean build tree dari source package;
- konsolidasi dokumentasi;
- standar format;
- `.gitignore`;
- CMake presets;
- CI baseline;
- migration discipline.

Selesai jika build/test repeatable dari clean checkout.

---

## Phase 1 — Harden core

Fokus:

- scanner;
- file identity;
- database;
- hashing;
- cache.

Tambahkan:

- file changed-during-hash detection;
- stronger identity handling;
- better error classification;
- batch DB writer;
- more edge-case tests.

---

## Phase 2 — Exact Duplicate Engine

Bangun:

```text
size grouping
quick hash grouping
partial hash grouping
full SHA-256 grouping
duplicate groups
```

Belum perlu AI.

Target akhir fase:

```text
aiorganizer duplicate <root>
```

menghasilkan duplicate groups dengan aman.

---

## Phase 3 — Similarity Engine

Tambah:

- pHash/dHash;
- visual similarity;
- image resize normalization;
- image embeddings sebagai optional advanced path.

Target:

```text
exact duplicate
near duplicate
similar image
```

---

## Phase 4 — Metadata

Tambah:

- image metadata;
- audio metadata;
- PDF/document metadata;
- archive metadata.

Metadata harus incremental dan cacheable.

---

## Phase 5 — Video

Tambah FFmpeg integration.

Fokus:

- probe;
- stream info;
- sample decode;
- corruption detection.

---

## Phase 6 — Job Engine

Refactor pekerjaan menjadi durable jobs.

Target:

```text
pause
resume
cancel
retry
checkpoint
recovery
```

Setelah fase ini, GUI akan jauh lebih mudah dibuat.

---

## Phase 7 — Organizer Engine

Tambah:

- rules;
- proposals;
- preview;
- approval;
- move engine;
- verification;
- audit log;
- reconciliation.

---

## Phase 8 — Qt GUI

Mulai GUI setelah core service sudah stabil.

Screen awal:

```text
Dashboard
Sources
Jobs
Duplicates
Proposals
History
Settings
```

---

## Phase 9 — Vision AI

Integrasikan ONNX Runtime.

Mulai dengan satu model yang jelas use-case-nya, bukan banyak model sekaligus.

Pertama:

```text
image classification
```

Kemudian:

```text
embedding
OCR
object detection
```

sesuai kebutuhan.

---

## Phase 10 — Local LLM

Integrasikan llama.cpp untuk semantic control/explanation.

Mulai dari fungsi read-only:

```text
search explanation
category explanation
rule creation helper
```

Baru setelah guardrail stabil, gunakan untuk proposal generation.

---

## Phase 11 — Advanced Intelligence

Tambahkan:

- semantic search;
- contextual grouping;
- duplicate cluster reasoning;
- smart naming;
- timeline grouping;
- user feedback loop;
- custom categories;
- model evaluation.

---

# 109. Fitur yang sebaiknya ditambahkan nanti

Potential feature backlog:

```text
[ ] Smart rename
[ ] Folder suggestion
[ ] Duplicate cleanup assistant
[ ] Similar-photo timeline
[ ] Screenshot detector
[ ] Meme detector
[ ] Anime detector
[ ] Document detector
[ ] OCR
[ ] Receipt detector
[ ] Camera grouping
[ ] GPS clustering
[ ] Date/event clustering
[ ] Video scene preview
[ ] Corrupt media report
[ ] Archive inspector
[ ] Content search
[ ] Semantic search
[ ] Natural language filters
[ ] Custom category training
[ ] User feedback learning
[ ] Watch folders
[ ] Scheduled scans
[ ] External drive profiles
[ ] Network share support
[ ] NAS profile
[ ] Backup verification
[ ] Export report
[ ] CSV/JSON export
[ ] API/server edition
```

Roadmap ini bersifat additive. Jangan membuat semua fitur masuk ke core yang sama.

---

# 110. Watch folder

Fitur masa depan:

```text
D:\Downloads
```

dipantau secara incremental menggunakan filesystem notifications jika tersedia.

Namun scanner periodic tetap dipertahankan sebagai source of truth karena file notification dapat hilang saat:

- reboot;
- queue overflow;
- drive disconnect;
- application offline.

Watch events hanya menjadi acceleration layer.

---

# 111. Scheduled scan

Scheduler target:

```text
quick scan daily
full reconciliation weekly
AI analysis on demand
```

Namun scheduler tidak perlu menjadi Windows service sejak awal. Desktop background task lebih sederhana.

---

# 112. External drive profiles

Setiap volume dapat mempunyai profile:

```text
volume identity
label
root mappings
policy
last seen
```

Contoh:

```text
Photography HDD
Archive SSD
Downloads SSD
NAS Share
```

Saat drive tidak tersambung, index tetap tersedia sebagai historical view.

---

# 113. Offline index behavior

User tetap dapat melihat:

```text
file pernah ada
old metadata
old hash
old classification
```

meskipun drive sedang offline.

Status harus jelas:

```text
OFFLINE
```

Jangan menampilkan file seolah tersedia bila sebenarnya volume offline.

---

# 114. Import/export

Database harus dapat diekspor secara aman.

Format:

```text
JSON
CSV
SQLite backup
```

Export adalah read-only operation.

---

# 115. Recovery priority

Jika index rusak:

```text
1. copy corrupted DB
2. inspect
3. restore backup if valid
4. reconcile filesystem
5. re-index changed/missing rows
6. rebuild cache if necessary
```

Jangan menghapus database rusak sebelum backup copy dibuat.

---

# 116. Release packaging

Target output:

```text
AIOrganizer/
├── AIOrganizer.exe
├── Qt runtime
├── plugins/
├── resources/
├── models/           # optional external
├── third-party licenses
└── config/
```

Runtime dependency harus dikumpulkan dalam release bundle atau installer sesuai license.

---

# 117. Installer

Installer dapat menggunakan:

- WiX;
- NSIS;
- Inno Setup;
- deployment mechanism Qt yang sesuai.

Jangan menambahkan installer sebelum command-line engine dan GUI sudah stabil.

---

# 118. Versioning

Gunakan semantic versioning untuk release aplikasi:

```text
MAJOR.MINOR.PATCH
```

Contoh:

```text
0.1.0
0.2.0
0.3.0
1.0.0
```

Schema version dan application version berbeda.

Contoh:

```text
app version = 1.2.0
schema version = 7
```

---

# 119. Compatibility policy

Jangan biarkan binary baru silently membuka database yang schema-nya lebih baru jika belum mendukung.

Current implementation sudah memiliki guard:

```text
if user_version > supported_version
    fail safely
```

Pertahankan prinsip ini.

---

# 120. Dependency updates

Update dependency tidak boleh dilakukan massal tanpa test.

Workflow:

```text
update one dependency
 ↓
build
 ↓
unit test
 ↓
integration test
 ↓
benchmark
 ↓
security/license review
 ↓
merge
```

Untuk AI runtime, tambahkan model compatibility test.

---

# 121. License compliance

Setiap dependency harus memiliki:

```text
license
version
source URL
redistribution terms
```

Project saat ini sudah menyimpan license files dari vendored dependencies pada tree masing-masing.

Untuk release, buat inventory dependency yang menjadi bagian installer.

---

# 122. Dependency manifest yang disarankan

Pada fase berikutnya buat machine-readable manifest seperti:

```text
name
version
source
license
build mode
runtime/static
optional/required
```

Bisa berupa JSON sederhana di tooling, tetapi dokumentasi manusia tetap berada di file master ini.

---

# 123. Development workflow harian

Urutan kerja ideal:

```text
1. update source
2. build
3. run unit tests
4. run targeted test
5. benchmark jika performance-related
6. inspect logs
7. commit
```

Jangan memasukkan perubahan feature + refactor + dependency upgrade besar dalam satu perubahan jika bisa dipisahkan.

---

# 124. Commit discipline

Format commit dapat dibuat seperti:

```text
core(scanner): improve native identity tracking
hash(cache): add stable file identity key
ui(jobs): add pause/resume controls
ai(vision): add image embedding provider
organizer(move): add same-volume verified move
```

Ini membantu ketika project sudah besar.

---

# 125. Pull request checklist

Sebelum menganggap fitur selesai:

```text
[ ] design documented
[ ] error cases handled
[ ] cancellation handled
[ ] retry policy considered
[ ] tests added
[ ] benchmark considered
[ ] migration added if schema changed
[ ] logging added
[ ] GUI impact reviewed
[ ] backward compatibility reviewed
```

---

# 126. Definition of Done

Sebuah fitur tidak dianggap selesai hanya karena "kode jalan".

Definition of Done:

```text
code
+ tests
+ error handling
+ cancellation
+ logging
+ documentation
+ migration if needed
+ benchmark if relevant
+ recovery behavior
```

---

# 127. Hal yang jangan dilakukan

Jangan:

- menaruh logic database besar di QML;
- membuat AI memanggil filesystem langsung;
- menyimpan seluruh file contents ke SQLite;
- hashing seluruh file setiap scan;
- memindahkan file otomatis tanpa proposal;
- menghapus duplicate secara otomatis;
- menggunakan LLM sebagai source of truth filesystem;
- memasang semua dependency sekaligus;
- menjadikan Python dependency runtime tanpa kebutuhan;
- menambah microservice hanya demi kompleksitas;
- membiarkan build tree masuk source release;
- mengabaikan Unicode;
- mengabaikan file berubah saat hashing;
- menganggap database selalu benar tanpa reconciliation.

---

# 128. Setup ketika Qt mulai diintegrasikan

Setelah Qt dipasang, configure project dengan:

```powershell
cmake -S . -B build-gui -G Ninja `
  -DCMAKE_PREFIX_PATH="D:\Tools\Qt\<qt-version>\msvc2022_64"
```

Path aktual harus disesuaikan dengan instalasi Qt dan toolchain yang digunakan.

Dokumentasi Qt menggunakan pola `CMAKE_PREFIX_PATH` untuk menunjukkan lokasi instalasi Qt pada build CMake. 

Tambahkan target Qt hanya ke layer GUI.

---

# 129. Setup FFmpeg ketika modul video dimulai

Buat struktur lokal misalnya:

```text
D:\Tools\FFmpeg\
├── include\
├── lib\
└── bin\
```

Core video abstraction harus bergantung pada interface internal, bukan path hard-coded.

Contoh:

```text
IVideoAnalyzer
      ↑
FFmpegVideoAnalyzer
```

---

# 130. Setup ONNX Runtime

Sediakan runtime dalam folder dependency terpisah.

Contoh:

```text
D:\Tools\ONNXRuntime\
├── include\
├── lib\
└── bin\
```

Tambahkan CMake option:

```text
AIORGANIZER_ENABLE_ONNX=ON
```

Sehingga core masih dapat dibuild tanpa ONNX ketika developer hanya mengerjakan scanner/hashing.

---

# 131. Setup llama.cpp

Gunakan opsi build yang terpisah:

```text
AIORGANIZER_ENABLE_LLM=ON
```

Pada machine tanpa GPU, CPU backend tetap harus menjadi fallback.

Model file tidak dibundel di repository source.

---

# 132. Feature flags CMake

Target akhir CMake options:

```text
AIORGANIZER_BUILD_TESTS=ON
AIORGANIZER_BUILD_BENCHMARKS=ON
AIORGANIZER_ENABLE_GUI=OFF
AIORGANIZER_ENABLE_FFMPEG=OFF
AIORGANIZER_ENABLE_ONNX=OFF
AIORGANIZER_ENABLE_LLM=OFF
AIORGANIZER_ENABLE_GPU=OFF
```

Developer dapat mengaktifkan hanya fitur yang sedang dibutuhkan.

---

# 133. Why feature flags are important

Tanpa feature flags:

```text
simple scanner build
```

bisa berubah menjadi wajib menginstall:

```text
Qt
FFmpeg
CUDA
ONNX
llama.cpp
model
```

Ini akan membuat core sulit dipelihara.

Feature flags menjaga development cost tetap terkendali.

---

# 134. Hardware acceleration strategy

GPU support harus optional.

Provider target dapat berupa:

```text
CPU
DirectML
CUDA
Vulkan
```

Urutan fallback harus jelas:

```text
requested backend
 ↓
try initialize
 ↓
if unavailable
 ↓
fallback
 ↓
log selected provider
```

Jangan gagal menjalankan seluruh aplikasi hanya karena GPU backend tidak tersedia.

---

# 135. AI model resource management

Jangan load semua model sekaligus.

Gunakan:

```text
model lifecycle
UNLOADED
LOADING
READY
BUSY
UNLOADING
ERROR
```

Model besar membutuhkan perhatian terhadap RAM/VRAM.

---

# 136. Batch inference

Untuk AI:

```text
batch size = configurable
```

Batch terlalu besar dapat menyebabkan:

- VRAM overflow;
- high latency;
- UI freeze.

Batch terlalu kecil dapat mengurangi throughput.

Benchmark di hardware target.

---

# 137. Thumbnail/AI pipeline optimization

Jangan decode gambar berkali-kali.

Ideal:

```text
decode once
 ↓
thumbnail
 ↓
classifier
 ↓
embedding
```

Gunakan reusable image buffer jika aman.

---

# 138. Observability

Metrics yang ideal terlihat di diagnostics:

```text
scan throughput
hash throughput
DB writes/sec
cache hit rate
AI throughput
GPU memory
queue depth
error rate
```

Observability membantu mencari bottleneck daripada menebak.

---

# 139. Debug bundle

Saat user melaporkan masalah, aplikasi nantinya dapat membuat diagnostic bundle yang berisi:

- app version;
- OS version;
- hardware summary;
- enabled features;
- DB schema version;
- job state;
- sanitized logs;
- error summary.

Jangan otomatis memasukkan file pengguna atau isi file.

---

# 140. Important distinction: index vs source of truth

Filesystem adalah source of truth untuk keberadaan file.

Database adalah source of truth untuk:

- analysis state;
- job state;
- historical index;
- proposal;
- audit;
- cached metadata.

Jika filesystem dan DB berbeda, jangan langsung memilih DB.

Lakukan reconciliation.

---

# 141. Recommended final architecture

Target final:

```text
                            AIOrganizer
                                │
                 ┌──────────────┼──────────────┐
                 │              │              │
               CLI            GUI            Future API
                 │              │              │
                 └──────────────┼──────────────┘
                                │
                       Application Services
                                │
       ┌────────────────────────┼────────────────────────┐
       │                        │                        │
    Job Engine             Rule Engine              Search Engine
       │                        │                        │
       └────────────────────────┼────────────────────────┘
                                │
                             Core
                                │
      ┌──────────┬──────────┬───┴────┬──────────┬────────────┐
      │          │          │        │          │            │
  Scanner    Hashing   Metadata   Duplicate   Video       Organizer
      │          │          │        │          │            │
      └──────────┴──────────┴────────┴──────────┴────────────┘
                                │
                            Database
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
          SQLite             Cache              Audit
                                │
                         Analysis adapters
                                │
                    ┌───────────┴───────────┐
                    │                       │
               ONNX Runtime            llama.cpp
                    │                       │
                 Vision                    LLM
```

---

# 142. Recommended build philosophy

Jangan mengejar "semua fitur" secepat mungkin.

Bangun berdasarkan dependency graph:

```text
filesystem reliability
        ↓
index reliability
        ↓
hash reliability
        ↓
duplicate correctness
        ↓
job durability
        ↓
operation safety
        ↓
GUI
        ↓
AI
```

AI yang sangat canggih di atas core filesystem yang rapuh tetap menghasilkan aplikasi yang rapuh.

---

# 143. What should be built first from the current ZIP

Urutan paling masuk akal dari source yang sekarang:

```text
1. Harden scanner
2. Harden file identity
3. Improve hash cache key
4. Add exact duplicate engine
5. Add persistent job model
6. Add operation/proposal model
7. Add safe move + verification
8. Add metadata engine
9. Add video analyzer
10. Add Qt GUI
11. Add ONNX image classifier
12. Add image embeddings
13. Add OCR
14. Add llama.cpp
15. Add semantic search
16. Add advanced automation
```

Jangan melompat langsung ke nomor 11 sebelum nomor 7 stabil.

---

# 144. Minimum viable advanced release

Release pertama yang sudah terasa sebagai aplikasi serius sebaiknya memiliki:

```text
✓ scanner
✓ incremental index
✓ exact duplicate detection
✓ safe preview
✓ proposal system
✓ verified move
✓ job queue
✓ pause/resume/cancel
✓ SQLite persistence
✓ audit log
✓ Qt GUI
✓ diagnostics
✓ backup/recovery
```

AI dapat masuk setelah foundation tersebut stabil.

---

# 145. Advanced release setelah AI aktif

Tambahkan:

```text
✓ image classification
✓ similarity embeddings
✓ OCR
✓ media health analysis
✓ semantic search
✓ natural language query
✓ explainable proposals
✓ model registry
✓ model versioning
✓ feedback system
```

---

# 146. Quality target

Target kualitas jangka panjang bukan sekadar "bisa membuka file".

Target:

```text
correct
recoverable
observable
testable
scalable
upgradeable
safe
```

---

# 147. Definition of production-ready

AIOrganizer boleh dianggap production-ready untuk suatu feature area jika:

```text
Feature exists
+ tests exist
+ failure modes are handled
+ recovery exists
+ logs are useful
+ performance is measured
+ configuration exists
+ user-facing explanation exists
+ upgrade path exists
```

Feature yang baru "jalan di mesin developer" belum production-ready.

---

# 148. Final setup checklist

## Base environment

```text
[ ] Windows 10/11 x64
[ ] Visual Studio C++ workload
[ ] Windows SDK
[ ] CMake
[ ] Ninja
[ ] Git
[ ] optional Python
```

## Current core

```text
[ ] configure
[ ] build
[ ] unit tests
[ ] scan test folder
[ ] verify SQLite DB
[ ] test Unicode path
[ ] test cancellation
```

## Development quality

```text
[ ] format
[ ] static analysis
[ ] Release build
[ ] RelWithDebInfo build
[ ] benchmark baseline
```

## Future GUI

```text
[ ] Qt 6
[ ] CMAKE_PREFIX_PATH
[ ] QML
[ ] ViewModels
```

## Future media

```text
[ ] FFmpeg dev libs
[ ] video tests
```

## Future AI

```text
[ ] ONNX Runtime
[ ] model registry
[ ] first classification model
[ ] benchmark dataset
[ ] optional GPU provider
```

## Future LLM

```text
[ ] llama.cpp
[ ] GGUF model
[ ] structured-output parser
[ ] safety boundary
```

---

# 149. Current project commands

## Version

```powershell
aiorganizer version
```

## Scan

```powershell
aiorganizer scan D:\Data --db D:\AIOrganizer\index.db
```

## Hash verification

```powershell
aiorganizer hash D:\Data\file.bin --db D:\AIOrganizer\index.db
```

## Test

```powershell
ctest --test-dir build --output-on-failure
```

---

# 150. Example future command set

```powershell
aiorganizer scan D:\Data
aiorganizer duplicate D:\Data
aiorganizer analyze D:\Data --type image
aiorganizer classify D:\Data --model vision-v1
aiorganizer proposals list
aiorganizer proposals preview 1024
aiorganizer proposals approve 1024
aiorganizer jobs list
aiorganizer jobs pause 42
aiorganizer jobs resume 42
aiorganizer jobs cancel 42
aiorganizer doctor
aiorganizer repair --dry-run D:\Data
```

Semua command tersebut harus berbagi core service yang sama dengan GUI.

---

# 151. External references and official documentation

Gunakan sumber resmi berikut saat memasang atau memperbarui dependency:

- CMake: <https://cmake.org/download/>
- Microsoft C++ Build Tools: <https://learn.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-build-tools>
- Qt CMake build: <https://doc.qt.io/qt-6/cmake-build-on-cmdline.html>
- SQLite downloads: <https://www.sqlite.org/download.html>
- GoogleTest CMake quickstart: <https://google.github.io/googletest/quickstart-cmake.html>
- spdlog releases: <https://github.com/gabime/spdlog/releases>
- FFmpeg downloads: <https://ffmpeg.org/download.html>
- ONNX Runtime C++: <https://onnxruntime.ai/docs/get-started/with-cpp.html>
- llama.cpp build guide: <https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md>

Dependency versions should be pinned deliberately in the project build/release process rather than blindly using whatever version happens to be newest on a developer machine.

---

# 152. Project state at the time this document was generated

Source yang diperiksa menunjukkan:

```text
Application version: 0.1.0
C++ standard: C++20
CMake minimum: 3.26
SQLite vendored: 3.53.4
spdlog vendored: 1.17.0
GoogleTest vendored: 1.18.0
```

Core yang terimplementasi:

```text
SQLite database
UTF-8/native filesystem adapter
Scanner
Quick/Partial/Full hashing
SHA-256
Hash cache
CLI
Tests
```

Feature yang belum terimplementasi:

```text
Duplicate engine
Metadata engine
Video engine
Job system
Organizer engine
Qt GUI
Vision AI
LLM
```

Build tree yang tersedia pada source package asal juga menunjukkan environment build dengan Ninja dan MSVC 14.44.35207, tetapi build artifacts sebaiknya tidak diperlakukan sebagai source-of-truth dan dapat diregenerate kapan saja.

---

# 153. Final engineering rule

Setiap fitur baru harus menjawab lima pertanyaan:

```text
1. Data apa yang dibutuhkan?
2. Modul mana yang memiliki data tersebut?
3. Bagaimana jika proses dihentikan di tengah?
4. Bagaimana jika file berubah atau rusak?
5. Bagaimana fitur ini bisa dihapus/di-upgrade tanpa merusak sistem lama?
```

Jika lima pertanyaan tersebut belum terjawab, fitur belum siap masuk production path.

---

# 154. Ringkasan paling penting

AIOrganizer sebaiknya dibangun sebagai **modular monolith desktop engine**, bukan kumpulan script dan bukan microservice network.

Core harus tetap ringan:

```text
C++20
SQLite
spdlog
filesystem
scanner
hashing
```

Fitur berat diaktifkan secara bertahap:

```text
Qt
FFmpeg
ONNX Runtime
llama.cpp
GPU backends
```

Dan alur produk tetap:

```text
DISCOVER
   ↓
INDEX
   ↓
ANALYZE
   ↓
COMPARE
   ↓
PROPOSE
   ↓
PREVIEW
   ↓
APPROVE
   ↓
EXECUTE
   ↓
VERIFY
   ↓
AUDIT
   ↓
RECONCILE
```

Arsitektur tersebut memberi ruang untuk pertumbuhan dari organizer sederhana menjadi aplikasi yang mampu menangani duplicate, similarity, metadata, media health, image AI, OCR, semantic search, local LLM, smart organization, dan pada akhirnya kemungkinan server edition tanpa harus mengganti fondasi filesystem dan database.

---

## Appendix A — Current source modules inspected

```text
src/main.cpp
src/CMakeLists.txt

src/core/database/database.cpp
src/core/database/database.h

src/core/filesystem/utf8.cpp
src/core/filesystem/utf8.h

src/core/hashing/hash_cache.cpp
src/core/hashing/hash_cache.h
src/core/hashing/pipeline.cpp
src/core/hashing/pipeline.h
src/core/hashing/sha256.cpp
src/core/hashing/sha256.h

src/core/scanner/scanner.cpp
src/core/scanner/scanner.h

tests/test_hash.cpp
tests/test_scanner.cpp
tests/CMakeLists.txt

CMakeLists.txt
ARCHITECTURE.md
BUILD.md
```

---

## Appendix B — Current tests represented in source

Current test coverage includes:

```text
SHA-256 known vectors
staged hashing byte limits
hash cache hit
hash cache invalidation
hash pipeline duplicate grouping basics
hash cancellation
fresh scan
unchanged rescan
change detection
gone detection
pre-cancelled scan
skip configured directories
database migration/settings
CJK/non-ANSI filename regression
```

Coverage must terus ditambah setiap kali subsystem baru masuk.

---

## Appendix C — Practical development order for this codebase

Untuk langsung melanjutkan project dari ZIP ini, gunakan urutan:

```text
STEP 1
Build existing source from clean directory.

STEP 2
Run all tests and record baseline.

STEP 3
Remove build artifacts from source release workflow.

STEP 4
Improve scanner/file identity edge cases.

STEP 5
Build exact duplicate engine.

STEP 6
Build durable job engine.

STEP 7
Build proposal + safe move + verification.

STEP 8
Build metadata engine.

STEP 9
Build Qt GUI on top of the service/core layer.

STEP 10
Integrate ONNX Runtime for vision.

STEP 11
Add media analysis with FFmpeg.

STEP 12
Add OCR and semantic search.

STEP 13
Integrate llama.cpp with structured-output guardrails.

STEP 14
Add advanced organization rules and user feedback.

STEP 15
Profile everything at 100k/500k/1M+ files.

STEP 16
Harden recovery, installer, backup, diagnostics, and release.
```

---

## Appendix D — Golden rule for future development

> **Jangan membangun fitur baru dengan mengorbankan invariants core.**

Invariant penting yang harus tetap dijaga:

```text
1. Database path/logical data UTF-8.
2. Windows filesystem access memakai native wide API.
3. Hash cache mencegah pembacaan ulang yang tidak perlu.
4. Full hash hanya digunakan setelah candidate reduction.
5. Error satu file tidak menghentikan seluruh job.
6. Job harus dapat pause/cancel/resume.
7. Filesystem adalah source of truth untuk physical state.
8. AI menghasilkan evidence/proposal, bukan direct write authority.
9. Move wajib dapat diverifikasi.
10. Delete tidak menjadi default automation.
11. Schema selalu versioned.
12. GUI tidak memiliki filesystem/database business logic.
13. Model AI dapat diganti tanpa mengubah core index.
14. Feature optional tidak boleh membuat core tidak bisa dibuild.
```

**Dokumen ini adalah panduan pengembangan. Source code tetap menjadi implementasi sebenarnya. Setiap perubahan arsitektur yang diterapkan ke project harus dicerminkan kembali di dokumen ini agar dokumentasi dan source tidak berjalan ke arah yang berbeda.**
