// main.cpp — entry Qt AIOrganizerPro.
#include <QApplication>
#include <QStyleFactory>

#include "MainWindow.h"

int main(int argc, char* argv[]) {
  QApplication app(argc, argv);
  app.setApplicationName("AIOrganizerPro");
  app.setOrganizationName("AIOrganizerPro");
  app.setStyleSheet(R"(
    * { font-family: "Segoe UI"; font-size: 13px; }
    QMainWindow { background: #0b1020; color: #e7ebf8; }
    QDockWidget { background: #11182c; color: #bfc9df; border: 0; }
    QDockWidget::title { background: #11182c; padding: 8px; color: #a89cff; }
    QWidget#sidePanel { background: #11182c; }
    QLabel#brand { color: #f1f2ff; font-size: 18px; font-weight: 700; padding: 7px 4px; }
    QLabel#sectionLabel { color: #7784a3; font-size: 10px; font-weight: 700; padding: 10px 5px 2px; }
    QLineEdit { background: #18213a; color: #e5ebfb; border: 1px solid #37425f; border-radius: 6px; padding: 8px; }
    QLineEdit:focus { border: 1px solid #9586ff; }
    QPushButton { background: #202a43; color: #dbe2f3; border: 1px solid #37425d; border-radius: 6px; padding: 8px 12px; }
    QPushButton:hover { background: #7768e7; border-color: #a99fff; color: white; }
    QPushButton#navButton { text-align: left; border: 0; background: transparent; color: #b5bfd7; padding: 8px 10px; }
    QPushButton#navButton:hover { background: #222c48; color: white; }
    QPushButton#primaryAction { background: #8171f2; color: white; border-color: #a99fff; font-weight: 600; }
    QTreeWidget, QListWidget, QTableWidget, QTextEdit, QPlainTextEdit { background: #11192d; color: #dce4f7; border: 1px solid #303b58; border-radius: 6px; }
    QTreeWidget::item, QListWidget::item { padding: 5px; }
    QTreeWidget::item:selected, QListWidget::item:selected { background: #3b307a; color: white; }
    QTabWidget::pane { border: 0; background: #0b1020; }
    QTabBar::tab { background: #151d33; color: #b9c4dc; padding: 10px 18px; border: 1px solid #303b58; border-bottom: 0; min-width: 100px; }
    QTabBar::tab:selected { background: #28234c; color: #eeeaff; border-top: 2px solid #9586ff; }
    QGroupBox { color: #e9ecf8; font-weight: 600; border: 1px solid #303b58; border-radius: 7px; margin-top: 11px; padding: 15px 10px 10px; background: #121a2e; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #dbe3f9; }
    QToolBar { background: #11192d; border: 1px solid #303b58; spacing: 4px; }
    QStatusBar { background: #11182c; color: #9faac4; border-top: 1px solid #293551; }
    QHeaderView::section { background: #202a43; color: #dbe3f6; border: 0; padding: 7px; }
  )");
  MainWindow w;
  w.show();
  return app.exec();
}
