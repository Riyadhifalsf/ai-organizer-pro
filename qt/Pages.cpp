// Pages.cpp — implementasi tab fitur (Qt Widgets, operasi berat di worker).
#include "Pages.h"

#include <QApplication>
#include <QCheckBox>
#include <QComboBox>
#include <QDesktopServices>
#include <QDir>
#include <QDirIterator>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QInputDialog>
#include <QJsonArray>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSpinBox>
#include <QSplitter>
#include <QSet>
#include <QTableWidget>
#include <QTextEdit>
#include <QTimer>
#include <QTreeWidget>
#include <QUrl>
#include <QVBoxLayout>
#include <QThread>
#include <algorithm>

namespace {
QList<GalleryItem> listMedia(Backend*, const QString& root, bool video) {
  QList<GalleryItem> out;
  static const QSet<QString> videoExts = {"mp4", "mov", "mkv", "avi", "mts",
                                          "m2ts", "webm", "wmv", "m4v", "ogv",
                                          "3gp", "ts", "flv"};
  static const QSet<QString> photoExts = {"jpg", "jpeg", "png", "webp", "bmp",
                                          "gif", "tif", "tiff", "heic", "heif"};
  const QSet<QString>& wanted = video ? videoExts : photoExts;

  QDirIterator it(root, QDir::Files | QDir::Readable | QDir::NoDotAndDotDot,
                  QDirIterator::Subdirectories);
  constexpr int kLimit = 5000;
  while (it.hasNext() && out.size() < kLimit) {
    const QString path = it.next();
    const QFileInfo fi(path);
    if (wanted.contains(fi.suffix().toLower()))
      out.append({fi.absoluteFilePath(), QDir(root).relativeFilePath(path),
                  fi.size()});
  }
  std::sort(out.begin(), out.end(), [](const GalleryItem& a, const GalleryItem& b) {
    return a.path.toLower() < b.path.toLower();
  });
  return out;
}

QString askText(QWidget* ctx, const QString& title, const QString& label,
                const QString& value) {
  bool ok = false;
  const QString v =
      QInputDialog::getText(ctx, title, label, QLineEdit::Normal, value, &ok);
  return ok ? v : QString();
}

bool askConfirm(QWidget* ctx, const QString& title, const QString& text) {
  const QVariant setting = qApp->property("aiorg_confirm_actions");
  if (setting.isValid() && !setting.toBool()) return true;
  return QMessageBox::question(ctx, title, text,
                               QMessageBox::Ok | QMessageBox::Cancel) ==
         QMessageBox::Ok;
}

void toast(QWidget* ctx, const QString& text) {
  QMessageBox::information(ctx, "AIOrganizerPro", text);
}
}  // namespace

// ---------------- SettingsPage / AboutPage ----------------
SettingsPage::SettingsPage(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(28, 24, 28, 28);
  lay->setSpacing(16);

  auto* title = new QLabel("Pengaturan", this);
  title->setObjectName("pageTitle");
  auto* subtitle = new QLabel(
      "Atur perilaku preview, keamanan aksi file, AI, dan beban thumbnail.",
      this);
  subtitle->setObjectName("pageSubtitle");
  lay->addWidget(title);
  lay->addWidget(subtitle);

  auto* playback = new QGroupBox("Pemutaran", this);
  auto* playbackLay = new QVBoxLayout(playback);
  m_autoplay = new QCheckBox("Putar video otomatis saat dipilih", playback);
  playbackLay->addWidget(m_autoplay);
  playbackLay->addWidget(new QLabel(
      "Matikan untuk library besar supaya pemilihan file hanya memuat preview.",
      playback));

  auto* safety = new QGroupBox("Keamanan & workflow", this);
  auto* safetyLay = new QVBoxLayout(safety);
  m_confirm = new QCheckBox("Konfirmasi sebelum aksi file", safety);
  m_dryRun = new QCheckBox("Default Organizer selalu dry-run", safety);
  safetyLay->addWidget(m_confirm);
  safetyLay->addWidget(m_dryRun);
  safetyLay->addWidget(new QLabel(
      "Dry-run membuat rencana tanpa memindahkan file sampai kamu menerapkannya.",
      safety));

  auto* ai = new QGroupBox("AI", this);
  auto* aiLay = new QVBoxLayout(ai);
  m_llm = new QCheckBox("Izinkan fitur LLM lokal bila tersedia", ai);
  aiLay->addWidget(m_llm);
  aiLay->addWidget(new QLabel(
      "Tidak mengirim file ke layanan online; fitur hanya aktif bila engine lokal tersedia.",
      ai));

  auto* perf = new QGroupBox("Performa", this);
  auto* perfLay = new QHBoxLayout(perf);
  perfLay->addWidget(new QLabel("Thumbnail per batch:", perf));
  m_thumbBatch = new QSpinBox(perf);
  m_thumbBatch->setRange(6, 64);
  m_thumbBatch->setSingleStep(6);
  perfLay->addWidget(m_thumbBatch);
  perfLay->addStretch(1);
  perfLay->addWidget(new QLabel("Lebih tinggi = lebih banyak CPU saat gallery dimuat.", perf));

  lay->addWidget(playback);
  lay->addWidget(safety);
  lay->addWidget(ai);
  lay->addWidget(perf);

  auto* actions = new QHBoxLayout();
  auto* bReset = new QPushButton("Pulihkan default", this);
  auto* bSave = new QPushButton("Simpan pengaturan", this);
  bSave->setObjectName("primaryAction");
  m_status = new QLabel(this);
  actions->addWidget(bReset);
  actions->addWidget(bSave);
  actions->addStretch(1);
  actions->addWidget(m_status);
  lay->addLayout(actions);
  lay->addStretch(1);

  const QJsonObject cfg = m_backend->appSettings();
  m_autoplay->setChecked(cfg.value("autoplay_preview").toBool(true));
  m_confirm->setChecked(cfg.value("confirm_file_actions").toBool(true));
  m_dryRun->setChecked(cfg.value("dry_run_default").toBool(true));
  m_llm->setChecked(cfg.value("llm_enabled").toBool(false));
  m_thumbBatch->setValue(cfg.value("thumbnail_batch").toInt(24));
  qApp->setProperty("aiorg_confirm_actions", m_confirm->isChecked());

  connect(bSave, &QPushButton::clicked, this, &SettingsPage::save);
  connect(bReset, &QPushButton::clicked, this, &SettingsPage::reset);
}

void SettingsPage::save() {
  QJsonObject cfg = m_backend->appSettings();
  cfg["autoplay_preview"] = m_autoplay->isChecked();
  cfg["confirm_file_actions"] = m_confirm->isChecked();
  cfg["dry_run_default"] = m_dryRun->isChecked();
  cfg["llm_enabled"] = m_llm->isChecked();
  cfg["thumbnail_batch"] = m_thumbBatch->value();
  qApp->setProperty("aiorg_confirm_actions", m_confirm->isChecked());
  const bool ok = m_backend->saveAppSettings(cfg);
  m_status->setText(ok ? "Tersimpan" : "Gagal menyimpan");
}

void SettingsPage::reset() {
  m_autoplay->setChecked(true);
  m_confirm->setChecked(true);
  m_dryRun->setChecked(true);
  m_llm->setChecked(false);
  m_thumbBatch->setValue(24);
  save();
}

