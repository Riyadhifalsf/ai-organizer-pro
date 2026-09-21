add_library(aiorg_core STATIC
  core/database/database.cpp
  core/filesystem/utf8.cpp
  core/scanner/scanner.cpp
  core/hashing/sha256.cpp
  core/hashing/hash_cache.cpp
  core/hashing/pipeline.cpp
  core/duplicate/duplicate.cpp
)
target_include_directories(aiorg_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} .)
target_link_libraries(aiorg_core PUBLIC sqlite3 spdlog::spdlog)
if(WIN32)
  target_link_libraries(aiorg_core PUBLIC bcrypt)
endif()

add_executable(aiorganizer main.cpp)
target_link_libraries(aiorganizer PRIVATE aiorg_core)
