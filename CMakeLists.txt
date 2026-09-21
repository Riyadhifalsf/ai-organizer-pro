cmake_minimum_required(VERSION 3.26)
project(AIOrganizer VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(MSVC)
  add_compile_options(/W4 /EHsc /permissive- /Zc:__cplusplus)
  add_compile_definitions(_CRT_SECURE_NO_WARNINGS NOMINMAX WIN32_LEAN_AND_MEAN)
endif()

# ---- third party ----
add_library(sqlite3 STATIC third_party/sqlite-src/sqlite-amalgamation-3530400/sqlite3.c)
target_include_directories(sqlite3 PUBLIC third_party/sqlite-src/sqlite-amalgamation-3530400)
if(NOT MSVC)
  target_link_libraries(sqlite3 PUBLIC dl pthread)
endif()

set(SPDLOG_FMT_EXTERNAL_HO OFF CACHE BOOL "" FORCE)
add_subdirectory(third_party/spdlog EXCLUDE_FROM_ALL)

# ---- core ----
add_subdirectory(src)

# ---- tests ----
option(AIORGANIZER_BUILD_TESTS "Build GoogleTest suite" ON)
if(AIORGANIZER_BUILD_TESTS)
  enable_testing()
  set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
  set(BUILD_GMOCK OFF CACHE BOOL "" FORCE)
  add_subdirectory(third_party/googletest EXCLUDE_FROM_ALL)
  add_subdirectory(tests)
endif()
