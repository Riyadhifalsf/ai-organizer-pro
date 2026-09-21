// AIOrganizerPro-web.exe — launcher Win32 (tanpa console).
// Cari PRO root (folder exe sendiri, atau folder di atasnya kalau exe ada di
// subfolder seperti dist-exe), jalankan `node server\server.mjs` detached,
// tunggu port 8471, buka browser default.
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <shellapi.h>

#include <string>

static std::wstring ExeDir() {
  wchar_t p[MAX_PATH];
  GetModuleFileNameW(NULL, p, MAX_PATH);
  std::wstring s = p;
  size_t i = s.find_last_of(L"\\/");
  return (i == std::wstring::npos) ? L"." : s.substr(0, i);
}

static bool PortOpen() {
  WSADATA w;
  if (WSAStartup(MAKEWORD(2, 2), &w) != 0) return false;
  SOCKET s = socket(AF_INET, SOCK_STREAM, 0);
  sockaddr_in a{};
  a.sin_family = AF_INET;
  a.sin_port = htons(8471);
  a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  bool ok = connect(s, (sockaddr*)&a, sizeof a) == 0;
  closesocket(s);
  WSACleanup();
  return ok;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int) {
  std::wstring dir = ExeDir();
  // PRO = folder exe bila ada server\server.mjs di situ, else parent-nya.
  std::wstring pro = dir;
  if (GetFileAttributesW((dir + L"\\server\\server.mjs").c_str()) ==
      INVALID_FILE_ATTRIBUTES) {
    size_t i = dir.find_last_of(L"\\/");
    if (i != std::wstring::npos) pro = dir.substr(0, i);
  }
  std::wstring server = pro + L"\\server\\server.mjs";
  DWORD attr = GetFileAttributesW(server.c_str());
  if (attr == INVALID_FILE_ATTRIBUTES) {
    MessageBoxW(NULL, (L"server.mjs tidak ketemu:\n" + server).c_str(),
                L"AIOrganizerPro", MB_ICONERROR);
    return 1;
  }
  if (!PortOpen()) {
    std::wstring cmd =
        L"cmd /c start \"AIOrganizerPro-server\" /min node \"" + server + L"\"";
    STARTUPINFOW si{};
    si.cb = sizeof si;
    PROCESS_INFORMATION pi{};
    std::wstring db = pro + L"\\data\\aiorganizer.db";
    SetEnvironmentVariableW(L"AIORG_DB", db.c_str());
    if (CreateProcessW(NULL, &cmd[0], NULL, NULL, FALSE,
                       CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
      CloseHandle(pi.hThread);
      CloseHandle(pi.hProcess);
    } else {
      MessageBoxW(NULL, L"Gagal menjalankan node. Install Node.js 20+.",
                  L"AIOrganizerPro", MB_ICONERROR);
      return 1;
    }
    for (int t = 0; t < 100 && !PortOpen(); t++) Sleep(150);
  }
  ShellExecuteW(NULL, L"open", L"http://127.0.0.1:8471/", NULL, NULL,
                SW_SHOWNORMAL);
  return 0;
}
