// MediaWidgets.cpp
#include "MediaWidgets.h"

#include <QAction>
#include <QDesktopServices>
#include <QFileInfo>
#include <QImageReader>
#include <QLabel>
#include <QListWidgetItem>
#include <QMessageBox>
#include <QPainter>
#include <QPainterPath>
#include <QPixmap>
#include <QSlider>
#include <QStyle>
#include <QTimer>
#include <QUrl>
#include <QVBoxLayout>
#include <limits>

// ---------------- EmptyVideoPlaceholder ----------------
EmptyVideoPlaceholder::EmptyVideoPlaceholder(QWidget* parent) : QLabel(parent) {
  setMinimumHeight(270);
  setAlignment(Qt::AlignHCenter | Qt::AlignBottom);
  setWordWrap(true);
  setContentsMargins(24, 20, 24, 30);
}

void EmptyVideoPlaceholder::paintEvent(QPaintEvent* event) {
  Q_UNUSED(event);
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing);
  const QRectF r = rect().adjusted(1, 1, -1, -1);

  // Palet placeholder: midnight-indigo → biru danau, selaras dengan border.
  QLinearGradient sky(r.topLeft(), r.bottomLeft());
  sky.setColorAt(0.0, QColor("#273760"));
  sky.setColorAt(0.52, QColor("#415a8d"));
  sky.setColorAt(0.53, QColor("#27436d"));
  sky.setColorAt(1.0, QColor("#152544"));
  p.setPen(QPen(QColor("#2c3a5d"), 1));
  p.setBrush(sky);
  p.drawRoundedRect(r, 8, 8);

  // Awan lembut dan refleksi air.
  p.setPen(Qt::NoPen);
  p.setBrush(QColor(218, 230, 255, 34));
  p.drawEllipse(QRectF(r.left() + r.width() * .58, r.top() + r.height() * .16,
                       r.width() * .22, r.height() * .07));
  p.drawEllipse(QRectF(r.left() + r.width() * .64, r.top() + r.height() * .13,
                       r.width() * .13, r.height() * .09));
  p.setPen(QPen(QColor(182, 204, 239, 40), 1));
  for (int y = int(r.top() + r.height() * .63); y < r.bottom() - 20; y += 13)
    p.drawLine(QPointF(r.left() + 18, y), QPointF(r.right() - 18, y));

  // Dua siluet bukit supaya area kosong tetap terasa sebagai video preview.
  QPainterPath distant;
  distant.moveTo(r.left(), r.top() + r.height() * .67);
  distant.lineTo(r.left() + r.width() * .30, r.top() + r.height() * .42);
  distant.lineTo(r.left() + r.width() * .50, r.top() + r.height() * .62);
  distant.lineTo(r.left() + r.width() * .68, r.top() + r.height() * .35);
  distant.lineTo(r.right(), r.top() + r.height() * .64);
  distant.lineTo(r.right(), r.bottom());
  distant.lineTo(r.left(), r.bottom());
  distant.closeSubpath();
  p.setPen(Qt::NoPen);
  p.setBrush(QColor("#1d3550"));
  p.drawPath(distant);
  QPainterPath front;
  front.moveTo(r.left(), r.top() + r.height() * .76);
  front.lineTo(r.left() + r.width() * .22, r.top() + r.height() * .58);
  front.lineTo(r.left() + r.width() * .42, r.top() + r.height() * .75);
  front.lineTo(r.left() + r.width() * .62, r.top() + r.height() * .52);
  front.lineTo(r.right(), r.top() + r.height() * .73);
  front.lineTo(r.right(), r.bottom());
  front.lineTo(r.left(), r.bottom());
  front.closeSubpath();
  p.setBrush(QColor("#142743"));
  p.drawPath(front);

  // Tombol play beraksen lavender.
  const QPointF c(r.center().x(), r.top() + r.height() * .48);
  p.setBrush(QColor(138, 120, 245, 225));
  p.drawEllipse(c, 29, 29);
  QPainterPath triangle;
  triangle.moveTo(c.x() - 7, c.y() - 11);
  triangle.lineTo(c.x() - 7, c.y() + 11);
  triangle.lineTo(c.x() + 12, c.y());
  triangle.closeSubpath();
  p.setBrush(QColor("#f4f2ff"));
  p.drawPath(triangle);

  p.setPen(QColor("#eaf0ff"));
  QFont f = font();
  f.setWeight(QFont::DemiBold);
  f.setPointSize(12);
  p.setFont(f);
  p.drawText(r.adjusted(16, r.height() * .66, -16, -16),
             Qt::AlignHCenter | Qt::AlignBottom | Qt::TextWordWrap, text());
}

