# -*- coding: utf-8 -*-
"""
XM 市場選擇五濾網評分系統 - 離線桌面應用（原生視窗版）
--------------------------------------------------
用 pywebview 把 xm_scorecard_web.html 包成一個原生視窗程式，
在 Windows 上會使用系統內建的 WebView2（Edge 核心）來顯示畫面，
外觀跟網頁版一模一樣，但完全離線執行、不需要另外開瀏覽器。

打包成 .exe 之後，使用者只要雙擊執行檔就能開啟，
不需要安裝 Python 或任何額外程式。
"""

import os
import sys
import webview


def resource_path(relative_path: str) -> str:
    """取得資源檔案的實際路徑。
    開發時使用目前檔案所在目錄；打包成 PyInstaller 執行檔後，
    改用 PyInstaller 解壓縮的暫存目錄 (sys._MEIPASS)。
    """
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def main():
    html_path = resource_path("xm_scorecard_web.html")

    webview.create_window(
        title="XM 市場選擇五濾網評分系統",
        url=html_path,
        width=1180,
        height=780,
        min_size=(960, 600),
        text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
