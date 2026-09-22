// Backend.cpp — implementasi jembatan Qt.
#include "Backend.h"

#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QUuid>

namespace {
QString envOr(const char* name, const QString& fallback) {
  const QString v = QString::fromLocal8Bit(qgetenv(name)).trimmed();
  return v.isEmpty() ? fallback : v;
}
QJsonObject parseLastJsonLine(const QString& out) {
  const QStringList lines = out.split('\n');
  for (int i = lines.size() - 1; i >= 0; --i) {
    QJsonParseError err{};
    const QJsonDocument d =
        QJsonDocument::fromJson(lines[i].trimmed().toUtf8(), &err);
    if (err.error == QJsonParseError::NoError && d.isObject())
      return d.object();
  }
  return {};
}
}  // namespace

Backend::Backend(QObject* parent) : QObject(parent) {}
Backend::~Backend() {
  if (m_sidecar) {
    m_sidecar->closeWriteChannel();
    m_sidecar->terminate();
    m_sidecar->waitForFinished(3000);
    delete m_sidecar;
  }
}

QString Backend::proRoot() {
  const QString env = envOr("AIORG_ROOT", {});
  if (!env.isEmpty() && QFileInfo(env).exists()) return env;
  QDir dir(QCoreApplication::applicationDirPath());
  QStringList cands{dir.absolutePath(), dir.absoluteFilePath("resources")};
  for (int i = 0; i < 8; ++i) {
    cands << dir.absolutePath();
    if (!dir.cdUp()) break;
  }
  for (const QString& c : cands) {
    if (QFileInfo(c + "/sidecar.py").isFile() ||
        QFileInfo(c + "/aiorganizer.exe").isFile())
      return QDir(c).absolutePath();
  }
  return QDir::currentPath();
}

// Worker Python diblend ke root: sidecar.py + app/ di sebelah PRO root.
QString Backend::engineDir() const { return proRoot(); }

QString Backend::ffprobeBin() const {
  const QString env = envOr("AIORG_FFPROBE", {});
  if (!env.isEmpty()) return env;
  const QStringList c{proRoot() + "/third_party/ffmpeg/bin/ffprobe.exe",
                      engineDir() + "/app/ffmpeg/bin/ffprobe.exe",
                      engineDir() + "/ffmpeg/bin/ffprobe.exe",
                      proRoot() + "/ffmpeg/bin/ffprobe.exe"};
  for (const QString& p : c)
    if (QFileInfo(p).isFile()) return p;
  return "ffprobe.exe";
}

QString Backend::ffmpegBin() const {
  const QString fp = ffprobeBin();
  if (fp.endsWith("ffprobe.exe", Qt::CaseInsensitive))
    return fp.left(fp.size() - 11) + "ffmpeg.exe";
  return "ffmpeg.exe";
}

QString Backend::pythonProg() const {
  const QString env = envOr("AIORG_PYTHON", {});
  if (!env.isEmpty()) return env;
  const QStringList c{proRoot() + "/python.exe",
                      proRoot() + "/python/python.exe",
                      engineDir() + "/python.exe"};
  for (const QString& p : c)
    if (QFileInfo(p).isFile()) return p;
#ifdef Q_OS_WIN
  return "python";
#else
  return "python3";
#endif
}

QString Backend::defaultDb() const { return proRoot() + "/data/aiorganizer.db"; }

bool Backend::dbEnabled() const {
  QFile f(proRoot() + "/data/db.json");
  if (!f.open(QIODevice::ReadOnly)) return true;
  const QJsonObject o =
      QJsonDocument::fromJson(f.readAll()).object();
  return o.value("enabled").toBool(true);
}

QString Backend::activeDb() const {
  if (!dbEnabled()) return ":memory:";
  QFile f(proRoot() + "/data/db.json");
  if (f.open(QIODevice::ReadOnly)) {
    const QJsonObject o = QJsonDocument::fromJson(f.readAll()).object();
    const QString p = o.value("path").toString().trimmed();
    if (!p.isEmpty()) return p;
  }
  return defaultDb();
}

namespace {
QString findCoreBin() {
  const QString env = envOr("AIORG_CORE", {});
  if (!env.isEmpty()) return env;
  const QString root = Backend::proRoot();
  const QStringList c{root + "/aiorganizer.exe", root + "/aiorganizer",
                      root + "/resources/aiorganizer.exe",
                      root + "/build/src/aiorganizer.exe"};
  for (const QString& p : c)
    if (QFileInfo(p).isFile()) return p;
  return "aiorganizer";
}
}  // namespace

