#pragma once
// Pages.h — semua tab fitur: Library, Foto, Duplikat, Organizer, AI+YOLO,
// Jobs, Database, Aktivitas. Operasi lama jalan di worker (QtConcurrent)
// agar UI tidak beku; operasi file ikut kontrak aman backend.
#include <QFutureWatcher>
#include <QWidget>
#include <QtConcurrent>
#include <functional>
#include <type_traits>

#include "Backend.h"
#include "MediaWidgets.h"

class QComboBox;
class QLabel;
class QLineEdit;
class QListWidget;
class QPlainTextEdit;
class QPushButton;
class QSpinBox;
class QTableWidget;
class QTextEdit;
class QTreeWidget;

// Helper: jalankan fungsi berat di thread, teruskan hasilnya ke UI thread.
template <typename Fn, typename Done>
void runAsync(QWidget* ctx, Fn fn, Done done) {
  auto* w = new QFutureWatcher<std::invoke_result_t<Fn>>();
  QObject::connect(w, &QFutureWatcher<std::invoke_result_t<Fn>>::finished,
                   ctx, [w, done]() {
                     done(w->result());
                     w->deleteLater();
                   });
  w->setFuture(QtConcurrent::run(fn));
}

class LibraryPage : public QWidget {
  Q_OBJECT
 public:
  explicit LibraryPage(Backend* backend, QWidget* parent = nullptr);
  void setRoot(const QString& root);

 private slots:
  void browse();
  void scan();
  void openSelected(const QString& path);
  void fileAction(const QString& action);

 private:
  void refreshList();
  Backend* m_backend;
  QString m_root;
  QLineEdit* m_folder;
  Gallery* m_gallery;
  VideoPlayer* m_player;
  QLabel* m_meta;
  QLabel* m_status;
  QString m_current;
};

class PhotoPage : public QWidget {
  Q_OBJECT
 public:
  explicit PhotoPage(Backend* backend, QWidget* parent = nullptr);
  void setRoot(const QString& root);

 private slots:
  void browse();
  void load();
  void onPhoto(const QString& path);
  void photoAction(const QString& action);
  void classifyYolo();

 private:
  Backend* m_backend;
  QString m_root;
  QLineEdit* m_folder;
  Gallery* m_gallery;
  PhotoViewer* m_viewer;
  QLabel* m_meta;
  QLabel* m_annot;
  QLabel* m_yolo;
  QString m_current;
  QJsonObject m_currentAnnot;
};

class DuplicatesPage : public QWidget {
  Q_OBJECT
 public:
  explicit DuplicatesPage(Backend* backend, QWidget* parent = nullptr);

 private slots:
  void find();
  void act(const QString& action);

 private:
  Backend* m_backend;
  QLineEdit* m_folder;
  QSpinBox* m_minSize;
  QTreeWidget* m_groups;
  QLabel* m_status;
};

class OrganizePage : public QWidget {
  Q_OBJECT
 public:
  explicit OrganizePage(Backend* backend, QWidget* parent = nullptr);

 private slots:
  void planOpts(bool copy, bool dated, bool junk, bool prune, bool apply);

 private:
  Backend* m_backend;
  QComboBox* m_kind;
  QLineEdit* m_folder;
  QLineEdit* m_dest;
  QLineEdit* m_content;
  QPlainTextEdit* m_out;
};

class AiPage : public QWidget {
  Q_OBJECT
 public:
  explicit AiPage(Backend* backend, QWidget* parent = nullptr);

 private slots:
  void runAi();
  void refreshYolo();
  void startTrain();
  void stopTrain();
  void loadDocs();

 private:
  Backend* m_backend;
  QComboBox* m_mode;
  QLineEdit* m_folder;
  QSpinBox* m_limit;
  QPlainTextEdit* m_out;
  QLabel* m_yoloStatus;
  QLabel* m_yoloClasses;
  QSpinBox* m_epochs;
  QSpinBox* m_batch;
  QComboBox* m_size;
  QSpinBox* m_imgsz;
  QSpinBox* m_patience;
  QPlainTextEdit* m_yoloLog;
  QTimer* m_poll = nullptr;
  QTableWidget* m_docs;
};

class JobsPage : public QWidget {
  Q_OBJECT
 public:
  explicit JobsPage(Backend* backend, QWidget* parent = nullptr);

 private slots:
  void refresh();
  void enqueue();
  void claim();
  void runOnce();
  void act(const QString& action);

 private:
  Backend* m_backend;
  QComboBox* m_kind;
  QLineEdit* m_payload;
  QTableWidget* m_table;
};

class DbPage : public QWidget {
  Q_OBJECT
 public:
  explicit DbPage(Backend* backend, QWidget* parent = nullptr);

 private slots:
  void refresh();
  void doctor();
  void toggleDb(bool on);

 private:
  Backend* m_backend;
  QTextEdit* m_out;
  QLabel* m_state;
};

class ActivityPage : public QWidget {
  Q_OBJECT
 public:
  explicit ActivityPage(Backend* backend, QWidget* parent = nullptr);

 private slots:
  void refresh();
  void clear();

 private:
  Backend* m_backend;
  QTableWidget* m_table;
};
