#pragma once
// MediaWidgets.h — VideoPlayer (QMediaPlayer, fallback cerdas utk kontainer
// yg tak didukung), PhotoViewer (zoom/fit), Gallery (thumbnail lazy).
#include <QAudioOutput>
#include <QLabel>
#include <QListWidget>
#include <QMediaPlayer>
#include <QScrollArea>
#include <QToolBar>
#include <QVideoWidget>
#include <QWidget>

class Backend;

// Prototype empty state untuk area video: dilukis langsung dengan QPainter
// supaya tampilannya tetap native C++ tanpa aset bitmap tambahan.
class EmptyVideoPlaceholder : public QLabel {
 public:
  explicit EmptyVideoPlaceholder(QWidget* parent = nullptr);

 protected:
  void paintEvent(QPaintEvent* event) override;
};

class VideoPlayer : public QWidget {
  Q_OBJECT
 public:
  explicit VideoPlayer(Backend* backend, QWidget* parent = nullptr);
  void load(const QString& path);  // "" = kosongkan
  QString currentPath() const { return m_path; }

 signals:
  void statusMessage(const QString& text);

 private slots:
  void onPlayPause();
  void onMediaStatus(QMediaPlayer::MediaStatus status);
  void onPlayerError();

 private:
  // WebView/QtMultimedia Windows andal utk MP4/H.264 & WebM; kontainer lain
  // langsung panel fallback (info + tombol buka eksternal).
  static bool isPlayable(const QString& path);
  Backend* m_backend;
  QMediaPlayer* m_player;
  QVideoWidget* m_video;
  QAudioOutput* m_audio;
  EmptyVideoPlaceholder* m_fallback;
  QLabel* m_info;
  QToolBar* m_bar;
  QString m_path;
};

class PhotoViewer : public QWidget {
  Q_OBJECT
 public:
  explicit PhotoViewer(QWidget* parent = nullptr);
  bool load(const QString& path);  // false bila tak terbaca
  QString currentPath() const { return m_path; }
  void zoomIn();
  void zoomOut();
  void zoomFit();
  void zoomPercent(int pct);

 signals:
  void metaMessage(const QString& text);

 private:
  void applyZoom();
  QScrollArea* m_scroll;
  QLabel* m_label;
  QImage m_image;
  double m_zoom = 1.0;
  bool m_fit = true;
  QString m_path;
};

struct GalleryItem {
  QString path;
  QString rel;
  qint64 size = 0;
};

class Gallery : public QWidget {
  Q_OBJECT
 public:
  explicit Gallery(QWidget* parent = nullptr);
  void setItems(const QList<GalleryItem>& items, bool isVideo);
  void setFilter(const QString& text);

 signals:
  void activated(const QString& path);

 private slots:
  void renderThumbs();

 private:
  QListWidget* m_list;
  QList<GalleryItem> m_items;
  bool m_isVideo = true;
};