CoreResult Backend::runCore(const QStringList& args, int timeoutMs) {
  CoreResult r;
  QProcess p;
  p.setProgram(findCoreBin());
  p.setArguments(args);
  QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
  env.insert("AIORG_FFPROBE", ffprobeBin());
  p.setProcessEnvironment(env);
  p.start();
  if (!p.waitForStarted(15000)) {
    r.error = "core gagal dijalankan: " + p.errorString();
    return r;
  }
  if (!p.waitForFinished(timeoutMs)) {
    p.kill();
    r.error = "core timeout";
    return r;
  }
  r.raw = QString::fromUtf8(p.readAllStandardOutput());
  const QString err = QString::fromUtf8(p.readAllStandardError());
  r.json = parseLastJsonLine(r.raw);
  r.ok = !r.json.isEmpty()
             ? r.json.value("ok").toBool(p.exitCode() == 0)
             : (p.exitCode() == 0);
  if (!r.ok && r.error.isEmpty())
    r.error = err.trimmed().isEmpty() ? r.raw.right(2000) : err.right(1000);
  return r;
}

void Backend::ensureSidecar() {
  const QString wantDb = activeDb();
  if (m_sidecar && m_sidecar->state() != QProcess::NotRunning &&
      m_sidecarDb == wantDb)
    return;
  restartSidecar();
}

void Backend::restartSidecar() {
  if (m_sidecar) {
    m_sidecar->closeWriteChannel();
    m_sidecar->terminate();
    m_sidecar->waitForFinished(3000);
    delete m_sidecar;
    m_sidecar = nullptr;
  }
  m_sidecarDb = activeDb();
  m_sidecar = new QProcess(this);
  QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
  env.insert("AIORG_DB", m_sidecarDb);
  env.insert("PYTHONIOENCODING", "utf-8");
  m_sidecar->setProcessEnvironment(env);
  m_sidecar->setProgram(pythonProg());
  m_sidecar->setArguments({engineDir() + "/sidecar.py"});
  m_sidecar->start();
  m_sidecar->waitForStarted(15000);
  emit sidecarRestarted();
}

QJsonObject Backend::sidecar(const QString& cmd, const QJsonObject& extra,
                             int timeoutMs) {
  ensureSidecar();
  if (!m_sidecar || m_sidecar->state() == QProcess::NotRunning)
    return {{"ok", false}, {"error", "sidecar tidak jalan"}};
  // Kuras sisa output basi agar respons tidak tertukar.
  m_sidecar->readAllStandardOutput();
  QJsonObject req{{"id", ++m_seq}, {"cmd", cmd}};
  for (auto it = extra.begin(); it != extra.end(); ++it) req[it.key()] = it.value();
  m_sidecar->write(QJsonDocument(req).toJson(QJsonDocument::Compact) + "\n");
  if (!m_sidecar->waitForBytesWritten(15000))
    return {{"ok", false}, {"error", "sidecar tulis gagal"}};
  QElapsedTimer t;
  t.start();
  QByteArray buf;
  while (t.elapsed() < timeoutMs) {
    if (m_sidecar->state() == QProcess::NotRunning) break;
    if (!m_sidecar->waitForReadyRead(500)) continue;
    buf += m_sidecar->readAllStandardOutput();
    int nl = buf.indexOf('\n');
    while (nl >= 0) {
      const QByteArray line = buf.left(nl).trimmed();
      buf = buf.mid(nl + 1);
      if (!line.isEmpty()) {
        QJsonParseError err{};
        const QJsonDocument d = QJsonDocument::fromJson(line, &err);
        if (err.error == QJsonParseError::NoError && d.isObject()) {
          QJsonObject o = d.object();
          if (o.value("id").toVariant().toLongLong() == m_seq) return o;
        }
      }
      nl = buf.indexOf('\n');
    }
  }
  return {{"ok", false}, {"error", "sidecar timeout/mati"}};
}

QJsonObject Backend::aiEngine(const QStringList& argv, int timeoutMs) {
  // Selaraskan output ke results/ root proyek bila pemanggil tak menentukan
  // --out sendiri (blend: tak ada lagi results/ di dalam folder worker).
  QStringList a = argv;
  if (!a.contains("--out")) a << "--out" << proRoot();
  QJsonArray arr;
  for (const QString& s : a) arr.append(s);
  return sidecar("engine", {{"argv", arr}}, timeoutMs);
}

QJsonObject Backend::yoloStatus() { return sidecar("yolo-status", {}, 60000); }

QJsonObject Backend::yoloClassify(const QString& root, int limit,
                                  const QString& model) {
  return sidecar("yolo-classify",
                 {{"root", root}, {"limit", limit}, {"model", model}},
                 600000);
}

QJsonObject Backend::yoloTrainStart(int epochs, int batch, const QString& size,
                                    int imgsz, int patience) {
  return sidecar("yolo-train-start",
                 {{"epochs", epochs},
                  {"batch", batch},
                  {"model_size", size},
                  {"imgsz", imgsz},
                  {"patience", patience}},
                 60000);
}

QJsonObject Backend::yoloTrainStatus() {
  return sidecar("yolo-train-status", {}, 30000);
}

QJsonObject Backend::yoloTrainStop() {
  return sidecar("yolo-train-stop", {}, 30000);
}