// ---------------- VideoPlayer ----------------
namespace {
QString mediaClock(qint64 ms) {
  if (ms < 0) ms = 0;
  const qint64 total = ms / 1000;
  const qint64 hours = total / 3600;
  const qint64 minutes = (total % 3600) / 60;
  const qint64 seconds = total % 60;
  if (hours > 0)
    return QString("%1:%2:%3").arg(hours).arg(minutes, 2, 10, QChar('0')).arg(seconds, 2, 10, QChar('0'));
  return QString("%1:%2").arg(minutes).arg(seconds, 2, 10, QChar('0'));
}
}

VideoPlayer::VideoPlayer(Backend* backend, QWidget* parent)
    : QWidget(parent), m_backend(backend) {
  auto* lay = new QVBoxLayout(this);
  lay->setContentsMargins(0, 0, 0, 0);
  lay->setSpacing(8);

  m_video = new QVideoWidget(this);
  m_video->setMinimumHeight(320);
  m_video->setStyleSheet("background:#080b14; border:1px solid #2b3550; border-radius:14px;");
  m_video->setAspectRatioMode(Qt::KeepAspectRatio);
  m_fallback = new EmptyVideoPlaceholder(this);
  m_fallback->setText("Pilih video untuk membuka preview.");
  m_video->hide();

  m_info = new QLabel(this);
  m_info->setWordWrap(true);
  m_info->setObjectName("mediaInfo");

  m_player = new QMediaPlayer(this);
  m_audio = new QAudioOutput(this);
  m_audio->setVolume(0.82f);
  m_player->setAudioOutput(m_audio);
  m_player->setVideoOutput(m_video);

  m_seek = new QSlider(Qt::Horizontal, this);
  m_seek->setRange(0, 0);
  m_seek->setSingleStep(1000);
  m_seek->setPageStep(5000);
  m_seek->setToolTip("Geser untuk mencari posisi video");
  m_seek->setEnabled(false);
  connect(m_seek, &QSlider::sliderPressed, this, [this]() { m_userSeeking = true; });
  connect(m_seek, &QSlider::sliderReleased, this, [this]() { m_userSeeking = false; m_player->setPosition(m_seek->value()); });
  connect(m_seek, &QSlider::sliderMoved, this, &VideoPlayer::onSeekSlider);

  m_bar = new QToolBar(this);
  m_bar->setIconSize(QSize(18, 18));
  m_bar->setMovable(false);
  m_bar->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
  m_playAction = m_bar->addAction(style()->standardIcon(QStyle::SP_MediaPlay), "Putar");
  QAction* back = m_bar->addAction(style()->standardIcon(QStyle::SP_MediaSeekBackward), "−10s");
  QAction* forward = m_bar->addAction(style()->standardIcon(QStyle::SP_MediaSeekForward), "+10s");
  QAction* mute = m_bar->addAction(style()->standardIcon(QStyle::SP_MediaVolume), "Suara");
  QAction* open = m_bar->addAction("Buka eksternal");
  m_time = new QLabel("0:00 / 0:00", this);
  m_time->setObjectName("mediaTime");
  m_bar->addWidget(m_time);
  m_bar->addSeparator();
  auto* volumeLabel = new QLabel(" Volume ", this);
  m_bar->addWidget(volumeLabel);
  m_volume = new QSlider(Qt::Horizontal, this);
  m_volume->setRange(0, 100);
  m_volume->setValue(82);
  m_volume->setFixedWidth(100);
  m_bar->addWidget(m_volume);

  connect(m_playAction, &QAction::triggered, this, &VideoPlayer::onPlayPause);
  connect(back, &QAction::triggered, this, [this]() { seekBy(-10000); });
  connect(forward, &QAction::triggered, this, [this]() { seekBy(10000); });
  connect(mute, &QAction::triggered, this, [this, mute]() {
    m_audio->setMuted(!m_audio->isMuted());
    mute->setText(m_audio->isMuted() ? "Aktifkan suara" : "Suara");
  });
  connect(open, &QAction::triggered, this, [this]() {
    if (!m_path.isEmpty()) QDesktopServices::openUrl(QUrl::fromLocalFile(m_path));
  });
  connect(m_volume, &QSlider::valueChanged, this, [this](int value) {
    m_audio->setVolume(value / 100.0f);
    if (value > 0) m_audio->setMuted(false);
  });
  connect(m_player, &QMediaPlayer::mediaStatusChanged, this, &VideoPlayer::onMediaStatus);
  connect(m_player, &QMediaPlayer::errorOccurred, this, &VideoPlayer::onPlayerError);
  connect(m_player, &QMediaPlayer::positionChanged, this, &VideoPlayer::onPositionChanged);
  connect(m_player, &QMediaPlayer::durationChanged, this, &VideoPlayer::onDurationChanged);
  connect(m_player, &QMediaPlayer::playbackStateChanged, this, [this](QMediaPlayer::PlaybackState s) {
    if (m_playAction) {
      m_playAction->setIcon(style()->standardIcon(
          s == QMediaPlayer::PlayingState ? QStyle::SP_MediaPause : QStyle::SP_MediaPlay));
      m_playAction->setText(s == QMediaPlayer::PlayingState ? "Jeda" : "Putar");
    }
  });

  lay->addWidget(m_video, 1);
  lay->addWidget(m_fallback, 1);
  lay->addWidget(m_seek);
  lay->addWidget(m_info);
  lay->addWidget(m_bar);
}