AboutPage::AboutPage(Backend* backend, QWidget* parent) : QWidget(parent) {
  Q_UNUSED(backend);
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(28, 24, 28, 28);
  lay->setSpacing(16);

  auto* title = new QLabel("Tentang AIOrganizerPro", this);
  title->setObjectName("pageTitle");
  auto* subtitle = new QLabel(
      "Local-first media organizer untuk library video, foto, dokumen, dan workflow AI.",
      this);
  subtitle->setObjectName("pageSubtitle");
  lay->addWidget(title);
  lay->addWidget(subtitle);

  auto* overview = new QGroupBox("AIOrganizerPro 0.4", this);
  auto* ol = new QVBoxLayout(overview);
  ol->addWidget(new QLabel(
      "Desktop native berbasis Qt 6 + C++20 dengan FFmpeg/Qt Multimedia untuk preview.",
      overview));
  ol->addWidget(new QLabel(
      "Core C++ menangani scan, hashing, duplicate detection, dan operasi file terverifikasi.",
      overview));
  ol->addWidget(new QLabel(
      "Python sidecar dipakai untuk integrasi AI/YOLO dan workflow yang memang membutuhkan Python.",
      overview));

  auto* principles = new QGroupBox("Prinsip desain", this);
  auto* pl = new QVBoxLayout(principles);
  for (const QString& s : {
           "Local-first: file tetap di komputer kamu.",
           "Preview-first: aksi organisasi dapat direncanakan sebelum diterapkan.",
           "Responsive UI: pekerjaan berat dijalankan di worker, bukan UI thread.",
           "Tidak ada persistent database bawaan aplikasi."
       })
    pl->addWidget(new QLabel("•  " + s, principles));

  auto* build = new QGroupBox("Runtime", this);
  auto* bl = new QVBoxLayout(build);
  bl->addWidget(new QLabel("Qt 6 · C++20 · Qt Multimedia · FFmpeg · Python/YOLO", build));
  bl->addWidget(new QLabel(
      "Database persistent dinonaktifkan; SQLite tetap tersedia untuk mode :memory: bila core membutuhkannya.",
      build));

  lay->addWidget(overview);
  lay->addWidget(principles);
  lay->addWidget(build);
  lay->addStretch(1);
}

// ---------------- LibraryPage ----------------
LibraryPage::LibraryPage(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(14, 10, 14, 14);
  auto* crumb = new QLabel("Video Organizer   ›   Library   ›   Pilih video untuk melihat detail", this);
  crumb->setStyleSheet("color:#aeb9d2; padding:2px 0;");
  lay->addWidget(crumb);
  auto* top = new QHBoxLayout();
  m_folder = new QLineEdit(this);
  m_folder->setPlaceholderText("D:\\Data");
  auto* bBrowse = new QPushButton("Pilih…", this);
  auto* bPickVideo = new QPushButton("Buka Video…", this);
  auto* bScan = new QPushButton("Scan & Index", this);
  bScan->setObjectName("primaryAction");
  top->addWidget(m_folder, 1);
  top->addWidget(bBrowse);
  top->addWidget(bPickVideo);
  top->addWidget(bScan);
  lay->addLayout(top);
  auto* split = new QSplitter(Qt::Horizontal, this);
  split->setHandleWidth(10);
  split->setChildrenCollapsible(false);

  auto* library = new QWidget(this);
  auto* libraryLay = new QVBoxLayout(library);
  libraryLay->setContentsMargins(0, 0, 0, 0);
  libraryLay->setSpacing(8);
  auto* libraryHead = new QLabel("RAK VIDEO", library);
  libraryHead->setObjectName("sectionLabel");
  auto* filter = new QLineEdit(library);
  filter->setPlaceholderText("Cari nama atau folder…");
  m_gallery = new Gallery(library);
  m_gallery->setThumbnailBatch(
      m_backend->appSettings().value("thumbnail_batch").toInt(24));
  libraryLay->addWidget(libraryHead);
  libraryLay->addWidget(filter);
  libraryLay->addWidget(m_gallery, 1);

  auto* center = new QWidget(this);
  auto* rl = new QVBoxLayout(center);
  rl->setContentsMargins(0, 0, 0, 0);
  rl->setSpacing(10);
  m_player = new VideoPlayer(backend, center);
  m_meta = new QLabel(this);
  m_meta->setWordWrap(true);
  m_status = new QLabel(this);
  m_meta->setStyleSheet("padding:9px; background:#121a2e; border:1px solid #2c3a5d; border-radius:6px; color:#bdc8df;");
  m_status->setStyleSheet("padding:6px; color:#6fdaa0;");
  auto* detailBox = new QGroupBox("▣  Detail Video", center);
  auto* detailLay = new QVBoxLayout(detailBox);
  detailLay->addWidget(m_meta);
  detailLay->addWidget(m_status);
  auto* analysisBox = new QGroupBox("◎  Analisis File", center);
  auto* analysisLay = new QVBoxLayout(analysisBox);
  m_analysis = new QLabel("Pilih video untuk membaca durasi, resolusi, codec, audio, serta status metadata dengan FFprobe.", analysisBox);
  m_analysis->setWordWrap(true);
  m_analysis->setStyleSheet("color:#aeb9d2; padding:4px;");
  analysisLay->addWidget(m_analysis);
  auto* tags = new QLabel("◇  Tag & Kategori dan ▤ Catatan dapat diedit lewat tombol di panel kanan.", analysisBox);
  tags->setWordWrap(true);
  tags->setStyleSheet("color:#a99cff; padding:4px;");
  analysisLay->addWidget(tags);

  auto* actions = new QWidget(this);
  actions->setMinimumWidth(294);
  actions->setMaximumWidth(294);
  auto* acts = new QVBoxLayout(actions);
  acts->setContentsMargins(0, 0, 0, 0);
  acts->setSpacing(9);
  auto* actionTitle = new QLabel("◇  Tools & Aksi", actions);
  actionTitle->setStyleSheet("font-weight:600; color:#edf0fb; padding:9px; background:#161f37; border:1px solid #2c3a5d; border-radius:6px;");
  acts->addWidget(actionTitle);
  const QStringList names{"Buka",  "Lokasi",  "Rename", "Pindah",
                          "Karantina", "Tag", "Catatan", "CekDuplikat"};
  const QStringList ids{"open", "folder",  "rename", "move",
                        "delete", "tags", "note", "dupcheck"};
  for (int i = 0; i < names.size(); ++i) {
    auto* b = new QPushButton(names[i], this);
    if (i == 0) b->setObjectName("primaryAction");
    connect(b, &QPushButton::clicked, this,
            [this, id = ids[i]]() { fileAction(id); });
    acts->addWidget(b);
  }
  auto* quick = new QGroupBox("☼  Quick Analysis", actions);
  auto* ql = new QVBoxLayout(quick);
  m_quick = new QLabel("✓  Duplikat          Perlu dicek\n"
                       "✓  File Rusak       Belum diperiksa\n"
                       "✓  Metadata          Muat video\n"
                       "✓  Ukuran File       —\n"
                       "✓  Tipe File          —", quick);
  m_quick->setStyleSheet("color:#aeb9d2; padding:3px; line-height:1.65;");
  ql->addWidget(m_quick);
  acts->addWidget(quick);
  auto* related = new QGroupBox("◉  Relasi", actions);
  auto* relLay = new QVBoxLayout(related);
  for (const QString& text : {"Lihat semua video di folder ini",
                              "Lihat video dengan tag yang sama",
                              "Lihat video dari tanggal ini"}) {
    auto* link = new QPushButton(text, related);
    link->setObjectName("relationLink");
    relLay->addWidget(link);
  }
  acts->addWidget(related);
  auto* summary = new QGroupBox("▧  Ringkasan", actions);
  auto* sumLay = new QVBoxLayout(summary);
  m_summary = new QLabel("Total di Folder Ini\n— video\n\nTotal Ukuran\n—\n\nDurasi Total\n—", summary);
  m_summary->setStyleSheet("color:#aeb9d2; line-height:1.4;");
  sumLay->addWidget(m_summary);
  acts->addWidget(summary);
  acts->addStretch(1);
  rl->addWidget(m_player, 1);
  rl->addWidget(detailBox, 0);
  rl->addWidget(analysisBox, 0);

  split->addWidget(library);
  split->addWidget(center);
  split->addWidget(actions);
  split->setStretchFactor(0, 0);
  split->setStretchFactor(1, 1);
  split->setStretchFactor(2, 0);
  split->setSizes({310, 760, 290});
  lay->addWidget(split, 1);

  connect(filter, &QLineEdit::textChanged, m_gallery, &Gallery::setFilter);
  connect(bBrowse, &QPushButton::clicked, this, &LibraryPage::browse);
  connect(bPickVideo, &QPushButton::clicked, this, [this]() {
    const QString path = QFileDialog::getOpenFileName(
        this, "Pilih video", m_root,
        "Video (*.mp4 *.mov *.mkv *.avi *.mts *.m2ts *.webm *.wmv *.m4v *.ogv)");
    if (!path.isEmpty()) openSelected(path);
  });
  connect(bScan, &QPushButton::clicked, this, &LibraryPage::scan);
  connect(m_gallery, &Gallery::activated, this, &LibraryPage::openSelected);
  connect(m_player, &VideoPlayer::statusMessage, m_status,
          &QLabel::setText);
}

