// MainWindow.cpp
#include "MainWindow.h"

#include <QAction>
#include <QApplication>
#include <QButtonGroup>
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
#include <QMouseEvent>
#include <QPixmap>
#include <QPushButton>
#include <QStatusBar>
#include <QTabBar>
#include <QTabWidget>
#include <QToolButton>
#include <QTreeWidget>
#include <QUrl>
#include <QVBoxLayout>
#include <QWindow>
#include <utility>

namespace {
class AppTitleBar final : public QWidget {
 public:
  explicit AppTitleBar(QWidget* parent) : QWidget(parent) {
    setObjectName("titleBar");
    setFixedHeight(42);
    auto* row = new QHBoxLayout(this);
    row->setContentsMargins(14, 0, 8, 0);
    row->setSpacing(3);
    const QIcon icon(Backend::proRoot() + "/assets/video-organizer.svg");
    auto* mark = new QLabel(this);
    mark->setPixmap(icon.pixmap(25, 25));
    row->addWidget(mark);
    auto* app = new QLabel("AIOrganizerPro", this);
    app->setObjectName("topBrand");
    row->addWidget(app);
    auto* tab = new QLabel("Local Media Workspace", this);
    tab->setObjectName("fileTab");
    row->addWidget(tab);
    row->addStretch(1);
    const auto add = [this, row](const QString& text, const char* name,
                                 auto fn) {
      auto* b = new QToolButton(this);
      b->setText(text); b->setObjectName(name); b->setFixedSize(28, 24);
      connect(b, &QToolButton::clicked, this, fn); row->addWidget(b);
    };
    add("—", "windowButton", [this] { window()->showMinimized(); });
    add("□", "windowButton", [this] { window()->isMaximized() ? window()->showNormal() : window()->showMaximized(); });
    add("×", "closeButton", [this] { window()->close(); });
  }
 protected:
  void mousePressEvent(QMouseEvent* e) override {
    if (e->button() == Qt::LeftButton && window()->windowHandle())
      window()->windowHandle()->startSystemMove();
    QWidget::mousePressEvent(e);
  }
  void mouseDoubleClickEvent(QMouseEvent* e) override {
    if (e->button() == Qt::LeftButton)
      window()->isMaximized() ? window()->showNormal() : window()->showMaximized();
  }
};
}  // namespace

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent), m_backend(new Backend(this)) {
  setWindowFlags(Qt::FramelessWindowHint | Qt::Window);
  setWindowTitle("AIOrganizerPro — Local File Intelligence (Qt)");
  setMinimumSize(1120, 720);
  resize(1520, 900);
  {
    const QString icon = Backend::proRoot() + "/assets/video-organizer.svg";
    if (QFileInfo::exists(icon)) setWindowIcon(QIcon(icon));
  }
  buildMenus();
  menuBar()->hide();
  setMenuWidget(new AppTitleBar(this));

  // Sidebar kiri: root + navigasi + folder tree.
  auto* side = new QDockWidget("Navigasi", this);
  side->setFeatures(QDockWidget::NoDockWidgetFeatures);
  side->setMinimumWidth(310);
  side->setMaximumWidth(310);
  side->setTitleBarWidget(new QWidget(side));
  auto* sw = new QWidget(side);
  sw->setObjectName("sidePanel");
  auto* sl = new QVBoxLayout(sw);
  sl->setContentsMargins(12, 12, 12, 12);
  sl->setSpacing(5);
  auto* brandRow = new QWidget(sw);
  auto* brandLay = new QHBoxLayout(brandRow);
  brandLay->setContentsMargins(3, 2, 0, 4);
  brandLay->setSpacing(9);
  auto* brandMark = new QLabel(brandRow);
  brandMark->setPixmap(QIcon(Backend::proRoot() + "/assets/video-organizer.svg").pixmap(29, 29));
  brandLay->addWidget(brandMark);
  auto* brand = new QLabel("Video Organizer", brandRow);
  brand->setObjectName("brand");
  brandLay->addWidget(brand);
  brandLay->addStretch();
  sl->addWidget(brandRow);
  auto* rootRow = new QHBoxLayout();
  m_rootEdit = new QLineEdit(sw);
  m_rootEdit->setPlaceholderText("D:\\Media\\Library");
  auto* bRoot = new QPushButton("…", sw);
  bRoot->setFixedWidth(36);
  rootRow->addWidget(m_rootEdit, 1);
  rootRow->addWidget(bRoot);
  sl->addLayout(rootRow);
  auto* navTitle = new QLabel("NAVIGASI", sw);
  navTitle->setObjectName("sectionLabel");
  sl->addWidget(navTitle);
  const QStringList nav{"⌂  Beranda", "▣  Video", "▧  Foto",
                        "◈  Duplikat", "✦  Organizer", "✦  AI + Training",
                        "◴  Jobs", "◉  Aktivitas", "⚙  Pengaturan",
                        "?  Tentang"};
  auto* navGroup = new QButtonGroup(sw);
  navGroup->setExclusive(true);
  for (int i = 0; i < nav.size(); ++i) {
    auto* b = new QPushButton(nav[i], sw);
    b->setObjectName("navButton");
    b->setCheckable(true);
    b->setProperty("pageIndex", i);
    navGroup->addButton(b, i);
    sl->addWidget(b);
  }
  if (auto* first = navGroup->button(0)) first->setChecked(true);

  auto* folderTitle = new QLabel("LIBRARY ROOT", sw);
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
  m_tabs->tabBar()->hide();
  auto* dash = new QWidget(this);
  auto* dl = new QVBoxLayout(dash);
  dl->setContentsMargins(32, 28, 32, 28);
  dl->setSpacing(16);
  auto* dashTitle = new QLabel("Ruang kerja lokal", dash);
  dashTitle->setObjectName("pageTitle");
  auto* dashSub = new QLabel(
      "Atur library, preview media, rapikan file, dan jalankan AI tanpa cloud.",
      dash);
  dashSub->setObjectName("pageSubtitle");
  dl->addWidget(dashTitle);
  dl->addWidget(dashSub);

  auto* metrics = new QHBoxLayout();
  for (const auto& pair : {
           std::pair<QString, QString>{"LOCAL-FIRST", "File tetap di perangkat"},
           std::pair<QString, QString>{"BACKGROUND", "Pekerjaan berat tidak memblok UI"},
           std::pair<QString, QString>{"PREVIEW", "Seek +10s / −10s + timeline"},
           std::pair<QString, QString>{"STORAGE", "Database persistent: OFF"}}) {
    auto* box = new QGroupBox(pair.first, dash);
    auto* bl = new QVBoxLayout(box);
    auto* value = new QLabel(pair.second, box);
    value->setWordWrap(true);
    value->setObjectName("metricValue");
    bl->addWidget(value);
    metrics->addWidget(box, 1);
  }
  dl->addLayout(metrics);

  auto* quick = new QGroupBox("Quick start", dash);
  auto* ql = new QHBoxLayout(quick);
  for (const auto& pair : {
           std::pair<QString, int>{"Buka video", 1},
           std::pair<QString, int>{"Buka foto", 2},
           std::pair<QString, int>{"Rapikan library", 4},
           std::pair<QString, int>{"Pengaturan", 8}}) {
    auto* b = new QPushButton(pair.first, quick);
    if (pair.second == 1) b->setObjectName("primaryAction");
    connect(b, &QPushButton::clicked, this, [this, idx = pair.second]() {
      gotoTab(idx);
    });
    ql->addWidget(b);
  }
  dl->addWidget(quick);

  auto* guide = new QGroupBox("Alur kerja yang disarankan", dash);
  auto* gl = new QVBoxLayout(guide);
  for (const QString& s : {
           "1. Pilih Library Root di sidebar.",
           "2. Scan & Index untuk memperbarui inventory.",
           "3. Pilih video: preview langsung, metadata dimuat background.",
           "4. Gunakan Organizer dalam mode dry-run sebelum apply."
       })
    gl->addWidget(new QLabel(s, guide));
  dl->addWidget(guide);
  dl->addStretch(1);

  m_library = new LibraryPage(m_backend, this);
  m_photos = new PhotoPage(m_backend, this);
  auto* duplicates = new DuplicatesPage(m_backend, this);
  auto* organizer = new OrganizePage(m_backend, this);
  auto* ai = new AiPage(m_backend, this);
  auto* jobs = new JobsPage(m_backend, this);
  auto* activity = new ActivityPage(m_backend, this);
  auto* settings = new SettingsPage(m_backend, this);
  auto* about = new AboutPage(m_backend, this);
  m_tabs->addTab(dash, "Beranda");
  m_tabs->addTab(m_library, "Video");
  m_tabs->addTab(m_photos, "Foto");
  m_tabs->addTab(duplicates, "Duplikat");
  m_tabs->addTab(organizer, "Organizer");
  m_tabs->addTab(ai, "AI + Training");
  m_tabs->addTab(jobs, "Jobs");
  m_tabs->addTab(activity, "Aktivitas");
  m_tabs->addTab(settings, "Pengaturan");
  m_tabs->addTab(about, "Tentang");
  m_tabs->setCurrentIndex(0);
  setCentralWidget(m_tabs);
  connect(navGroup, QOverload<int>::of(&QButtonGroup::idClicked),
          this, &MainWindow::gotoTab);
  connect(m_tabs, &QTabWidget::currentChanged, this, [navGroup](int index) {
    if (auto* b = navGroup->button(index)) b->setChecked(true);
  });

  m_health = new QLabel("● memeriksa…", this);
  m_health->setObjectName("healthPill");
  statusBar()->addPermanentWidget(m_health);
  statusBar()->showMessage("Local-first · persistent database OFF · file tidak dihapus permanen");

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
  qApp->setProperty("aiorg_confirm_actions",
                    cfg.value("confirm_file_actions").toBool(true));
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
  m_tree->setEnabled(false);
  runAsync(
      this,
      [b = m_backend, root]() {
        return b->sidecar("list-folders", {{"root", root}, {"limit", 2000}});
      },
      [this, root](QJsonObject r) {
        if (root != m_rootEdit->text().trimmed()) {
          m_tree->setEnabled(true);
          return;
        }
        m_tree->clear();
        for (const QJsonValue& v : r.value("folders").toArray()) {
          const QJsonObject f = v.toObject();
          const int depth = f.value("depth").toInt();
          QString indent;
          for (int i = 0; i < qMin(depth, 8); ++i) indent += "  ";
          auto* it = new QTreeWidgetItem(
              m_tree, {QString("%1%2  ·  %3v  %4p")
                           .arg(indent)
                           .arg(f.value("rel").toString())
                           .arg(f.value("videos").toInt())
                           .arg(f.value("images").toInt())});
          it->setData(0, Qt::UserRole, f.value("path").toString());
        }
        m_tree->setEnabled(true);
      });
}

void MainWindow::showAbout() {
  gotoTab(9);
}
