// MediaWidgets.cpp
#include "MediaWidgets.h"

#include <QAction>
#include <QDesktopServices>
#include <QFileInfo>
#include <QImageReader>
#include <QLabel>
#include <QListWidgetItem>
#include <QMessageBox>
#include <QPixmap>
#include <QTimer>
#include <QUrl>
#include <QVBoxLayout>

// ---------------- VideoPlayer ----------------
VideoPlayer::VideoPlayer(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(0, 0, 0, 0);
  m_video = new QVideoWidget(this);
  m_fallback = new QLabel(this);
  m_fallback->setAlignment(Qt::AlignCenter);
  m_fallback->setWordWrap(true);
  m_fallback->hide();
  m_info = new QLabel(this);
  m_info->setWordWrap(true);
  m_player = new QMediaPlayer(this);
  m_audio = new QAudioOutput(this);
  m_player->setAudioOutput(m_audio);
  m_player->setVideoOutput(m_video);
  m_bar = new QToolBar(this);
  QAction* play = m_bar->addAction("Main/Jeda");
  QAction* mute = m_bar->addAction("Suara");
  QAction* open = m_bar->addAction("Buka di Player");
  connect(play, &QAction::triggered, this, &VideoPlayer::onPlayPause);
  connect(mute, &QAction::triggered, this, [this, mute]() {
    m_audio->setMuted(!m_audio->isMuted());
    mute->setText(m_audio->isMuted() ? "Bisukan" : "Suara");
  });
  connect(open, &QAction::triggered, this, [this]() {
    if (!m_path.isEmpty())
      QDesktopServices::openUrl(QUrl::fromLocalFile(m_path));
  });
  connect(m_player, &QMediaPlayer::mediaStatusChanged, this,
          &VideoPlayer::onMediaStatus);
  connect(m_player, &QMediaPlayer::errorOccurred, this,
          &VideoPlayer::onPlayerError);
  lay->addWidget(m_video, 1);
  lay->addWidget(m_fallback, 1);
  lay->addWidget(m_info);
  lay->addWidget(m_bar);
}

bool VideoPlayer::isPlayable(const QString& path) {
  static const QSet<QString> ok{"mp4", "m4v", "webm", "ogv", "mov"};
  return ok.contains(QFileInfo(path).suffix().toLower());
}

void VideoPlayer::load(const QString& path) {
  m_path = path;
  m_player->stop();
  if (path.isEmpty()) {
    m_video->hide();
    m_fallback->setText("Belum ada video dipilih.");
    m_fallback->show();
    m_info->clear();
    return;
  }
  const QFileInfo fi(path);
  m_info->setText(QString("%1  •  %2 bytes  •  diubah %3")
                      .arg(fi.fileName())
                      .arg(fi.size())
                      .arg(fi.lastModified().toString("yyyy-MM-dd HH:mm")));
  if (!isPlayable(path)) {
    m_video->hide();
    m_fallback->setText(
        QString("Format .%1 tidak diputar di pemutar internal.\nMetadata tetap "
                "dibaca engine; gunakan tombol \"Buka di Player\".")
            .arg(fi.suffix().toUpper()));
    m_fallback->show();
    emit statusMessage("Kontainer tak didukung pemutar internal.");
    return;
  }
  m_fallback->hide();
  m_video->show();
  m_player->setSource(QUrl::fromLocalFile(path));
  m_player->play();
}

void VideoPlayer::onPlayPause() {
  if (m_player->playbackState() == QMediaPlayer::PlayingState)
    m_player->pause();
  else
    m_player->play();
}

void VideoPlayer::onMediaStatus(QMediaPlayer::MediaStatus s) {
  if (s == QMediaPlayer::LoadedMedia)
    emit statusMessage("Siap diputar.");
  else if (s == QMediaPlayer::InvalidMedia)
    onPlayerError();
}

void VideoPlayer::onPlayerError() {
  m_video->hide();
  m_fallback->setText("Video tak bisa diputar di pemutar internal.\nGunakan "
                      "tombol \"Buka di Player\".");
  m_fallback->show();
  emit statusMessage("Player internal gagal: " + m_player->errorString());
}

// ---------------- PhotoViewer ----------------
PhotoViewer::PhotoViewer(QWidget* parent) : QWidget(parent) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(0, 0, 0, 0);
  m_scroll = new QScrollArea(this);
  m_scroll->setWidgetResizable(true);
  m_scroll->setAlignment(Qt::AlignCenter);
  m_label = new QLabel(m_scroll);
  m_label->setAlignment(Qt::AlignCenter);
  m_scroll->setWidget(m_label);
  lay->addWidget(m_scroll, 1);
}