void LibraryPage::setRoot(const QString& root) {
  m_root = root.trimmed();
  m_folder->setText(m_root);
  refreshList();
}

void LibraryPage::browse() {
  const QString d = QFileDialog::getExistingDirectory(
      this, "Pilih folder video", m_folder->text());
  if (!d.isEmpty()) {
    m_folder->setText(d);
    m_root = d;
    refreshList();
  }
}

void LibraryPage::scan() {
  const QString folder = m_folder->text().trimmed();
  if (folder.isEmpty()) return;
  m_root = folder;
  m_status->setText("Scanning…");
  const int workers = qMax(1, QThread::idealThreadCount());
  runAsync(
      this,
      [b = m_backend, folder, workers]() {
        return b->runCore({"scan", folder, "--db", b->activeDb(), "--json",
                           "--actor", "gui", "--workers", QString::number(workers)});
      },
      [this](CoreResult r) {
        m_status->setText(r.ok ? "Scan selesai." : ("Scan gagal: " + r.error));
        refreshList();
      });
}

void LibraryPage::refreshList() {
  const QString root = m_root;
  if (root.isEmpty()) return;
  runAsync(
      this, [b = m_backend, root]() { return listMedia(b, root, true); },
      [this, root](QList<GalleryItem> items) {
        if (root != m_root) return;
        m_gallery->setItems(items, true);
        m_status->setText(QString("%1 video.").arg(items.size()));
        qint64 bytes = 0;
        for (const auto& item : items) bytes += item.size;
        m_summary->setText(QString("Total di Folder Ini\n%1 video\n\nTotal Ukuran\n%2 MB\n\nDurasi Total\nPilih video")
                               .arg(items.size()).arg(bytes / 1048576.0, 0, 'f', 1));
      });
}

void LibraryPage::openSelected(const QString& path) {
  if (path.isEmpty()) return;
  m_current = path;
  m_player->load(path);
  const QFileInfo fi(path);
  m_meta->setText(QString("%1  ·  %2 · memuat metadata…")
                     .arg(fi.fileName())
                     .arg(fi.suffix().toUpper()));
  m_analysis->setText("Membaca metadata video di worker…");
  m_status->setText("Preview dibuka · analisis berjalan di background");
  m_quick->setText(QString("✓  Tipe File          %1\n✓  Ukuran File       %2\n…  Metadata          Memuat…\n…  Duplikat          Belum dicek\n…  File Rusak       Belum dicek")
                       .arg(fi.suffix().toUpper())
                       .arg(fi.size() >= 1048576
                                ? QString::number(fi.size() / 1048576.0, 'f', 1) + " MB"
                                : QString::number(fi.size() / 1024.0, 'f', 0) + " KB"));
  runAsync(
      this,
      [b = m_backend, path]() {
        return b->sidecar("video-inspect", {{"path", path}}, 120000);
      },
      [this, path](QJsonObject r) {
        if (m_current != path) return;
        if (!r.value("ok").toBool()) {
          m_analysis->setText("Metadata belum dapat dibaca: " + r.value("error").toString());
          m_status->setText("Preview siap · metadata terbatas");
          return;
        }
        const QJsonObject pr = r.value("probe").toObject();
        const QJsonObject v = pr.value("video").toObject();
        const double seconds = pr.value("duration").toDouble();
        const QString duration = seconds > 0 ? QString::number(seconds, 'f', 1) + " dtk" : "—";
        const QString audio = pr.value("audio").toObject().value("codec").toString("Tidak ada");
        m_meta->setText(QString("%1  ·  %2  ·  %3 × %4  ·  %5")
                            .arg(QFileInfo(path).fileName())
                            .arg(duration)
                            .arg(v.value("width").toInt())
                            .arg(v.value("height").toInt())
                            .arg(v.value("codec").toString("—")));
        m_analysis->setText(QString("✓ FFprobe berhasil\n"
                                    "• Video: %1 (%2 × %3)\n"
                                    "• Audio: %4\n"
                                    "• Durasi: %5\n\n"
                                    "Preview siap. Aksi file tetap berjalan lewat worker.")
                                .arg(v.value("codec").toString("—"))
                                .arg(v.value("width").toInt())
                                .arg(v.value("height").toInt())
                                .arg(audio)
                                .arg(duration));
        m_quick->setText(QString("✓  Tipe File          %1\n✓  Ukuran File       %2 MB\n✓  Metadata          Lengkap\n…  Duplikat          Klik CekDuplikat\n✓  File Rusak       Tidak terdeteksi")
                             .arg(QFileInfo(path).suffix().toUpper())
                             .arg(QFileInfo(path).size() / 1048576.0, 0, 'f', 1));
        m_status->setText("Preview siap · metadata lengkap");
      });
}

