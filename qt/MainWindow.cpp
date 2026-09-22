// MainWindow.cpp
#include "MainWindow.h"

#include <QAction>
#include <QDesktopServices>
#include <QDir>
#include <QDockWidget>
#include <QFileDialog>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QIcon>
#include <QLabel>
#include <QLineEdit>
#include <QMenuBar>
#include <QMessageBox>
#include <QPushButton>
#include <QStatusBar>
#include <QTabWidget>
#include <QTreeWidget>
#include <QUrl>
#include <QVBoxLayout>

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent), m_backend(new Backend(this)) {
  setWindowTitle("AIOrganizerPro — Local File Intelligence (Qt)");
  resize(1520, 900);
  {
    const QString icon = Backend::proRoot() + "/assets/icon.ico";
    if (QFileInfo::exists(icon)) setWindowIcon(QIcon(icon));
  }
  buildMenus();

  // Sidebar kiri: root + navigasi + folder tree.
  auto* side = new QDockWidget("Navigasi", this);
  side->setFeatures(QDockWidget::NoDockWidgetFeatures);
  side->setTitleBarWidget(new QWidget(side));
  auto* sw = new QWidget(side);
  sw->setObjectName("sidePanel");
  auto* sl = new QVBoxLayout(sw);
  sl->setContentsMargins(12, 12, 12, 12);
  auto* brand = new QLabel("▶  Video Organizer", sw);
  brand->setObjectName("brand");
  sl->addWidget(brand);
  auto* rootRow = new QHBoxLayout();
  m_rootEdit = new QLineEdit(sw);
  m_rootEdit->setPlaceholderText("⌕  Cari folder atau video…");
  auto* bRoot = new QPushButton("…", sw);
  bRoot->setFixedWidth(36);
  rootRow->addWidget(m_rootEdit, 1);
  rootRow->addWidget(bRoot);
  sl->addLayout(rootRow);
  auto* navTitle = new QLabel("NAVIGASI", sw);
  navTitle->setObjectName("sectionLabel");
  sl->addWidget(navTitle);
  const QStringList nav{"⌂  Beranda", "▣  Semua Video", "▧  Semua Foto",
                        "Duplikat", "Organizer", "AI + Training", "Jobs",
                        "Database", "Aktivitas"};
  for (int i = 0; i < nav.size(); ++i) {
    auto* b = new QPushButton(nav[i], sw);
    b->setObjectName("navButton");
    connect(b, &QPushButton::clicked, this,
            [this, i]() { gotoTab(i); });
    sl->addWidget(b);
  }
  auto* folderTitle = new QLabel("FOLDER", sw);
  folderTitle->setObjectName("sectionLabel");
  sl->addWidget(folderTitle);
  m_tree = new QTreeWidget(sw);
  m_tree->setHeaderHidden(true);
  sl->addWidget(m_tree, 1);
  side->setWidget(sw);
  addDockWidget(Qt::LeftDockWidgetArea, side);

  // Tab system.
  m_tabs = new QTabWidget(this);
  m_tabs->setTabsClosable(false);
  auto* dash = new QLabel(
      "<h2>AIOrganizerPro (Qt)</h2>"
      "<p>File intelligence lokal 100%: scan C++ 1700 f/s, duplikat exact, "
      "organizer metadata, AI dokumen, klasifikasi + training YOLO.</p>"
      "<p>Tidak pernah menghapus permanen. Move selalu terverifikasi.</p>",
      this);
  dash->setWordWrap(true);
  dash->setAlignment(Qt::AlignTop);
  m_library = new LibraryPage(m_backend, this);
  m_photos = new PhotoPage(m_backend, this);
  m_tabs->addTab(dash, "Beranda");
  m_tabs->addTab(m_library, "Semua Video");
  m_tabs->addTab(m_photos, "Semua Foto");
  m_tabs->addTab(new DuplicatesPage(m_backend, this), "Duplikat");
  m_tabs->addTab(new OrganizePage(m_backend, this), "Organizer");
  m_tabs->addTab(new AiPage(m_backend, this), "AI + Training");
  m_tabs->addTab(new JobsPage(m_backend, this), "Jobs");
  m_tabs->addTab(new DbPage(m_backend, this), "Database");
  m_tabs->addTab(new ActivityPage(m_backend, this), "Aktivitas");
  m_tabs->setCurrentIndex(1);  // mulai dari halaman video seperti workspace utama
  setCentralWidget(m_tabs);

  m_health = new QLabel("●", this);
  statusBar()->addPermanentWidget(m_health);
  statusBar()->showMessage("Lokal 100% • tanpa hapus permanen");

  connect(bRoot, &QPushButton::clicked, this, &MainWindow::pickRoot);
  connect(m_rootEdit, &QLineEdit::returnPressed, this, [this]() {
    const QString r = m_rootEdit->text().trimmed();
    if (!r.isEmpty()) {
      m_library->setRoot(r);
      m_photos->setRoot(r);
      refreshFolderTree();
    }
  });
  connect(m_tree, &QTreeWidget::itemActivated, this,
          [this](QTreeWidgetItem* it) {
            const QString p = it->data(0, Qt::UserRole).toString();
            if (p.isEmpty()) return;
            m_rootEdit->setText(p);
            m_library->setRoot(p);
            m_photos->setRoot(p);
          });
  // Health core+sidecar saat start (di worker agar UI tak beku).
  m_health->setText("● memeriksa…");
  runAsync(
      this,
      [b = m_backend]() -> QJsonObject {
        const CoreResult v = b->runCore({"version"});
        const QJsonObject s = b->sidecar("ping", {}, 15000);
        return {{"ok", v.ok && s.value("ok").toBool()}};
      },
      [this](QJsonObject r) {
        m_health->setText(r.value("ok").toBool() ? "● online"
                                                 : "● bermasalah");
      });
  // Pengaturan + sapaan pemula.
  QJsonObject cfg = m_backend->appSettings();
  const QString savedRoot = cfg.value("library_root").toString();
  if (!savedRoot.isEmpty()) {
    m_rootEdit->setText(savedRoot);
    m_library->setRoot(savedRoot);
    m_photos->setRoot(savedRoot);
    refreshFolderTree();
  }
  if (cfg.value("first_run").toBool(true) &&
      !QFileInfo::exists(m_backend->appSettingsPath())) {
    QMessageBox::information(
        this, "Selamat datang",
        "AIOrganizerPro 100% offline.\n\n3 langkah pemula:\n"
        "1. Pilih folder library (kiri atas).\n"
        "2. Tab Video/Foto → Scan & Index (baca saja, aman).\n"
        "3. Semua aksi pindah default pratinjau dulu (dry-run).\n\n"
        "Perilakumu tercatat di data/behavior.jsonl agar AI memberi saran.");
    cfg["first_run"] = false;
    if (!savedRoot.isEmpty()) cfg["library_root"] = savedRoot;
    m_backend->saveAppSettings(cfg);
  }
}