bool PhotoViewer::load(const QString& path) {
  QImageReader rd(path);
  rd.setAutoTransform(true);
  QImage img = rd.read();
  if (img.isNull()) return false;
  m_image = img;
  m_path = path;
  m_fit = true;
  applyZoom();
  emit metaMessage(QString("%1 × %2")
                       .arg(img.width())
                       .arg(img.height()));
  return true;
}

void PhotoViewer::applyZoom() {
  if (m_image.isNull()) return;
  QPixmap pm;
  if (m_fit) {
    pm = QPixmap::fromImage(m_image).scaled(
        m_scroll->viewport()->size(), Qt::KeepAspectRatio,
        Qt::SmoothTransformation);
  } else {
    pm = QPixmap::fromImage(m_image).scaled(
        m_image.size() * m_zoom, Qt::KeepAspectRatio,
        Qt::SmoothTransformation);
  }
  m_label->setPixmap(pm);
  m_label->resize(pm.size());
}

void PhotoViewer::zoomIn() {
  m_fit = false;
  m_zoom = qMin(4.0, m_zoom * 1.25);
  applyZoom();
}
void PhotoViewer::zoomOut() {
  m_fit = false;
  m_zoom = qMax(0.1, m_zoom / 1.25);
  applyZoom();
}
void PhotoViewer::zoomFit() {
  m_fit = true;
  applyZoom();
}
void PhotoViewer::zoomPercent(int pct) {
  m_fit = false;
  m_zoom = qBound(0.1, pct / 100.0, 4.0);
  applyZoom();
}

// ---------------- Gallery ----------------
Gallery::Gallery(QWidget* parent) : QWidget(parent) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(0, 0, 0, 0);
  m_list = new QListWidget(this);
  m_list->setViewMode(QListView::IconMode);
  m_list->setIconSize(QSize(160, 120));
  m_list->setResizeMode(QListView::Adjust);
  m_list->setMovement(QListView::Static);
  connect(m_list, &QListWidget::itemActivated,
          [this](QListWidgetItem* it) { emit activated(it->data(Qt::UserRole).toString()); });
  connect(m_list, &QListWidget::itemClicked,
          [this](QListWidgetItem* it) { emit activated(it->data(Qt::UserRole).toString()); });
  lay->addWidget(m_list);
  // Render thumbnail bertahap agar UI tetap responsif.
  auto* timer = new QTimer(this);
  timer->setInterval(400);
  connect(timer, &QTimer::timeout, this, &Gallery::renderThumbs);
  timer->start();
}

void Gallery::setItems(const QList<GalleryItem>& items, bool isVideo) {
  m_items = items;
  m_isVideo = isVideo;
  m_list->clear();
  for (const GalleryItem& g : items) {
    auto* it = new QListWidgetItem(
        QIcon(), QString("%1\n%2 bytes").arg(QFileInfo(g.path).fileName()).arg(g.size), m_list);
    it->setData(Qt::UserRole, g.path);
    it->setToolTip(g.path);
  }
}

void Gallery::setFilter(const QString& text) {
  const QString q = text.trimmed().toLower();
  for (int i = 0; i < m_list->count(); ++i) {
    QListWidgetItem* it = m_list->item(i);
    it->setHidden(!q.isEmpty() &&
                  !m_items[i].path.toLower().contains(q));
  }
}

void Gallery::renderThumbs() {
  // Isi maksimal 12 ikon kosong per tick dari thumbnail disk (foto) atau
  // placeholder (video; frame diambil via panel player).
  int done = 0;
  for (int i = 0; i < m_list->count() && done < 12; ++i) {
    QListWidgetItem* it = m_list->item(i);
    if (!it->icon().isNull() || it->isHidden()) continue;
    QPixmap pm;
    if (!m_isVideo) {
      QImageReader rd(m_items[i].path);
      rd.setAutoTransform(true);
      QImage img = rd.read();
      if (!img.isNull())
        pm = QPixmap::fromImage(img.scaled(
            QSize(320, 240), Qt::KeepAspectRatio, Qt::FastTransformation));
    }
    if (pm.isNull()) {
      pm = QPixmap(160, 120);
      pm.fill(m_isVideo ? QColor("#1c2a4a") : QColor("#2a2a2a"));
    }
    it->setIcon(QIcon(pm));
    ++done;
  }
}
