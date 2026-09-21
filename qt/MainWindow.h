#pragma once
// MainWindow.h — shell Qt: sidebar, tab system, menu, dialog, status.
#include <QMainWindow>

#include "Backend.h"
#include "Pages.h"

class QLabel;
class QLineEdit;
class QTabWidget;
class QTreeWidget;

class MainWindow : public QMainWindow {
  Q_OBJECT
 public:
  explicit MainWindow(QWidget* parent = nullptr);

 private slots:
  void pickRoot();
  void gotoTab(int index);
  void refreshFolderTree();
  void showAbout();

 private:
  void buildMenus();
  Backend* m_backend;
  QTabWidget* m_tabs;
  QLineEdit* m_rootEdit;
  QTreeWidget* m_tree;
  LibraryPage* m_library;
  PhotoPage* m_photos;
  QLabel* m_health;
};