QString Backend::annotPath() {
  return proRoot() + "/data/video-annotations.json";
}

QString Backend::normalizeKey(const QString& path) {
  QString t = path.trimmed();
  for (const char* p : {"\\\\?\\", "\\\\.\\"}) {
    const QString pre = QString::fromLatin1(p);
    if (t.startsWith(pre)) return t.mid(pre.size());
  }
  return t;
}

QJsonObject Backend::annotationFor(const QString& path) const {
  QFile f(annotPath());
  QJsonObject all;
  if (f.open(QIODevice::ReadOnly))
    all = QJsonDocument::fromJson(f.readAll()).object();
  const QString norm = normalizeKey(QDir::toNativeSeparators(path));
  for (const QString& k :
       {QDir::toNativeSeparators(path), norm, "\\\\?\\" + norm}) {
    if (all.contains(k)) {
      const QJsonObject v = all.value(k).toObject();
      return {{"tags", v.value("tags").toArray()}, {"note", v.value("note").toString()}};
    }
  }
  return {{"tags", QJsonArray()}, {"note", ""}};
}

bool Backend::saveAnnotation(const QString& path, const QStringList& tags,
                             const QString& note) {
  QFile f(annotPath());
  QJsonObject all;
  if (f.open(QIODevice::ReadOnly)) {
    all = QJsonDocument::fromJson(f.readAll()).object();
    f.close();
  }
  QDir().mkpath(QFileInfo(annotPath()).absolutePath());
  QJsonArray t;
  for (const QString& s : tags) {
    const QString c = s.trimmed();
    if (!c.isEmpty() && t.size() < 30) t.append(c);
  }
  all[normalizeKey(QDir::toNativeSeparators(path))] =
      QJsonObject{{"tags", t}, {"note", note.left(5000)}};
  if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return false;
  f.write(QJsonDocument(all).toJson(QJsonDocument::Indented));
  return true;
}

bool Backend::filesEqual(const QString& a, const QString& b) {
  QFile fa(a), fb(b);
  if (!fa.open(QIODevice::ReadOnly) || !fb.open(QIODevice::ReadOnly))
    return false;
  if (fa.size() != fb.size()) return false;
  while (!fa.atEnd()) {
    if (fa.read(1024 * 1024) != fb.read(1024 * 1024)) return false;
  }
  return true;
}

QJsonObject Backend::moveVerified(const QString& src, const QString& dst) {
  if (QFileInfo(dst).exists())
    return {{"ok", false}, {"error", "file tujuan sudah ada"}};
  QDir().mkpath(QFileInfo(dst).absolutePath());
  QString mode = "rename";
  if (!QFile::rename(src, dst)) {
    mode = "copy-verify-delete";
    if (!QFile::copy(src, dst))
      return {{"ok", false}, {"error", "copy gagal"}};
    if (!filesEqual(src, dst)) {
      QFile::remove(dst);
      return {{"ok", false}, {"error", "verifikasi copy gagal"}};
    }
    if (!QFile::remove(src)) {
      QFile::remove(dst);
      return {{"ok", false}, {"error", "sumber tak bisa dihapus setelah copy"}};
    }
  }
  return {{"ok", true}, {"path", dst}, {"mode", mode}};
}

void Backend::logActivity(const QString& action, const QString& detail) {  const QString p = proRoot() + "/data/activity.log";
  QDir().mkpath(QFileInfo(p).absolutePath());
  QFile f(p);
  if (f.open(QIODevice::Append)) {
    const QJsonObject e{{"ts", QDateTime::currentDateTimeUtc().toString(Qt::ISODate)},
                        {"action", action},
                        {"detail", detail.left(500)}};
    f.write(QJsonDocument(e).toJson(QJsonDocument::Compact) + "\n");
  }
}

QString Backend::appSettingsPath() {
  return proRoot() + "/data/settings.json";
}

QJsonObject Backend::appSettings() const {
  QJsonObject d{{"library_root", ""},
                {"dry_run_default", true},
                {"llm_enabled", false},
                {"language", "id"},
                {"first_run", true},
                {"yolo",
                 QJsonObject{{"epochs", 150},
                             {"batch", 16},
                             {"model_size", "m"},
                             {"imgsz", 288},
                             {"patience", 25}}}};
  QFile f(appSettingsPath());
  if (f.open(QIODevice::ReadOnly)) {
    const QJsonObject o = QJsonDocument::fromJson(f.readAll()).object();
    for (auto it = o.begin(); it != o.end(); ++it) d[it.key()] = it.value();
  }
  return d;
}

bool Backend::saveAppSettings(const QJsonObject& settings) const {
  QDir().mkpath(QFileInfo(appSettingsPath()).absolutePath());
  QFile f(appSettingsPath());
  if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return false;
  f.write(QJsonDocument(settings).toJson(QJsonDocument::Indented));
  return true;
}
