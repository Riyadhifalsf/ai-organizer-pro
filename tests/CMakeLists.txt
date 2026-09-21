add_executable(aiorg_tests test_scanner.cpp test_hash.cpp test_duplicate.cpp test_db_v4.cpp)
target_link_libraries(aiorg_tests PRIVATE aiorg_core gtest_main)
include(GoogleTest)
gtest_discover_tests(aiorg_tests)
