# -*- coding: utf-8 -*-
"""
XM 市場選擇五濾網評分系統 - 離線桌面應用（原生視窗版）
--------------------------------------------------
用 pywebview 把 xm_scorecard_web.html 包成一個原生視窗程式，
在 Windows 上會使用系統內建的 WebView2（Edge 核心）來顯示畫面，
外觀跟網頁版一模一樣。

打包成 .exe 之後，使用者只要雙擊執行檔就能開啟，
不需要安裝 Python 或任何額外程式。

新增：財經日曆 + 即時報價功能
------------------------------
瀏覽器直接呼叫外部 API 常會被瀏覽器的 CORS 安全限制擋下來，
所以改成由這支 Python 程式（不受瀏覽器 CORS 限制）幫忙呼叫 API，
再把結果透過 pywebview 的 js_api 橋接傳回網頁畫面顯示。
網頁端呼叫方式：
  window.pywebview.api.fetch_economic_calendar(apiKey, daysAhead)   -- 資料來源：Finnhub
  window.pywebview.api.fetch_quote(apiKey, symbol)                  -- 資料來源：Twelve Data

需要網路連線，且需要使用者自行申請免費 API Key
（申請帳號這部分請自行操作，這裡不會幫忙處理帳密）：
  財經日曆：https://finnhub.io （注意：財經日曆屬於 Finnhub 付費方案功能，
            免費方案會回傳 403 錯誤，目前沒有免費管道）
  即時報價：https://twelvedata.com （免費方案涵蓋外匯、貴金屬、美股即時報價，
            每天 800 次、每分鐘 8 次呼叫上限）

報價僅供評分時參考用，不是即時成交報價，也不是交易依據，
實際下單價格請以 XM 平台當下顯示的報價為準。
"""

import os
import sys
from datetime import date, timedelta

import webview

try:
    import requests
except ImportError:  # 萬一環境沒裝 requests，財經日曆功能會回傳錯誤訊息，不影響評分表其他功能
    requests = None


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


class Api:
    """透過 pywebview 暴露給網頁 JavaScript 呼叫的橋接函式。"""

    def fetch_economic_calendar(self, api_key: str, days_ahead: int = 2):
        """呼叫 Finnhub 財經日曆 API，回傳未來 N 天的經濟事件列表。

        回傳格式：
          成功：{"events": [...]}
          失敗：{"error": "錯誤訊息文字"}
        """
        if not requests:
            return {"error": "伺服器端缺少 requests 套件，無法呼叫網路 API。"}

        if not api_key or not api_key.strip():
            return {"error": "尚未設定 Finnhub API Key，請先到設定欄位輸入。"}

        try:
            days_ahead = max(1, min(int(days_ahead), 14))
        except (TypeError, ValueError):
            days_ahead = 2

        today = date.today()
        to_date = today + timedelta(days=days_ahead)

        try:
            resp = requests.get(
                "https://finnhub.io/api/v1/calendar/economic",
                params={
                    "from": today.isoformat(),
                    "to": to_date.isoformat(),
                    "token": api_key.strip(),
                },
                timeout=12,
            )
        except requests.exceptions.RequestException as e:
            return {"error": f"連線失敗，請確認網路連線是否正常：{e}"}

        if resp.status_code == 401:
            return {"error": "API Key 無效，請確認在 finnhub.io 複製的金鑰是否正確。"}
        if resp.status_code == 429:
            return {"error": "已達 API 呼叫次數上限，請稍後再試（免費方案有每分鐘呼叫次數限制）。"}
        if resp.status_code != 200:
            return {"error": f"API 回應異常（狀態碼 {resp.status_code}），請稍後再試。"}

        try:
            data = resp.json()
        except ValueError:
            return {"error": "API 回傳格式異常，無法解析。"}

        # Finnhub 回傳鍵名可能隨版本調整，這裡盡量兼容常見的欄位命名
        events = data.get("economicCalendar") or data.get("economic_calendar") or []
        if not isinstance(events, list):
            events = []

        return {"events": events}

    @staticmethod
    def _normalize_symbol(raw_symbol: str) -> str:
        """把使用者輸入的商品代碼轉成 Twelve Data 慣用格式。

        - 已經含有斜線（例如 "EUR/USD"、"XAU/USD"）就直接使用，不做任何轉換
        - 純英文字母且長度為 6（例如 "EURUSD"、"XAUUSD"、"USDJPY"）視為外匯/貴金屬，
          自動轉成 "XXX/YYY" 格式（Twelve Data 外匯/商品報價慣用的表示方式）
        - 其他情況（例如美股代碼 "AAPL"）直接原樣送出，不做轉換
        """
        s = raw_symbol.strip().upper()
        if not s:
            return s
        if "/" in s:
            return s
        if len(s) == 6 and s.isalpha():
            return f"{s[:3]}/{s[3:]}"
        return s

    def fetch_quote(self, api_key: str, symbol: str):
        """呼叫 Twelve Data 即時報價 API。

        回傳格式：
          成功：{"quote": {...Twelve Data 原始欄位..., "symbol_used": "實際查詢用的代碼"}}
          失敗：{"error": "錯誤訊息文字"}

        提醒：報價可能有些微延遲，僅供評分時參考，不是即時成交報價，
        實際下單請以 XM 平台報價為準。
        """
        if not requests:
            return {"error": "伺服器端缺少 requests 套件，無法呼叫網路 API。"}

        if not api_key or not api_key.strip():
            return {"error": "尚未設定 Twelve Data API Key，請先到設定欄位輸入。"}

        if not symbol or not symbol.strip():
            return {"error": "請輸入商品代碼，例如 EURUSD、XAUUSD、AAPL。"}

        normalized = self._normalize_symbol(symbol)

        try:
            resp = requests.get(
                "https://api.twelvedata.com/quote",
                params={"symbol": normalized, "apikey": api_key.strip()},
                timeout=12,
            )
        except requests.exceptions.RequestException as e:
            return {"error": f"連線失敗，請確認網路連線是否正常：{e}"}

        if resp.status_code == 429:
            return {"error": "已達 API 呼叫次數上限，請稍後再試（免費方案有每分鐘/每日呼叫次數限制）。"}
        if resp.status_code != 200:
            return {"error": f"API 回應異常（狀態碼 {resp.status_code}），請稍後再試。"}

        try:
            data = resp.json()
        except ValueError:
            return {"error": "API 回傳格式異常，無法解析。"}

        # Twelve Data 錯誤時會回傳 {"status": "error", "message": "..."}
        if isinstance(data, dict) and data.get("status") == "error":
            msg = data.get("message", "未知錯誤")
            return {
                "error": (
                    f"查詢「{normalized}」失敗：{msg}\n"
                    "請確認 API Key 是否正確，或代碼格式是否正確（外匯/貴金屬請用 XXX/YYY 格式）。"
                )
            }

        data["symbol_used"] = normalized
        return {"quote": data}


def main():
    html_path = resource_path("xm_scorecard_web.html")

    webview.create_window(
        title="XM 市場選擇五濾網評分系統",
        url=html_path,
        width=1180,
        height=780,
        min_size=(960, 600),
        text_select=True,
        js_api=Api(),
    )
    webview.start()


if __name__ == "__main__":
    main()