void LibraryPage::fileAction(const QString& action) {
  if (m_current.isEmpty()) {
    toast(this, "Pilih video di galeri dahulu.");
    return;
  }
  const QString path = m_current;
  if (action == "open") {
    QDesktopServices::openUrl(QUrl::fromLocalFile(path));
  } else if (action == "folder") {
    QProcess::startDetached("explorer.exe", {"/select," + path});
  } else if (action == "rename") {
    const QString v = askText(this, "Rename", "Nama baru:",
                              QFileInfo(path).fileName());
    if (v.isEmpty()) return;
    runAsync(
        this,
        [b = m_backend, path, v]() {
          return b->sidecar("video-rename",
                            {{"path", path}, {"new_name", v}});
        },
        [this](QJsonObject r) {
          if (!r.value("ok").toBool()) {
            toast(this, "Rename gagal: " + r.value("error").toString());
            return;
          }
          m_current = r.value("path").toString();
          m_player->load(m_current);
          refreshList();
        });
  } else if (action == "move") {
    const QString v = askText(this, "Pindah", "Folder tujuan:",
                              QFileInfo(path).absolutePath());
    if (v.isEmpty()) return;
    runAsync(
        this,
        [b = m_backend, path, v]() {
          return b->sidecar("video-move",
                            {{"path", path}, {"destination", v}});
        },
        [this](QJsonObject r) {
          if (!r.value("ok").toBool()) {
            toast(this, "Pindah gagal: " + r.value("error").toString());
            return;
          }
          m_current = r.value("path").toString();
          m_player->load(m_current);
          refreshList();
        });
  } else if (action == "delete") {
    if (!askConfirm(this, "Karantina",
                    "Pindah ke 99_To-Delete (bisa dipulihkan, bukan hapus)?"))
      return;
    runAsync(
        this,
        [b = m_backend, path]() { return b->sidecar("video-quarantine", {{"path", path}}); },
        [this](QJsonObject r) {
          if (!r.value("ok").toBool()) {
            toast(this, "Karantina gagal: " + r.value("error").toString());
            return;
          }
          m_current.clear();
          m_player->load({});
          refreshList();
        });
  } else if (action == "tags" || action == "note") {
    const QJsonObject a = m_backend->annotationFor(path);
    QStringList tags;
    for (const QJsonValue& t : a.value("tags").toArray())
      tags << t.toString();
    if (action == "tags") {
      const QString v =
          askText(this, "Tag", "Koma-pisah:", tags.join(", "));
      if (v.isNull()) return;
      tags = v.split(',', Qt::SkipEmptyParts);
      for (QString& t : tags) t = t.trimmed();
    }
    QString note = a.value("note").toString();
    if (action == "note") {
      bool ok = false;
      const QString v = QInputDialog::getMultiLineText(this, "Catatan",
                                                       "Catatan:", note, &ok);
      if (!ok) return;
      note = v;
    }
    if (m_backend->saveAnnotation(path, tags, note))
      toast(this, "Anotasi disimpan.");
    else
      toast(this, "Gagal menyimpan anotasi.");
  } else if (action == "dupcheck") {
    runAsync(
        this,
        [b = m_backend, path]() {
          return b->sidecar("video-duplicate-check", {{"path", path}});
        },
        [this](QJsonObject r) {
          if (!r.value("ok").toBool()) {
            m_status->setText("Cek duplikat gagal.");
            return;
          }
          m_status->setText(r.value("duplicate").toBool()
                                ? "Duplikat exact ditemukan."
                                : "Tidak ada duplikat exact.");
        });
  }
}

// ---------------- PhotoPage ----------------
PhotoPage::PhotoPage(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  auto* top = new QHBoxLayout();
  m_folder = new QLineEdit(this);
  m_folder->setPlaceholderText("D:\\Photos");
  auto* bBrowse = new QPushButton("Pilih…", this);
  auto* bLoad = new QPushButton("Muat Foto", this);
  top->addWidget(m_folder, 1);
  top->addWidget(bBrowse);
  top->addWidget(bLoad);
  lay->addLayout(top);
  auto* split = new QSplitter(Qt::Horizontal, this);
  auto* left = new QWidget(this);
  auto* ll = new QVBoxLayout(left);
  m_gallery = new Gallery(this);
  ll->addWidget(m_gallery, 1);
  auto* filter = new QLineEdit(this);
  filter->setPlaceholderText("Cari nama/path…");
  ll->addWidget(filter);
  auto* right = new QWidget(this);
  auto* rl = new QVBoxLayout(right);
  m_viewer = new PhotoViewer(this);
  m_meta = new QLabel(this);
  m_meta->setWordWrap(true);
  m_annot = new QLabel("Belum ada tag/catatan.", this);
  m_annot->setWordWrap(true);
  m_yolo = new QLabel(this);
  m_yolo->setWordWrap(true);
  auto* zoom = new QHBoxLayout();
  const QStringList zn{"Fit", "-", "+", "Buka"};
  const QStringList zi{"fit", "out", "in", "open"};
  for (int i = 0; i < zn.size(); ++i) {
    auto* b = new QPushButton(zn[i], this);
    connect(b, &QPushButton::clicked, this, [this, id = zi[i]]() {
      if (id == "fit") m_viewer->zoomFit();
      else if (id == "out") m_viewer->zoomOut();
      else if (id == "in") m_viewer->zoomIn();
      else if (!m_current.isEmpty())
        QDesktopServices::openUrl(QUrl::fromLocalFile(m_current));
    });
    zoom->addWidget(b);
  }
  auto* acts = new QHBoxLayout();
  const QStringList names{"Rename", "Pindah", "Karantina", "Tag", "Catatan",
                          "YOLO"};
  const QStringList ids{"rename", "move", "delete", "tags", "note", "yolo"};
  for (int i = 0; i < names.size(); ++i) {
    auto* b = new QPushButton(names[i], this);
    connect(b, &QPushButton::clicked, this,
            [this, id = ids[i]]() { photoAction(id); });
    acts->addWidget(b);
  }
  rl->addWidget(m_viewer, 1);
  rl->addWidget(m_meta);
  rl->addWidget(m_annot);
  rl->addWidget(m_yolo);
  rl->addLayout(zoom);
  rl->addLayout(acts);
  split->addWidget(left);
  split->addWidget(right);
  split->setStretchFactor(0, 1);
  split->setStretchFactor(1, 1);
  lay->addWidget(split, 1);
  connect(bBrowse, &QPushButton::clicked, this, &PhotoPage::browse);
  connect(bLoad, &QPushButton::clicked, this, &PhotoPage::load);
  connect(m_gallery, &Gallery::activated, this, &PhotoPage::onPhoto);
  connect(filter, &QLineEdit::textChanged, m_gallery, &Gallery::setFilter);
  connect(m_viewer, &PhotoViewer::metaMessage, this, [this](const QString& t) {
    m_meta->setText(m_current + "  •  " + t);
  });
}

void PhotoPage::setRoot(const QString& root) {
  m_root = root.trimmed();
  m_folder->setText(m_root);
  load();
}

void PhotoPage::browse() {
  const QString d = QFileDialog::getExistingDirectory(
      this, "Pilih folder foto", m_folder->text());
  if (!d.isEmpty()) {
    m_folder->setText(d);
    m_root = d;
    load();
  }
}

void PhotoPage::load() {
  const QString folder = m_folder->text().trimmed().isEmpty()
                             ? m_root
                             : m_folder->text().trimmed();
  if (folder.isEmpty()) return;
  m_root = folder;
  runAsync(
      this, [b = m_backend, folder]() { return listMedia(b, folder, false); },
      [this, folder](QList<GalleryItem> items) {
        if (folder != m_root) return;
        m_gallery->setItems(items, false);
      });
}

void PhotoPage::onPhoto(const QString& path) {
  if (!m_viewer->load(path)) {
    toast(this, "Foto tak terbaca: " + path);
    return;
  }
  m_current = path;
  const QJsonObject a = m_backend->annotationFor(path);
  m_currentAnnot = a;
  QStringList tags;
  for (const QJsonValue& t : a.value("tags").toArray())
    tags << t.toString();
  m_annot->setText("Tag: " + (tags.isEmpty() ? "-" : tags.join(", ")) +
                   "  •  " + a.value("note").toString());
  m_yolo->clear();
}

