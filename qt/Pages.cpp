// Pages.cpp — implementasi tab fitur (Qt Widgets, operasi berat di worker).
#include "Pages.h"

#include <QCheckBox>
#include <QComboBox>
#include <QDesktopServices>
#include <QDir>
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
#include <QTableWidget>
#include <QTextEdit>
#include <QTimer>
#include <QTreeWidget>
#include <QUrl>
#include <QVBoxLayout>

namespace {
const QStringList kVideoExts{"mp4", "mov", "mts", "m2ts", "mkv", "avi",
                             "wmv", "webm", "m4v", "ogv"};
const QStringList kPhotoExts{"jpg", "jpeg", "png",  "webp", "bmp", "gif",
                             "tif", "tiff", "heic", "heif"};

QList<GalleryItem> listMedia(Backend* b, const QString& root, bool video) {
  QList<GalleryItem> out;
  const QJsonObject r = b->sidecar(
      "list-videos",
      {{"root", root},
       {"limit", 5000},
       {"kind", video ? "videos" : "images"}},
      120000);
  for (const QJsonValue& v : r.value("videos").toArray()) {
    const QJsonObject o = v.toObject();
    out.append({o.value("path").toString(), o.value("rel").toString(),
                qint64(o.value("size").toDouble())});
  }
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
  return QMessageBox::question(ctx, title, text,
                               QMessageBox::Ok | QMessageBox::Cancel) ==
         QMessageBox::Ok;
}

void toast(QWidget* ctx, const QString& text) {
  QMessageBox::information(ctx, "AIOrganizerPro", text);
}
}  // namespace

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
  auto* bScan = new QPushButton("Scan & Index", this);
  bScan->setObjectName("primaryAction");
  top->addWidget(m_folder, 1);
  top->addWidget(bBrowse);
  top->addWidget(bScan);
  lay->addLayout(top);
  auto* split = new QSplitter(Qt::Horizontal, this);
  auto* left = new QWidget(this);
  auto* ll = new QVBoxLayout(left);
  ll->setContentsMargins(0, 0, 0, 0);
  auto* galleryTitle = new QLabel("▣  Video di folder ini", left);
  galleryTitle->setStyleSheet("font-weight:600; color:#dce4f7; padding:4px;");
  ll->addWidget(galleryTitle);
  m_gallery = new Gallery(this);
  ll->addWidget(m_gallery, 1);
  auto* filter = new QLineEdit(this);
  filter->setPlaceholderText("Cari nama/path…");
  ll->addWidget(filter);
  auto* center = new QWidget(this);
  auto* rl = new QVBoxLayout(center);
  rl->setContentsMargins(0, 0, 0, 0);
  m_player = new VideoPlayer(backend, this);
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
  auto* analysis = new QLabel("Pilih video untuk membaca durasi, resolusi, codec, audio, serta status metadata dengan FFprobe.", analysisBox);
  analysis->setWordWrap(true);
  analysis->setStyleSheet("color:#aeb9d2; padding:4px;");
  analysisLay->addWidget(analysis);
  auto* tags = new QLabel("◇  Tag & Kategori dan ▤ Catatan dapat diedit lewat tombol di panel kanan.", analysisBox);
  tags->setWordWrap(true);
  tags->setStyleSheet("color:#a99cff; padding:4px;");
  analysisLay->addWidget(tags);

  auto* actions = new QWidget(this);
  actions->setMinimumWidth(238);
  actions->setMaximumWidth(285);
  auto* acts = new QVBoxLayout(actions);
  acts->setContentsMargins(0, 0, 0, 0);
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
  acts->addStretch(1);
  rl->addWidget(m_player, 4);
  rl->addWidget(detailBox);
  rl->addWidget(analysisBox);
  split->addWidget(left);
  split->addWidget(center);
  split->addWidget(actions);
  split->setStretchFactor(0, 1);
  split->setStretchFactor(1, 3);
  split->setStretchFactor(2, 0);
  split->setSizes({280, 760, 250});
  lay->addWidget(split, 1);
  connect(bBrowse, &QPushButton::clicked, this, &LibraryPage::browse);
  connect(bScan, &QPushButton::clicked, this, &LibraryPage::scan);
  connect(m_gallery, &Gallery::activated, this, &LibraryPage::openSelected);
  connect(filter, &QLineEdit::textChanged, m_gallery, &Gallery::setFilter);
  connect(m_player, &VideoPlayer::statusMessage, m_status,
          &QLabel::setText);
}

