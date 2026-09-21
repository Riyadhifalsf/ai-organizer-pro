# Qt GUI AIOrganizerPro (Widgets + Multimedia). Independen dari build inti:
#   cmake -S qt -B qt/build -DCMAKE_PREFIX_PATH=D:/Qt/6.8.3/msvc2022_64
#   cmake --build qt/build --config Release
cmake_minimum_required(VERSION 3.26)
project(AIOrganizerProQt VERSION 0.4.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)

if(MSVC)
  add_compile_options(/W4 /EHsc /permissive- /Zc:__cplusplus /utf-8)
  add_compile_definitions(_CRT_SECURE_NO_WARNINGS NOMINMAX WIN32_LEAN_AND_MEAN)
endif()

find_package(Qt6 REQUIRED COMPONENTS Widgets Multimedia MultimediaWidgets Concurrent)

add_executable(AIOrganizerPro
  main.cpp
  Backend.h Backend.cpp
  MediaWidgets.h MediaWidgets.cpp
  Pages.h Pages.cpp
  MainWindow.h MainWindow.cpp
)
target_link_libraries(AIOrganizerPro PRIVATE
  Qt6::Widgets Qt6::Multimedia Qt6::MultimediaWidgets Qt6::Concurrent)

if(WIN32)
  # ON = console dev (lihat log); OFF = exe bersih tanpa console.
  option(QT_CONSOLE_DEV "Console dev" OFF)
  if(NOT QT_CONSOLE_DEV)
    set_target_properties(AIOrganizerPro PROPERTIES WIN32_EXECUTABLE TRUE)
  endif()
endif()