void PhotoPage::photoAction(const QString& action) {
  if (m_current.isEmpty()) {
    toast(this, "Pilih foto dahulu.");
    return;
  }
  const QString path = m_current;
  if (action == "yolo") {
    classifyYolo();
    return;
  }
  if (action == "rename" || action == "move" || action == "delete") {
    QString cmd, key, val;
    if (action == "rename") {
      const QString v = askText(this, "Rename foto", "Nama baru:",
                                QFileInfo(path).fileName());
      if (v.isEmpty()) return;
      cmd = "video-rename";
      key = "new_name";
      val = v;
    } else if (action == "move") {
      const QString v = askText(this, "Pindah foto", "Folder tujuan:",
                                QFileInfo(path).absolutePath());
      if (v.isEmpty()) return;
      cmd = "video-move";
      key = "destination";
      val = v;
    } else {
      if (!askConfirm(this, "Karantina",
                      "Pindah ke 99_To-Delete (bisa dipulihkan)?"))
        return;
      cmd = "video-quarantine";
    }
    runAsync(
        this,
        [b = m_backend, cmd, path, key, val]() {
          QJsonObject ex{{"path", path}};
          if (!key.isEmpty()) ex[key] = val;
          return b->sidecar(cmd, ex);
        },
        [this, action](QJsonObject r) {
          if (!r.value("ok").toBool()) {
            toast(this, "Gagal: " + r.value("error").toString());
            return;
          }
          if (action == "delete") m_current.clear();
          else m_current = r.value("path").toString();
          load();
        });
  } else if (action == "tags" || action == "note") {
    QStringList tags;
    for (const QJsonValue& t : m_currentAnnot.value("tags").toArray())
      tags << t.toString();
    QString note = m_currentAnnot.value("note").toString();
    if (action == "tags") {
      const QString v = askText(this, "Tag foto", "Koma-pisah:",
                                tags.join(", "));
      if (v.isNull()) return;
      tags = v.split(',', Qt::SkipEmptyParts);
      for (QString& t : tags) t = t.trimmed();
    } else {
      bool ok = false;
      const QString v = QInputDialog::getMultiLineText(this, "Catatan foto",
                                                       "Catatan:", note, &ok);
      if (!ok) return;
      note = v;
    }
    if (m_backend->saveAnnotation(path, tags, note)) {
      m_currentAnnot = m_backend->annotationFor(path);
      onPhoto(path);
    }
  }
}

void PhotoPage::classifyYolo() {
  if (m_current.isEmpty()) {
    toast(this, "Pilih foto dahulu.");
    return;
  }
  m_yolo->setText("Mengklasifikasi…");
  runAsync(
      this,
      [b = m_backend, p = m_current]() {
        return b->yoloClassify(QFileInfo(p).absolutePath(), 500);
      },
      [this](QJsonObject r) {
        if (!r.value("ok").toBool()) {
          m_yolo->setText("YOLO: " + r.value("error").toString());
          return;
        }
        QString out = "YOLO: tak ter-cover limit.";
        for (const QJsonValue& v : r.value("rows").toArray()) {
          const QJsonObject o = v.toObject();
          if (o.value("path").toString().compare(m_current,
                                                 Qt::CaseInsensitive) == 0) {
            out = QString("YOLO: %1 (%2, %3)")
                      .arg(o.value("kelas").toString())
                      .arg(o.value("confidence").toDouble())
                      .arg(o.value("level").toString());
            break;
          }
        }
        m_yolo->setText(out);
      });
}

// ---------------- DuplicatesPage ----------------
DuplicatesPage::DuplicatesPage(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  auto* top = new QHBoxLayout();
  m_folder = new QLineEdit(this);
  m_folder->setPlaceholderText("D:\\Data");
  m_minSize = new QSpinBox(this);
  m_minSize->setRange(1, 1000000000);
  m_minSize->setValue(1);
  auto* bFind = new QPushButton("Cari Duplikat", this);
  top->addWidget(m_folder, 1);
  top->addWidget(m_minSize);
  top->addWidget(bFind);
  lay->addLayout(top);
  m_groups = new QTreeWidget(this);
  m_groups->setHeaderLabels({"Grup", "Ukuran", "SHA-256", "Path"});
  lay->addWidget(m_groups, 1);
  auto* acts = new QHBoxLayout();
  auto* bMove = new QPushButton("Simpan + Karantina", this);
  bMove->setObjectName("primaryAction");
  m_status = new QLabel(this);
  acts->addWidget(bMove);
  acts->addWidget(m_status, 1);
  lay->addLayout(acts);
  connect(bFind, &QPushButton::clicked, this, &DuplicatesPage::find);
  connect(bMove, &QPushButton::clicked, this,
          [this]() { act("move"); });
}

void DuplicatesPage::find() {
  const QString folder = m_folder->text().trimmed();
  if (folder.isEmpty()) return;
  m_status->setText("Hashing…");
  m_groups->clear();
  runAsync(
      this,
      [b = m_backend, folder, mn = m_minSize->value()]() {
        return b->runCore({"duplicates", folder, "--db", b->activeDb(),
                           "--json", "--actor", "gui", "--min-size",
                           QString::number(mn), "--workers",
                           QString::number(qMax(1, QThread::idealThreadCount()))},
                          1800000);
      },
      [this](CoreResult r) {
        if (!r.ok) {
          m_status->setText("Gagal: " + r.error);
          return;
        }
        const QJsonArray groups = r.json.value("groups").toArray();
        for (const QJsonValue& gv : groups) {
          const QJsonObject g = gv.toObject();
          auto* top = new QTreeWidgetItem(
              m_groups, {QString("Grup %1").arg(g.value("id").toInt()),
                         QString::number(qint64(g.value("size").toDouble())),
                         g.value("sha256").toString().left(20)});
          top->setData(0, Qt::UserRole, g.value("id").toInt());
          for (const QJsonValue& pv : g.value("paths").toArray()) {
            auto* ch = new QTreeWidgetItem(top, {"", "", "", pv.toString()});
            ch->setData(0, Qt::UserRole, pv.toString());
          }
        }
        m_groups->expandAll();
        m_status->setText(QString("%1 grup.").arg(groups.size()));
      });
}

void DuplicatesPage::act(const QString& action) {
  QTreeWidgetItem* top = m_groups->currentItem();
  while (top && top->parent()) top = top->parent();
  if (!top || top->parent()) {
    toast(this, "Pilih salah satu grup dahulu.");
    return;
  }
  QStringList paths;
  for (int i = 0; i < top->childCount(); ++i)
    paths << top->child(i)->text(3);
  if (paths.isEmpty()) return;
  const QString keep = QInputDialog::getItem(this, "File canonical",
                                             "Pertahankan:", paths, 0, false);
  if (keep.isEmpty()) return;
  const QString to = askText(this, action == "move" ? "Karantina" : "Proposal",
                             "Folder tujuan:",
                             m_folder->text().trimmed() + "/__duplikat__");
  if (to.isEmpty()) return;
  if (action != "move") return;
  if (!askConfirm(this, "Pindah ke karantina",
                  QString("Pertahankan %1, pindahkan %2 file duplikat ke %3?")
                      .arg(QFileInfo(keep).fileName())
                      .arg(paths.size() - 1)
                      .arg(to)))
    return;

  runAsync(
      this,
      [paths, keep, to]() {
        QJsonObject result{{"ok", true}, {"moved", 0}, {"failed", 0}};
        QJsonArray failures;
        for (const QString& path : paths) {
          if (QFileInfo(path).absoluteFilePath().compare(
                  QFileInfo(keep).absoluteFilePath(), Qt::CaseInsensitive) == 0)
            continue;
          const QString dst = QDir(to).filePath(QFileInfo(path).fileName());
          const QJsonObject r = Backend::moveVerified(path, dst);
          if (r.value("ok").toBool()) {
            result["moved"] = result.value("moved").toInt() + 1;
          } else {
            result["failed"] = result.value("failed").toInt() + 1;
            failures.append(path + " → " + r.value("error").toString());
          }
        }
        result["failures"] = failures;
        result["ok"] = result.value("failed").toInt() == 0;
        return result;
      },
      [this](QJsonObject r) {
        const int moved = r.value("moved").toInt();
        const int failed = r.value("failed").toInt();
        if (failed == 0)
          m_status->setText(QString("%1 file dipindah · database tidak diperlukan.")
                                .arg(moved));
        else
          m_status->setText(QString("%1 dipindah · %2 gagal.").arg(moved).arg(failed));
        find();
      });
}

