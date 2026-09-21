// MainWindow.cpp
#include "MainWindow.h"

#include <QAction>
#include <QDesktopServices>
#include <QDir>
#include <QDockWidget>
#include <QFileDialog>
#include <QFileInfo>
#include <QHBoxLayout>
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
  buildMenus();

  // Sidebar kiri: root + navigasi + folder tree.
  auto* side = new QDockWidget("Navigasi", this);
  side->setFeatures(QDockWidget::NoDockWidgetFeatures);
  auto* sw = new QWidget(side);
  auto* sl = new QVBoxLayout(sw);
  auto* rootRow = new QHBoxLayout();
  m_rootEdit = new QLineEdit(sw);
  m_rootEdit->setPlaceholderText("Folder library…");
  auto* bRoot = new QPushButton("…", sw);
  bRoot->setFixedWidth(36);
  rootRow->addWidget(m_rootEdit, 1);
  rootRow->addWidget(bRoot);
  sl->addLayout(rootRow);
  const QStringList nav{"Beranda:Video", "Semua Video", "Semua Foto",
                        "Duplikat", "Organizer", "AI + Training", "Jobs",
                        "Database", "Aktivitas"};
  for (int i = 0; i < nav.size(); ++i) {
    auto* b = new QPushButton(nav[i], sw);
    b->setFlat(true);
    b->setStyleSheet("text-align:left; padding:6px;");
    connect(b, &QPushButton::clicked, this,
            [this, i]() { gotoTab(i); });
    sl->addWidget(b);
  }
  sl->addWidget(new QLabel("Folder aktif:", sw));
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
