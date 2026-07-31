name: 打包 Windows 離線版執行檔

# 兩種觸發方式：
# 1. 手動點擊「Run workflow」按鈕（推薦，隨時可以重新打包）
# 2. 推送/上傳檔案到 main 分支時自動打包
on:
  workflow_dispatch:
  push:
    branches: [ main ]
    paths:
      - 'native_app/**'

jobs:
  build:
    # 使用 GitHub 提供的雲端 Windows 機器來打包
    runs-on: windows-latest

    steps:
      - name: 取得專案檔案
        uses: actions/checkout@v4

      - name: 安裝 Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: 安裝必要套件
        run: |
          pip install pywebview pyinstaller

      - name: 打包成單一 .exe 檔案
        working-directory: native_app
        run: |
          pyinstaller --onefile --windowed `
            --name "XM市場選擇評分系統(離線版)" `
            --add-data "xm_scorecard_web.html;." `
            app.py

      - name: 上傳打包好的執行檔
        uses: actions/upload-artifact@v4
        with:
          name: XM市場選擇評分系統-Windows離線版
          path: native_app/dist/*.exe
