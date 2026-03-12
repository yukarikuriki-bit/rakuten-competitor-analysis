@echo off
chcp 65001 > nul
echo ========================================
echo  楽天競合調査ツール 起動中...
echo ========================================

:: Pythonチェック
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Pythonがインストールされていません。
    echo 以下のURLからPythonをダウンロードしてインストールしてください:
    echo https://www.python.org/downloads/
    echo.
    echo インストール時に「Add Python to PATH」に必ずチェックを入れてください。
    echo.
    pause
    exit /b 1
)

:: 依存パッケージのインストール
echo パッケージを確認・インストール中...
pip install -r requirements.txt -q

:: アプリ起動
echo.
echo ブラウザが自動で開きます...
echo 終了するにはこのウィンドウを閉じてください。
echo.
streamlit run app.py --server.headless false
pause
