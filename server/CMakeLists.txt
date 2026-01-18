以下は、配布物に含めるための方法

1) CMakeLists.txt にオプションを追加

option(BUILD_PY_SERVER "Build python server executable (PyInstaller) for packaging" OFF)

2) ON のときだけ PyInstaller ターゲットと install を有効化

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(PY_DIR       ${CMAKE_SOURCE_DIR}/python)
set(PY_ENTRY     ${PY_DIR}/my_server_entry.py)
set(PY_REQ       ${PY_DIR}/requirements.txt)
set(PY_BUILD_DIR ${CMAKE_BINARY_DIR}/py_build)
set(PY_DIST_DIR  ${CMAKE_BINARY_DIR}/py_dist)

set(VENV_DIR ${CMAKE_BINARY_DIR}/venv)
if (WIN32)
  set(VENV_PY ${VENV_DIR}/Scripts/python.exe)
else()
  set(VENV_PY ${VENV_DIR}/bin/python)
endif()

if (BUILD_PY_SERVER)

  # (任意) Pythonソース一式の変更も検知したい場合
  file(GLOB_RECURSE PY_SRCS CONFIGURE_DEPENDS ${PY_DIR}/*.py)

  # venv作成
  add_custom_command(
    OUTPUT  ${VENV_DIR}/pyvenv.cfg
    COMMAND ${Python3_EXECUTABLE} -m venv ${VENV_DIR}
    COMMAND ${VENV_PY} -m pip install -U pip
    COMMENT "Create venv"
  )

  # 依存インストール（requirements変更時のみ）
  set(PY_DEPS_STAMP ${CMAKE_BINARY_DIR}/.py_deps_installed)
  add_custom_command(
    OUTPUT  ${PY_DEPS_STAMP}
    DEPENDS ${VENV_DIR}/pyvenv.cfg ${PY_REQ}
    COMMAND ${VENV_PY} -m pip install -r ${PY_REQ}
    COMMAND ${VENV_PY} -m pip install pyinstaller
    COMMAND ${CMAKE_COMMAND} -E touch ${PY_DEPS_STAMP}
    COMMENT "Install python deps"
  )

  # PyInstaller 実行（ソース/依存が変わった時だけ）
  if (WIN32)
    set(PY_SERVER_EXE ${PY_DIST_DIR}/my_server_entry/my_server_entry.exe)
  else()
    set(PY_SERVER_EXE ${PY_DIST_DIR}/my_server_entry/my_server_entry)
  endif()

  add_custom_command(
    OUTPUT  ${PY_SERVER_EXE}
    DEPENDS ${PY_DEPS_STAMP} ${PY_SRCS}
    COMMAND ${VENV_PY} -m PyInstaller
            --noconfirm --clean
            --workpath ${PY_BUILD_DIR}
            --distpath ${PY_DIST_DIR}
            ${PY_ENTRY}
    WORKING_DIRECTORY ${PY_DIR}
    USES_TERMINAL
    COMMENT "Build python server exe"
  )

  add_custom_target(py_server_exe DEPENDS ${PY_SERVER_EXE})

  # 配布物に同梱
  install(PROGRAMS ${PY_SERVER_EXE} DESTINATION bin)

  # (任意) パッケージ作成ターゲットが Python exe を先に作るように
  # cpack する前に: cmake --build . --target py_server_exe
endif()


3) 使い方（ビルドコマンド）
通常ビルド（Python exe 作らない）
cmake -S . -B build -G Ninja
cmake --build build

配布ビルド（Python exe も作る）

cmake -S . -B build_release -G Ninja -DBUILD_PY_SERVER=ON
cmake --build build_release --target py_server_exe
cmake --build build_release --target install
# 必要なら cpack
# (build_release ディレクトリで) cpack