void MainWindow::buildMenus() {
  auto* file = menuBar()->addMenu("File");
  QAction* aRoot = file->addAction("Pilih folder library…");
  connect(aRoot, &QAction::triggered, this, &MainWindow::pickRoot);
  QAction* aQuit = file->addAction("Keluar");
  connect(aQuit, &QAction::triggered, this, &QWidget::close);
  auto* help = menuBar()->addMenu("Bantuan");
  QAction* aAbout = help->addAction("Tentang");
  connect(aAbout, &QAction::triggered, this, &MainWindow::showAbout);
}

void MainWindow::pickRoot() {
  const QString d =
      QFileDialog::getExistingDirectory(this, "Pilih folder library");
  if (d.isEmpty()) return;
  m_rootEdit->setText(d);
  m_library->setRoot(d);
  m_photos->setRoot(d);
  refreshFolderTree();
  QJsonObject cfg = m_backend->appSettings();
  cfg["library_root"] = d;
  m_backend->saveAppSettings(cfg);
}

void MainWindow::gotoTab(int index) { m_tabs->setCurrentIndex(index); }

void MainWindow::refreshFolderTree() {
  m_tree->clear();
  const QString root = m_rootEdit->text().trimmed();
  if (root.isEmpty()) return;
  const QJsonObject r =
      m_backend->sidecar("list-folders", {{"root", root}, {"limit", 2000}});
  for (const QJsonValue& v : r.value("folders").toArray()) {
    const QJsonObject f = v.toObject();
    const int depth = f.value("depth").toInt();
    QString indent;
    for (int i = 0; i < qMin(depth, 8); ++i) indent += "  ";
    auto* it = new QTreeWidgetItem(
        m_tree, {QString("%1%2 (%3v/%4p)")
                     .arg(indent)
                     .arg(f.value("rel").toString())
                     .arg(f.value("videos").toInt())
                     .arg(f.value("images").toInt())});
    it->setData(0, Qt::UserRole, f.value("path").toString());
  }
}

void MainWindow::showAbout() {
  QMessageBox::about(
      this, "AIOrganizerPro",
      "AIOrganizerPro 0.4 (Qt6/C++)\n\nCore C++ + SQLite + FFmpeg.\nPython "
      "hanya untuk AI (YOLO).");
}