// ---------------- OrganizePage ----------------
OrganizePage::OrganizePage(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  auto* form = new QFormLayout();
  m_kind = new QComboBox(this);
  m_kind->addItems({"Video", "Foto"});
  m_folder = new QLineEdit(this);
  m_dest = new QLineEdit(this);
  m_dest->setPlaceholderText("Tujuan (opsional)");
  m_content = new QLineEdit(this);
  m_content->setPlaceholderText("*liburan*=>03_Content/Liburan");
  form->addRow("Jenis:", m_kind);
  form->addRow("Folder:", m_folder);
  form->addRow("Dest:", m_dest);
  form->addRow("Content:", m_content);
  lay->addLayout(form);
  auto* opts = new QHBoxLayout();
  auto* cApply = new QCheckBox("Terapkan", this);
  cApply->setChecked(
      !m_backend->appSettings().value("dry_run_default").toBool(true));
  auto* cCopy = new QCheckBox("Copy saja", this);
  auto* cDated = new QCheckBox("Nama tanggal", this);
  auto* cJunk = new QCheckBox("Junk→99_To-Delete", this);
  auto* cPrune = new QCheckBox("Prune kosong", this);
  auto* bPlan = new QPushButton("Rencana", this);
  auto* bApply = new QPushButton("Terapkan", this);
  opts->addWidget(cApply);
  opts->addWidget(cCopy);
  opts->addWidget(cDated);
  opts->addWidget(cJunk);
  opts->addWidget(cPrune);
  opts->addWidget(bPlan);
  opts->addWidget(bApply);
  lay->addLayout(opts);
  m_out = new QPlainTextEdit(this);
  m_out->setReadOnly(true);
  lay->addWidget(m_out, 1);
  connect(bPlan, &QPushButton::clicked, this,
          [this, cCopy, cDated, cJunk, cPrune]() {
            planOpts(cCopy->isChecked(), cDated->isChecked(),
                     cJunk->isChecked(), cPrune->isChecked(), false);
          });
  connect(bApply, &QPushButton::clicked, this,
          [this, cCopy, cDated, cJunk, cPrune, cApply]() {
            planOpts(cCopy->isChecked(), cDated->isChecked(),
                     cJunk->isChecked(), cPrune->isChecked(),
                     cApply->isChecked());
          });
}

void OrganizePage::planOpts(bool copy, bool dated, bool junk, bool prune,
                             bool apply) {
  const QString folder = m_folder->text().trimmed();
  if (folder.isEmpty()) return;
  if (apply && !askConfirm(this, "Terapkan",
                           "File dipindah sesuai rencana di " + folder + "?"))
    return;
  m_out->setPlainText(apply ? "Menerapkan…" : "Merencanakan…");
  const QStringList content =
      m_content->text().split(';', Qt::SkipEmptyParts);
  runAsync(
      this,
      [b = m_backend, folder, kind = m_kind->currentIndex(),
       dest = m_dest->text().trimmed(), content, copy, dated, junk, prune,
       apply]() {
        QStringList argv{kind == 1 ? "organize-images" : "organize-videos",
                         folder};
        if (!dest.isEmpty()) argv << "--dest-root" << dest;
        for (const QString& c : content)
          if (c.contains("=>")) argv << "--content" << c.trimmed();
        if (copy) argv << "--apply-copy";
        if (dated) argv << "--rename-dated";
        if (junk) argv << "--junk-to-delete";
        if (prune) argv << "--prune-empty";
        argv << (apply ? "--apply" : "--dry-run");
        return b->aiEngine(argv);
      },
      [this](QJsonObject r) {
        m_out->setPlainText(r.value("output").toString().right(12000) +
                            (r.contains("report") && !r.value("report").toString().isEmpty()
                                 ? "\n\nLaporan: " + r.value("report").toString()
                                 : ""));
      });
}

// ---------------- AiPage ----------------
AiPage::AiPage(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  auto* top = new QHBoxLayout();
  m_mode = new QComboBox(this);
  m_mode->addItems({"video-broken", "image-broken", "size", "analyze", "scan",
                    "karantina", "yolo-classify"});
  m_folder = new QLineEdit(this);
  m_folder->setPlaceholderText("D:\\Data");
  m_limit = new QSpinBox(this);
  m_limit->setRange(0, 1000000);
  auto* bRun = new QPushButton("Jalankan", this);
  top->addWidget(m_mode);
  top->addWidget(m_folder, 1);
  top->addWidget(m_limit);
  top->addWidget(bRun);
  lay->addLayout(top);
  m_out = new QPlainTextEdit(this);
  m_out->setReadOnly(true);
  lay->addWidget(m_out, 2);
  // Kartu training YOLO.
  auto* train = new QHBoxLayout();
  m_yoloStatus = new QLabel("YOLO: belum dicek.", this);
  m_yoloStatus->setWordWrap(true);
  auto* bRefresh = new QPushButton("Status", this);
  m_epochs = new QSpinBox(this);
  m_epochs->setRange(1, 2000);
  m_epochs->setValue(150);
  m_epochs->setPrefix("epoch ");
  m_batch = new QSpinBox(this);
  m_batch->setRange(1, 512);
  m_batch->setValue(16);
  m_batch->setPrefix("batch ");
  m_size = new QComboBox(this);
  m_size->addItems({"n", "s", "m", "l", "x"});
  m_size->setCurrentText("m");
  m_imgsz = new QSpinBox(this);
  m_imgsz->setRange(64, 1280);
  m_imgsz->setValue(288);
  m_patience = new QSpinBox(this);
  m_patience->setRange(0, 500);
  m_patience->setValue(25);
  auto* bStart = new QPushButton("Latih", this);
  auto* bStop = new QPushButton("Stop", this);
  train->addWidget(bRefresh);
  train->addWidget(m_epochs);
  train->addWidget(m_batch);
  train->addWidget(m_size);
  train->addWidget(m_imgsz);
  train->addWidget(m_patience);
  train->addWidget(bStart);
  train->addWidget(bStop);
  lay->addLayout(train);
  lay->addWidget(m_yoloStatus);
  m_yoloClasses = new QLabel(this);
  m_yoloClasses->setWordWrap(true);
  lay->addWidget(m_yoloClasses);
  m_yoloLog = new QPlainTextEdit(this);
  m_yoloLog->setReadOnly(true);
  m_yoloLog->setMaximumBlockCount(200);
  lay->addWidget(m_yoloLog, 1);
  m_docs = new QTableWidget(0, 4, this);
  m_docs->setHorizontalHeaderLabels({"Kategori", "Conf", "Saran nama", "Path"});
  m_docs->horizontalHeader()->setStretchLastSection(true);
  m_docs->setMaximumHeight(180);
  lay->addWidget(m_docs);
  m_poll = new QTimer(this);
  m_poll->setInterval(4000);
  connect(bRun, &QPushButton::clicked, this, &AiPage::runAi);
  connect(bRefresh, &QPushButton::clicked, this, &AiPage::refreshYolo);
  connect(bStart, &QPushButton::clicked, this, &AiPage::startTrain);
  connect(bStop, &QPushButton::clicked, this, &AiPage::stopTrain);
  connect(m_poll, &QTimer::timeout, this, [this]() {
    runAsync(
        this, [b = m_backend]() { return b->yoloTrainStatus(); },
        [this](QJsonObject r) {
          const QStringList tail;
          QStringList lines;
          for (const QJsonValue& v : r.value("log_tail").toArray())
            lines << v.toString();
          m_yoloLog->setPlainText(lines.join('\n'));
          if (!r.value("running").toBool()) {
            m_poll->stop();
            refreshYolo();
          }
        });
  });
  refreshYolo();
  loadDocs();
}

