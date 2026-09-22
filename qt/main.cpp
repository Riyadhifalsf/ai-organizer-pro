// main.cpp — entry Qt AIOrganizerPro.
#include <QApplication>
#include <QColor>
#include <QPalette>
#include <QStyleFactory>

#include "MainWindow.h"

int main(int argc, char* argv[]) {
  QApplication app(argc, argv);
  app.setApplicationName("AIOrganizerPro");
  app.setOrganizationName("AIOrganizerPro");
  // Fusion menghindari kontrol putih/hitam bawaan Windows yang dapat menembus
  // stylesheet saat aplikasi dirender dengan tema OS berbeda.
  app.setStyle(QStyleFactory::create("Fusion"));
  QPalette palette;
  palette.setColor(QPalette::Window, QColor("#0b1020"));
  palette.setColor(QPalette::WindowText, QColor("#e7ebf8"));
  palette.setColor(QPalette::Base, QColor("#11192d"));
  palette.setColor(QPalette::AlternateBase, QColor("#151f36"));
  palette.setColor(QPalette::Text, QColor("#dce4f7"));
  palette.setColor(QPalette::Button, QColor("#202a43"));
  palette.setColor(QPalette::ButtonText, QColor("#dbe2f3"));
  palette.setColor(QPalette::Highlight, QColor("#7567d6"));
  palette.setColor(QPalette::HighlightedText, Qt::white);
  app.setPalette(palette);
  app.setStyleSheet(R"(
    * { font-family: "Segoe UI"; font-size: 13px; }
    QMainWindow { background: #0b0f1a; color: #edf1fb; }
    QWidget#titleBar { background: #101727; border-bottom: 1px solid #222c43; }
    QLabel#topBrand { color: #f5f7ff; font-size: 15px; font-weight: 700; padding-right: 22px; }
    QLabel#fileTab { color: #cfc8ff; background: #1b1a31; border-left: 1px solid #2b3150; border-right: 1px solid #2b3150; padding: 11px 20px; }
    QToolButton#windowButton, QToolButton#closeButton { background: transparent; border: 0; border-radius: 7px; color: #aeb8cf; font-size: 13px; padding: 0; }
    QToolButton#windowButton:hover { background: #202943; color: white; }
    QToolButton#closeButton:hover { background: #aa3f56; color: white; }
    QDockWidget { background: #101727; color: #b9c5de; border: 0; }
    QDockWidget::title { background: #101727; padding: 8px; color: #8f88d9; }
    QWidget#sidePanel { background: #101727; }
    QLabel#brand { color: #f7f8ff; font-size: 18px; font-weight: 700; padding: 7px 4px; }
    QLabel#sectionLabel { color: #68758f; font-size: 10px; font-weight: 700; letter-spacing: 1px; padding: 10px 5px 3px; }
    QLabel#pageTitle { color: #f4f6fd; font-size: 28px; font-weight: 700; padding: 0; }
    QLabel#pageSubtitle { color: #8995ae; font-size: 14px; padding-bottom: 4px; }
    QLabel#metricValue { color: #d8dff0; font-size: 13px; line-height: 1.3; }
    QLabel#mediaInfo { background: #121a2a; color: #e0e6f3; border: 1px solid #26324b; border-radius: 10px; padding: 10px 12px; }
    QLabel#mediaTime { color: #c2cae0; padding: 0 7px; }
    QLabel#healthPill { color: #8ee0ad; background: #13251e; border: 1px solid #24553e; border-radius: 9px; padding: 3px 9px; }
    QLineEdit { background: #141c2d; color: #e7ecf8; border: 1px solid #27334c; border-radius: 10px; padding: 9px 12px; min-height: 20px; selection-background-color: #4e478f; }
    QLineEdit:focus { border: 1px solid #8174e9; background: #161f33; }
    QPushButton { background: #182137; color: #dce4f4; border: 1px solid #293652; border-radius: 9px; padding: 8px 13px; min-height: 20px; }
    QPushButton:hover { background: #252e49; border-color: #6259a7; color: white; }
    QPushButton:pressed { background: #2d2a50; }
    QPushButton:checked { background: #2a2848; color: white; border-color: #655db3; }
    QPushButton#navButton { text-align: left; border: 0; background: transparent; color: #9eabc4; padding: 9px 12px; min-height: 20px; border-radius: 9px; }
    QPushButton#navButton:hover { background: #171f32; color: #edf1fa; }
    QPushButton#navButton:checked { background: #252242; color: #f6f4ff; }
    QPushButton#primaryAction { background: #7467db; color: white; border-color: #9388ef; font-weight: 600; }
    QPushButton#primaryAction:hover { background: #8274ed; }
    QToolButton { background: #171f32; color: #dbe2f0; border: 1px solid #2a3550; border-radius: 8px; padding: 6px 9px; }
    QToolButton:hover { background: #262d49; border-color: #675db6; color: white; }
    QCheckBox { color: #dce3f2; spacing: 9px; }
    QCheckBox::indicator { width: 17px; height: 17px; }
    QComboBox, QSpinBox { background: #141c2d; color: #e7ecf8; border: 1px solid #27334c; border-radius: 9px; padding: 7px 9px; min-height: 20px; }
    QTreeWidget, QListWidget, QTableWidget, QTextEdit, QPlainTextEdit { background: #101727; color: #dce4f5; border: 1px solid #26324b; border-radius: 10px; }
    QTreeWidget::item, QListWidget::item { padding: 7px; border-radius: 7px; }
    QTreeWidget::item:hover, QListWidget::item:hover { background: #171f32; }
    QTreeWidget::item:selected, QListWidget::item:selected { background: #312b61; color: white; }
    QTabWidget::pane { border: 0; background: #0b0f1a; }
    QGroupBox { color: #e9ecf8; font-weight: 600; border: 1px solid #26324b; border-radius: 12px; margin-top: 12px; padding: 16px 12px 12px; background: #11192a; }
    QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #d8def0; }
    QToolBar { background: #101727; border: 1px solid #26324b; border-radius: 9px; spacing: 5px; padding: 3px; }
    QStatusBar { background: #101727; color: #8e9ab3; border-top: 1px solid #222c43; }
    QHeaderView::section { background: #182137; color: #d8e0f0; border: 0; padding: 8px; }
    QSlider::groove:horizontal { height: 5px; background: #263149; border-radius: 2px; }
    QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; background: #8b7ff0; border-radius: 7px; }
    QSlider::sub-page:horizontal { background: #7669dc; border-radius: 2px; }
    QSplitter::handle { background: #0b0f1a; width: 10px; }
    QSplitter::handle:hover { background: #171f32; }
    QScrollBar:vertical { background: #0f1626; width: 10px; margin: 2px; }
    QScrollBar::handle:vertical { background: #2c3955; min-height: 24px; border-radius: 5px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar:horizontal { background: #0f1626; height: 10px; margin: 2px; }
    QScrollBar::handle:horizontal { background: #2c3955; min-width: 24px; border-radius: 5px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
  )");
  MainWindow w;
  w.show();
  return app.exec();
}
