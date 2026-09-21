// main.cpp — entry Qt AIOrganizerPro.
#include <QApplication>
#include <QStyleFactory>

#include "MainWindow.h"

int main(int argc, char* argv[]) {
  QApplication app(argc, argv);
  app.setApplicationName("AIOrganizerPro");
  app.setOrganizationName("AIOrganizerPro");
  MainWindow w;
  w.show();
  return app.exec();
}