void AiPage::loadDocs() {
  runAsync(
      this, [b = m_backend]() { return b->sidecar("docs", {{"limit", 200}}); },
      [this](QJsonObject r) {
        m_docs->setRowCount(0);
        if (!r.value("ok").toBool()) return;
        for (const QJsonValue& v : r.value("docs").toArray()) {
          const QJsonObject d = v.toObject();
          const int row = m_docs->rowCount();
          m_docs->insertRow(row);
          m_docs->setItem(row, 0,
                          new QTableWidgetItem(d.value("kategori").toString()));
          m_docs->setItem(row, 1, new QTableWidgetItem(QString::number(
                                           d.value("confidence").toDouble(), 'f', 2)));
          m_docs->setItem(row, 2, new QTableWidgetItem(
                                       d.value("saran_nama").toString()));
          m_docs->setItem(row, 3,
                          new QTableWidgetItem(d.value("path").toString()));
        }
      });
}

void AiPage::runAi() {
  const QString folder = m_folder->text().trimmed();
  if (folder.isEmpty()) return;
  const QString mode = m_mode->currentText();
  if ((mode == "karantina" || mode == "yolo-classify") &&
      !askConfirm(this, "Jalankan",
                  "Dry-run MATI? Mode ini bisa memindahkan file. Lanjut?"))
    return;
  m_out->setPlainText("Berjalan…");
  runAsync(
      this,
      [b = m_backend, mode, folder, lim = m_limit->value()]() {
        QStringList argv{mode, folder, "--dry-run"};
        if ((mode == "analyze" || mode == "yolo-classify") && lim > 0)
          argv << "--limit" << QString::number(lim);
        return b->aiEngine(argv);
      },
      [this](QJsonObject r) {
        m_out->setPlainText(r.value("output").toString().right(12000));
        loadDocs();
      });
}

void AiPage::refreshYolo() {
  m_yoloStatus->setText("Memeriksa…");
  runAsync(
      this, [b = m_backend]() { return b->yoloStatus(); },
      [this](QJsonObject r) {
        if (!r.value("ok").toBool()) {
          m_yoloStatus->setText("YOLO: " + r.value("error").toString());
          return;
        }
        const QJsonObject cls = r.value("classes").toObject();
        QStringList parts;
        for (auto it = cls.begin(); it != cls.end(); ++it)
          parts << QString("%1:%2").arg(it.key()).arg(it.value().toInt());
        m_yoloStatus->setText(
            QString("%1 • model %2%3")
                .arg(r.value("ready").toBool() ? "Model siap"
                                               : r.value("ready_note").toString())
                .arg(QFileInfo(r.value("model").toString()).fileName())
                .arg(r.value("train").toObject().value("running").toBool()
                         ? " • TRAINING BERJALAN"
                         : ""));
        m_yoloClasses->setText(
            QString("dataset_raw: %1 gambar — %2")
                .arg(r.value("class_total").toInt())
                .arg(parts.join(" · ")));
        const QJsonObject t = r.value("train").toObject();
        if (t.value("running").toBool() && !m_poll->isActive())
          m_poll->start();
      });
}

void AiPage::startTrain() {
  if (!askConfirm(this, "Latih YOLO",
                  "Training background (bisa jam-jaman). Lanjut?"))
    return;
  runAsync(
      this,
      [b = m_backend, e = m_epochs->value(), bt = m_batch->value(),
       s = m_size->currentText(), im = m_imgsz->value(),
       p = m_patience->value()]() {
        return b->yoloTrainStart(e, bt, s, im, p);
      },
      [this](QJsonObject r) {
        if (!r.value("ok").toBool()) {
          toast(this, "Gagal mulai: " + r.value("error").toString());
          return;
        }
        toast(this, QString("Training dimulai (pid %1).").arg(r.value("pid").toInt()));
        m_poll->start();
        refreshYolo();
      });
}

void AiPage::stopTrain() {
  if (!askConfirm(this, "Stop", "Hentikan training yang berjalan?")) return;
  runAsync(
      this, [b = m_backend]() { return b->yoloTrainStop(); },
      [this](QJsonObject r) {
        m_poll->stop();
        toast(this, r.value("stopped").toBool() ? "Training dihentikan."
                                                : "Tidak ada training berjalan.");
        refreshYolo();
      });
}

// ---------------- JobsPage ----------------
JobsPage::JobsPage(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  auto* top = new QHBoxLayout();
  m_kind = new QComboBox(this);
  m_kind->addItems({"scan", "duplicates", "ai", "organize"});
  m_kind->setEditable(true);
  m_payload = new QLineEdit(this);
  m_payload->setPlaceholderText("{\"folder\":\"D:\\\\Data\"}");
  auto* bAdd = new QPushButton("Tambah", this);
  auto* bClaim = new QPushButton("Ambil 1", this);
  auto* bRun = new QPushButton("Jalankan antrean", this);
  auto* bRefresh = new QPushButton("Refresh", this);
  top->addWidget(m_kind);
  top->addWidget(m_payload, 1);
  top->addWidget(bAdd);
  top->addWidget(bClaim);
  top->addWidget(bRun);
  top->addWidget(bRefresh);
  lay->addLayout(top);
  m_table = new QTableWidget(0, 4, this);
  m_table->setHorizontalHeaderLabels({"#", "Kind", "Status", "Payload"});
  m_table->horizontalHeader()->setStretchLastSection(true);
  lay->addWidget(m_table, 1);
  auto* acts = new QHBoxLayout();
  for (const char* a : {"pause", "resume", "cancel"}) {
    auto* b = new QPushButton(a, this);
    connect(b, &QPushButton::clicked, this,
            [this, act = QString(a)]() { this->act(act); });
    acts->addWidget(b);
  }
  lay->addLayout(acts);
  connect(bAdd, &QPushButton::clicked, this, &JobsPage::enqueue);
  connect(bClaim, &QPushButton::clicked, this, &JobsPage::claim);
  connect(bRun, &QPushButton::clicked, this, &JobsPage::runOnce);
  connect(bRefresh, &QPushButton::clicked, this, &JobsPage::refresh);
  refresh();
}