bool VideoPlayer::isPlayable(const QString& path) {
  static const QSet<QString> ok{"mp4", "m4v", "webm", "ogv", "mov", "mkv", "avi", "mts", "m2ts", "wmv", "3gp", "ts", "flv"};
  return ok.contains(QFileInfo(path).suffix().toLower());
}

void VideoPlayer::load(const QString& path) {
  m_path = path;
  m_player->stop();
  m_seek->setRange(0, 0);
  m_seek->setEnabled(false);
  m_time->setText("0:00 / 0:00");
  if (path.isEmpty()) {
    m_video->hide();
    m_fallback->setText("Belum ada video dipilih.");
    m_fallback->show();
    m_info->clear();
    return;
  }
  const QFileInfo fi(path);
  m_info->setText(QString("%1  ·  %2  ·  diubah %3")
                     .arg(fi.fileName())
                     .arg(fi.size() >= 1048576 ? QString::number(fi.size() / 1048576.0, 'f', 1) + " MB" : QString::number(fi.size() / 1024.0, 'f', 0) + " KB")
                     .arg(fi.lastModified().toString("dd MMM yyyy, HH:mm")));
  if (!isPlayable(path)) {
    m_video->hide();
    m_fallback->setText(QString("Format .%1 belum didukung preview internal.\nMetadata tetap bisa dianalisis; gunakan Buka eksternal.").arg(fi.suffix().toUpper()));
    m_fallback->show();
    emit statusMessage("Format belum didukung preview internal.");
    return;
  }
  m_fallback->hide();
  m_video->show();
  m_player->setSource(QUrl::fromLocalFile(path));
  const bool autoplay = m_backend->appSettings().value("autoplay_preview").toBool(true);
  if (autoplay) m_player->play();
  emit statusMessage(autoplay ? "Membuka preview…" : "Preview siap.");
}

void VideoPlayer::onPlayPause() {
  if (m_path.isEmpty()) return;
  if (m_player->playbackState() == QMediaPlayer::PlayingState) m_player->pause();
  else m_player->play();
}

void VideoPlayer::onMediaStatus(QMediaPlayer::MediaStatus s) {
  if (s == QMediaPlayer::LoadedMedia || s == QMediaPlayer::BufferedMedia)
    emit statusMessage("Preview siap diputar.");
  else if (s == QMediaPlayer::InvalidMedia)
    onPlayerError();
}

void VideoPlayer::onPositionChanged(qint64 position) {
  if (!m_userSeeking) m_seek->setValue(int(position));
  m_time->setText(mediaClock(position) + " / " + mediaClock(m_player->duration()));
}

void VideoPlayer::onDurationChanged(qint64 duration) {
  m_seek->setRange(0, int(qMin<qint64>(duration, std::numeric_limits<int>::max())));
  m_seek->setEnabled(duration > 0);
  m_time->setText(mediaClock(m_player->position()) + " / " + mediaClock(duration));
}

void VideoPlayer::onSeekSlider(qint64 position) {
  m_player->setPosition(position);
  m_time->setText(mediaClock(position) + " / " + mediaClock(m_player->duration()));
}

void VideoPlayer::seekBy(qint64 deltaMs) {
  if (m_path.isEmpty()) return;
  const qint64 duration = m_player->duration();
  const qint64 next = qBound<qint64>(0, m_player->position() + deltaMs, qMax<qint64>(0, duration));
  m_player->setPosition(next);
}

