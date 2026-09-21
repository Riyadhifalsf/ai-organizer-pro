# Build (Windows 10/11, x64)

## One-time toolchain (~15 GB on D:, C: stays lean)

```powershell
winget install --id Kitware.CMake --silent                    # cmake
pip install ninja                                              # ninja binary
# VS 2022 Build Tools -> D:\development\environment-files\VS_BuildTools
# (layout first, then install). Dulu di D:\tools (pindah 2026-09-20).
$T = "D:\development\environment-files\VS_BuildTools"
& "$T\vs_BuildTools.exe" --layout "$T\VSLayout" `
  --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --lang en-US
& "$T\VSLayout\vs_BuildTools.exe" --installPath "$T\VS" --wait --quiet --norestart
```

Deps are vendored, no package manager needed today:
`third_party/` = SQLite amalgamation 3.53.4, googletest + spdlog (git shallow).

## Configure / build / test

```powershell
$env:Path = 'C:\Program Files\CMake\bin;<python>\Scripts;' + $env:Path
$V = "D:\development\environment-files\VS_BuildTools\VS\VC\Auxiliary\Build\vcvars64.bat"
cmd /c "`"$V`" >nul && cmake -S D:\ai-organizer-pro -B D:\ai-organizer-pro\build -G Ninja -DCMAKE_BUILD_TYPE=Release"
cmd /c "`"$V`" >nul && cmake --build D:\ai-organizer-pro\build --config Release"
D:\ai-organizer-pro\build\tests\aiorg_tests.exe
D:\ai-organizer-pro\aiorganizer.exe scan D:\Data --db D:\ai-organizer-pro\data\aiorganizer.db
```

## Coming next (in order)

- Qt 6 via `pip install aqtinstall` → `aqt install-qt windows desktop 6.8.x win64_msvc2022_64`
- FFmpeg dev libs (BtbN shared) for native libav* video analyzer
- ONNX Runtime release zip for vision classifier