static int selectedJobId(QTableWidget* t) {
  const int row = t->currentRow();
  if (row < 0) return -1;
  return t->item(row, 0) ? t->item(row, 0)->text().toInt() : -1;
}

void JobsPage::refresh() {
  runAsync(
      this,
      [b = m_backend]() {
        return b->sidecar("job", {{"action", "list"}, {"limit", 50}});
      },
      [this](QJsonObject r) {
        m_table->setRowCount(0);
        if (!r.value("ok").toBool()) return;
        for (const QJsonValue& v : r.value("jobs").toArray()) {
          const QJsonObject j = v.toObject();
          const int row = m_table->rowCount();
          m_table->insertRow(row);
          m_table->setItem(row, 0,
                           new QTableWidgetItem(QString::number(j.value("id").toInt())));
          m_table->setItem(row, 1,
                           new QTableWidgetItem(j.value("kind").toString()));
          m_table->setItem(row, 2,
                           new QTableWidgetItem(j.value("status").toString()));
          m_table->setItem(row, 3, new QTableWidgetItem(
                                       j.value("payload").toString()));
        }
      });
}

void JobsPage::enqueue() {
  if (m_payload->text().trimmed().isEmpty()) return;
  runAsync(
      this,
      [b = m_backend, k = m_kind->currentText(),
       p = m_payload->text().trimmed()]() {
        return b->sidecar(
            "job", {{"action", "enqueue"}, {"kind", k}, {"payload", p}});
      },
      [this](QJsonObject r) {
        toast(this, r.value("ok").toBool() ? "Job ditambahkan."
                                           : ("Gagal: " + r.value("error").toString()));
        refresh();
      });
}

void JobsPage::claim() {
  runAsync(
      this, [b = m_backend]() { return b->sidecar("job", {{"action", "claim"}}); },
      [this](QJsonObject r) {
        toast(this, r.value("ok").toBool() ? "Job diambil."
                                           : "Tidak ada job pending.");
        refresh();
      });
}

void JobsPage::runOnce() {
  // Worker jalan di sidecar Python (data/jobs.json): claim -> eksekusi -> finish.
  runAsync(
      this,
      [b = m_backend]() { return b->sidecar("job", {{"action", "run-once"}}); },
      [this](QJsonObject r) {
        toast(this, r.value("ran").toBool()
                        ? (r.value("ok").toBool() ? "Job selesai." : "Job gagal.")
                        : "Tidak ada job pending.");
        refresh();
      });
}

void JobsPage::act(const QString& action) {
  const int id = selectedJobId(m_table);
  if (id < 0) {
    toast(this, "Pilih job dahulu.");
    return;
  }
  runAsync(
      this,
      [b = m_backend, action, id]() {
        return b->sidecar(
            "job", {{"action", action}, {"id", id}});
      },
      [this](QJsonObject r) {
        toast(this, r.value("ok").toBool()
                        ? "OK."
                        : ("Gagal: " + r.value("error").toString()));
        refresh();
      });
}

// ---------------- DbPage ----------------
DbPage::DbPage(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  auto* top = new QHBoxLayout();
  m_state = new QLabel(this);
  auto* bRefresh = new QPushButton("Stats", this);
  auto* bDoctor = new QPushButton("Doctor", this);
  auto* bToggle = new QPushButton("ON/OFF DB", this);
  top->addWidget(m_state, 1);
  top->addWidget(bRefresh);
  top->addWidget(bDoctor);
  top->addWidget(bToggle);
  lay->addLayout(top);
  m_out = new QTextEdit(this);
  m_out->setReadOnly(true);
  m_out->setFontFamily("Consolas");
  lay->addWidget(m_out, 1);
  connect(bRefresh, &QPushButton::clicked, this, &DbPage::refresh);
  connect(bDoctor, &QPushButton::clicked, this, &DbPage::doctor);
  connect(bToggle, &QPushButton::clicked, this,
          [this]() { toggleDb(!m_backend->dbEnabled()); });
  refresh();
}

void DbPage::refresh() {
  m_state->setText(
      QString("DB %1 • %2")
          .arg(m_backend->dbEnabled() ? "ON" : "OFF")
          .arg(m_backend->activeDb()));
  runAsync(
      this,
      [b = m_backend]() {
        return b->runCore(
            {"stats", "--db", b->activeDb(), "--json"});
      },
      [this](CoreResult r) {
        m_out->setPlainText(
            r.ok ? QJsonDocument(r.json).toJson() : ("Gagal: " + r.error));
      });
}

void DbPage::doctor() {
  runAsync(
      this,
      [b = m_backend]() {
        return b->runCore(
            {"doctor", "--db", b->activeDb(), "--json"});
      },
      [this](CoreResult r) {
        m_out->setPlainText(
            r.ok ? QJsonDocument(r.json).toJson() : ("Gagal: " + r.error));
      });
}

void DbPage::toggleDb(bool on) {
  if (!askConfirm(this, "Database",
                  on ? "Aktifkan database (hasil tersimpan permanen)?"
                     : "Matikan database (mode efemeral)?"))
    return;
  QFile f(Backend::proRoot() + "/data/db.json");
  QDir().mkpath(QFileInfo(f.fileName()).absolutePath());
  if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
    f.write(QJsonDocument(QJsonObject{{"enabled", on},
                                      {"path", m_backend->defaultDb()}})
                .toJson());
  }
  m_backend->restartSidecar();
  refresh();
}

// ---------------- ActivityPage ----------------
ActivityPage::ActivityPage(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  auto* top = new QHBoxLayout();
  auto* bRefresh = new QPushButton("Muat", this);
  auto* bClear = new QPushButton("Hapus Log", this);
  top->addWidget(bRefresh);
  top->addWidget(bClear);
  top->addStretch(1);
  lay->addLayout(top);
  m_table = new QTableWidget(0, 3, this);
  m_table->setHorizontalHeaderLabels({"Waktu", "Aksi", "Detail"});
  m_table->horizontalHeader()->setStretchLastSection(true);
  lay->addWidget(m_table, 1);
  connect(bRefresh, &QPushButton::clicked, this, &ActivityPage::refresh);
  connect(bClear, &QPushButton::clicked, this, &ActivityPage::clear);
  refresh();
}

void ActivityPage::refresh() {
  m_table->setRowCount(0);
  QFile f(Backend::proRoot() + "/data/activity.log");
  if (!f.open(QIODevice::ReadOnly)) return;
  QStringList lines;
  while (!f.atEnd()) lines << f.readLine();
  int shown = 0;
  for (int i = lines.size() - 1; i >= 0 && shown < 500; --i) {
    const QJsonObject o =
        QJsonDocument::fromJson(lines[i].toUtf8()).object();
    if (o.isEmpty()) continue;
    const int row = m_table->rowCount();
    m_table->insertRow(row);
    m_table->setItem(row, 0, new QTableWidgetItem(o.value("ts").toString()));
    m_table->setItem(row, 1,
                     new QTableWidgetItem(o.value("action").toString()));
    m_table->setItem(row, 2,
                     new QTableWidgetItem(o.value("detail").toString()));
    ++shown;
  }
}

void ActivityPage::clear() {
  if (!askConfirm(this, "Hapus", "Kosongkan activity.log?")) return;
  QFile f(Backend::proRoot() + "/data/activity.log");
  if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) f.close();
  refresh();
}