void VideoPlayer::onPlayerError() {
  m_video->hide();
  m_fallback->setText("Video tidak bisa diputar preview internal.\nGunakan Buka eksternal untuk membukanya dengan player Windows.");
  m_fallback->show();
  emit statusMessage("Preview gagal: " + m_player->errorString());
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
  m_list->setIconSize(QSize(190, 118));
  m_list->setGridSize(QSize(216, 164));
  m_list->setResizeMode(QListView::Adjust);
  m_list->setMovement(QListView::Static);
  m_list->setUniformItemSizes(true);
  m_list->setSpacing(8);
  m_list->setSelectionMode(QAbstractItemView::SingleSelection);
  m_list->setWordWrap(true);
  m_list->setTextElideMode(Qt::ElideMiddle);
  m_list->setVerticalScrollMode(QAbstractItemView::ScrollPerPixel);
  connect(m_list, &QListWidget::itemActivated, this,
          [this](QListWidgetItem* it) { emit activated(it->data(Qt::UserRole).toString()); });
  connect(m_list, &QListWidget::itemClicked, this,
          [this](QListWidgetItem* it) { emit activated(it->data(Qt::UserRole).toString()); });
  lay->addWidget(m_list);

  auto* timer = new QTimer(this);
  timer->setInterval(120);
  connect(timer, &QTimer::timeout, this, &Gallery::renderThumbs);
  timer->start();
}

void Gallery::setThumbnailBatch(int batch) {
  m_thumbnailBatch = qBound(6, batch, 64);
}

void Gallery::setItems(const QList<GalleryItem>& items, bool isVideo) {
  m_items = items;
  m_isVideo = isVideo;
  m_list->clear();
  m_list->setUpdatesEnabled(false);
  for (const GalleryItem& g : items) {
    const QFileInfo fi(g.path);
    const double mb = g.size / 1048576.0;
    const QString size = mb >= 1.0 ? QString::number(mb, 'f', 1) + " MB"
                                   : QString::number(g.size / 1024.0, 'f', 0) + " KB";
    auto* it = new QListWidgetItem(QIcon(), QString("%1\n%2 · %3")
                                               .arg(fi.fileName())
                                               .arg(fi.suffix().toUpper())
                                               .arg(size),
                                   m_list);
    it->setData(Qt::UserRole, g.path);
    it->setToolTip(g.path);
    it->setTextAlignment(Qt::AlignLeft | Qt::AlignVCenter);
  }
  m_list->setUpdatesEnabled(true);
  m_list->viewport()->update();
}

void Gallery::setFilter(const QString& text) {
  const QString q = text.trimmed().toLower();
  for (int i = 0; i < m_list->count(); ++i) {
    QListWidgetItem* it = m_list->item(i);
    const bool match = q.isEmpty() || m_items[i].path.toLower().contains(q);
    it->setHidden(!match);
  }
}

void Gallery::renderThumbs() {
  int done = 0;
  for (int i = 0; i < m_list->count() && done < m_thumbnailBatch; ++i) {
    QListWidgetItem* it = m_list->item(i);
    if (!it->icon().isNull() || it->isHidden()) continue;

    QPixmap pm;
    if (!m_isVideo) {
      QImageReader rd(m_items[i].path);
      rd.setAutoTransform(true);
      rd.setScaledSize(QSize(380, 240));
      const QImage img = rd.read();
      if (!img.isNull())
        pm = QPixmap::fromImage(img);
    }

    if (pm.isNull()) {
      pm = QPixmap(380, 240);
      pm.fill(Qt::transparent);
      QPainter p(&pm);
      p.setRenderHint(QPainter::Antialiasing);
      const QRectF card(1, 1, pm.width() - 2, pm.height() - 2);
      QLinearGradient grad(card.topLeft(), card.bottomRight());
      if (m_isVideo) {
        grad.setColorAt(0.0, QColor("#2b3152"));
        grad.setColorAt(1.0, QColor("#111728"));
      } else {
        grad.setColorAt(0.0, QColor("#252a3d"));
        grad.setColorAt(1.0, QColor("#161a28"));
      }
      p.setBrush(grad);
      p.setPen(QPen(QColor("#3d4868"), 1));
      p.drawRoundedRect(card, 12, 12);
      if (m_isVideo) {
        const QPointF c = pm.rect().center();
        p.setPen(Qt::NoPen);
        p.setBrush(QColor(128, 111, 244, 235));
        p.drawEllipse(c, 27, 27);
        QPainterPath tri;
        tri.moveTo(c.x() - 7, c.y() - 11);
        tri.lineTo(c.x() - 7, c.y() + 11);
        tri.lineTo(c.x() + 12, c.y());
        tri.closeSubpath();
        p.setBrush(QColor("#fbfaff"));
        p.drawPath(tri);
        p.setPen(QColor("#d6dcf2"));
        QFont f = p.font();
        f.setWeight(QFont::DemiBold);
        f.setPointSize(10);
        p.setFont(f);
        p.drawText(pm.rect().adjusted(14, 12, -14, -12),
                   Qt::AlignLeft | Qt::AlignBottom,
                   QFileInfo(m_items[i].path).suffix().toUpper());
      }
      p.end();
    }
    it->setIcon(QIcon(pm.scaled(QSize(190, 118), Qt::KeepAspectRatio,
                                Qt::SmoothTransformation)));
    ++done;
  }
}