void LibraryPage::setRoot(const QString& root) {
  m_root = root;
  if (!m_folder->text().isEmpty()) m_folder->setText(root);
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
  runAsync(
      this, [b = m_backend, folder]() { return b->runCore({"scan", folder, "--db", b->activeDb(), "--json", "--actor", "gui"}); },
      [this](CoreResult r) {
        m_status->setText(r.ok ? "Scan selesai." : ("Scan gagal: " + r.error));
        refreshList();
      });
}

void LibraryPage::refreshList() {
  if (m_root.isEmpty()) return;
  runAsync(
      this, [b = m_backend, root = m_root]() { return listMedia(b, root, true); },
      [this](QList<GalleryItem> items) {
        m_gallery->setItems(items, true);
        m_status->setText(QString("%1 video.").arg(items.size()));
      });
}

void LibraryPage::openSelected(const QString& path) {
  if (path.isEmpty()) return;
  m_current = path;
  m_player->load(path);
  const QJsonObject r =
      m_backend->sidecar("video-inspect", {{"path", path}}, 120000);
  if (r.value("ok").toBool()) {
    const QJsonObject pr = r.value("probe").toObject();
    const QJsonObject v = pr.value("video").toObject();
    m_meta->setText(QString("%1  •  %2  •  %3x%4 %5")
                        .arg(QFileInfo(path).fileName())
                        .arg(pr.value("duration").toDouble() > 0
                                 ? QString::number(pr.value("duration").toDouble(), 'f', 1) + " dtk"
                                 : "-")
                        .arg(v.value("width").toInt())
                        .arg(v.value("height").toInt())
                        .arg(v.value("codec").toString()));
  } else {
    m_meta->setText(QFileInfo(path).fileName());
  }
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
  m_root = root;
  if (!m_folder->text().isEmpty()) m_folder->setText(root);
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
      [this](QList<GalleryItem> items) { m_gallery->setItems(items, false); });
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
  auto* bProp = new QPushButton("Buat Proposal", this);
  m_status = new QLabel(this);
  acts->addWidget(bMove);
  acts->addWidget(bProp);
  acts->addWidget(m_status, 1);
  lay->addLayout(acts);
  connect(bFind, &QPushButton::clicked, this, &DuplicatesPage::find);
  connect(bMove, &QPushButton::clicked, this,
          [this]() { act("move"); });
  connect(bProp, &QPushButton::clicked, this,
          [this]() { act("propose"); });
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
                           QString::number(mn), "--workers", "4"},
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
  const int gid = top->data(0, Qt::UserRole).toInt();
  if (action == "move") {
    if (!askConfirm(this, "Pindah",
                    QString("Pertahankan %1, pindahkan sisanya ke %2?")
                        .arg(keep, to)))
      return;
    runAsync(
        this,
        [b = m_backend, gid, keep, to]() {
          return b->runCore(
              {"move-approved", "--db", b->activeDb(), "--group",
               QString::number(gid), "--keep", keep, "--to", to, "--json",
               "--actor", "gui"});
        },
        [this](CoreResult r) {
          toast(this, r.ok ? "Dipindah." : ("Gagal: " + r.error));
          find();
        });
  } else {
    runAsync(
        this,
        [b = m_backend, gid, keep, to]() {
          return b->runCore({"proposals", "propose", "--group",
                             QString::number(gid), "--keep", keep, "--to", to,
                             "--db", b->activeDb(), "--json", "--actor",
                             "gui"});
        },
        [this](CoreResult r) {
          toast(this, r.ok ? "Proposal dibuat (belum pindah)."
                           : ("Gagal: " + r.error));
        });
  }
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
