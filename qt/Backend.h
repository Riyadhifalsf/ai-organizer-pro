#pragma once
// Backend.h — jembatan Qt ke core C++ (aiorganizer.exe --json), sidecar
// Python (persisten, JSON per baris), ffprobe/ffmpeg, dan store anotasi.
// Kontrak aman: tanpa hapus permanen; move selalu terverifikasi (di sisi
// pelaksana); training YOLO detached + pid file (di sidecar).
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QObject>
#include <QProcess>
#include <QString>
#include <QStringList>

struct CoreResult {
  bool ok = false;
  QJsonObject json;
  QString raw;
  QString error;
};

class Backend : public QObject {
  Q_OBJECT
 public:
  explicit Backend(QObject* parent = nullptr);
  ~Backend() override;

  // ---- path ----
  static QString proRoot();
  QString engineDir() const;
  QString ffprobeBin() const;
  QString ffmpegBin() const;
  QString pythonProg() const;
  QString defaultDb() const;
  // Saklar data/db.json {enabled, path}. Mati = ":memory:".
  bool dbEnabled() const;
  QString activeDb() const;

  // ---- core C++ (sinkron, boleh lama; panggil dari worker thread) ----
  CoreResult runCore(const QStringList& args, int timeoutMs = 600000);

  // ---- sidecar Python persisten ----
  QJsonObject sidecar(const QString& cmd, const QJsonObject& extra = {},
                      int timeoutMs = 120000);
  void restartSidecar();

  // ---- AI engine (analyze/broken/organize/yolo-classify/...) ----
  QJsonObject aiEngine(const QStringList& argv, int timeoutMs = 1800000);

  // ---- YOLO ----
  QJsonObject yoloStatus();
  QJsonObject yoloClassify(const QString& root, int limit = 50,
                           const QString& model = {});
  QJsonObject yoloTrainStart(int epochs, int batch, const QString& size,
                             int imgsz, int patience);
  QJsonObject yoloTrainStatus();
  QJsonObject yoloTrainStop();

  // ---- anotasi lokal (data/video-annotations.json, format sama dgn Tauri) ----
  static QString annotPath();
  QJsonObject annotationFor(const QString& path) const;
  bool saveAnnotation(const QString& path, const QStringList& tags,
                      const QString& note);
  static QString normalizeKey(const QString& path);

  // ---- util file terverifikasi (dipakai bila pelaksana bukan core) ----
  static bool filesEqual(const QString& a, const QString& b);
  // Pindah terverifikasi (rename; lintas-volume: copy+verify+delete).
  // Return {"ok","path","mode"} atau {"ok":false,"error"}.
  static QJsonObject moveVerified(const QString& src, const QString& dst);

  void logActivity(const QString& action, const QString& detail);

 signals:
  void sidecarRestarted();

 private:
  void ensureSidecar();
  QProcess* m_sidecar = nullptr;
  qint64 m_seq = 0;
  QString m_sidecarDb;
};
