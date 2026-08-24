# -*- coding: utf-8 -*-
"""
XM 市場選擇五濾網評分系統（精簡版 v2）- 離線桌面應用（原生視窗版）
--------------------------------------------------
這是精簡版，對應 xm_scorecard_web_v2.html：拿掉了即時報價查詢、策略指標分析
這兩個需要額外申請 API Key 的面板，只保留市場評分核心功能 + 財經日曆連結。
用 pywebview 把 xm_scorecard_web_v2.html 包成一個原生視窗程式，
在 Windows 上會使用系統內建的 WebView2（Edge 核心）來顯示畫面，
外觀跟網頁版一模一樣。

打包成 .exe 之後，使用者只要雙擊執行檔就能開啟，
不需要安裝 Python 或任何額外程式。
"""

import os
import sys
import webbrowser

import webview

try:
    import requests
except ImportError:
    requests = None


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class Api:
    def open_external(self, url: str):
        try:
            webbrowser.open(url)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _normalize_symbol(raw_symbol: str) -> str:
        s = raw_symbol.strip().upper()
        if not s:
            return s
        if "/" in s:
            return s
        if len(s) == 6 and s.isalpha():
            return f"{s[:3]}/{s[3:]}"
        return s

    def fetch_quote(self, api_key: str, symbol: str):
        if not requests:
            return {"error": "伺服器端缺少 requests 套件。"}
        if not api_key or not api_key.strip():
            return {"error": "尚未設定 Twelve Data API Key。"}
        if not symbol or not symbol.strip():
            return {"error": "請輸入商品代碼。"}
        normalized = self._normalize_symbol(symbol)
        try:
            resp = requests.get(
                "https://api.twelvedata.com/quote",
                params={"symbol": normalized, "apikey": api_key.strip()},
                timeout=12,
            )
        except requests.exceptions.RequestException as e:
            return {"error": f"連線失敗：{e}"}
        if resp.status_code == 429:
            return {"error": "已達 API 呼叫次數上限。"}
        if resp.status_code != 200:
            return {"error": f"API 回應異常（狀態碼 {resp.status_code}）。"}
        try:
            data = resp.json()
        except ValueError:
            return {"error": "API 回傳格式異常。"}
        if isinstance(data, dict) and data.get("status") == "error":
            msg = data.get("message", "未知錯誤")
            return {"error": f"查詢「{normalized}」失敗：{msg}"}
        data["symbol_used"] = normalized
        return {"quote": data}

    INDICATOR_DEFAULTS = {
        "rsi": {"time_period": 14},
        "sma": {"time_period": 20},
        "ema": {"time_period": 20},
        "bbands": {"time_period": 20},
        "adx": {"time_period": 14},
        "atr": {"time_period": 14},
        "cci": {"time_period": 14},
        "willr": {"time_period": 14},
    }

    def fetch_available_indicators(self, api_key: str):
        if not requests:
            return {"error": "伺服器端缺少 requests 套件。"}
        if not api_key or not api_key.strip():
            return {"error": "尚未設定 Twelve Data API Key。"}
        try:
            resp = requests.get(
                "https://api.twelvedata.com/technical_indicators",
                params={"apikey": api_key.strip()},
                timeout=15,
            )
        except requests.exceptions.RequestException as e:
            return {"error": f"連線失敗：{e}"}
        if resp.status_code != 200:
            return {"error": f"API 回應異常（狀態碼 {resp.status_code}）。"}
        try:
            data = resp.json()
        except ValueError:
            return {"error": "API 回傳格式異常。"}
        raw = data.get("data") or {}
        indicators = []
        for key, info in raw.items():
            if not isinstance(info, dict):
                continue
            indicators.append({"key": key, "name": info.get("full_name") or key.upper(), "type": info.get("type") or ""})
        indicators.sort(key=lambda x: (x["type"], x["name"]))
        if not indicators:
            return {"error": "查無可用指標清單。"}
        return {"indicators": indicators}

    def fetch_technical_indicators(self, api_key: str, symbol: str, interval: str = "1day", indicators=None):
        if not requests:
            return {"error": "伺服器端缺少 requests 套件。"}
        if not api_key or not api_key.strip():
            return {"error": "尚未設定 Twelve Data API Key。"}
        if not symbol or not symbol.strip():
            return {"error": "請輸入商品代碼。"}
        if not indicators:
            indicators = ["rsi", "macd"]
        indicators = [i for i in indicators if isinstance(i, str) and i.replace("_", "").isalnum()]
        if not indicators:
            return {"error": "沒有選擇任何有效的指標。"}
        normalized = self._normalize_symbol(symbol)
        key = api_key.strip()

        def _call(endpoint, extra_params):
            try:
                resp = requests.get(
                    f"https://api.twelvedata.com/{endpoint}",
                    params={"symbol": normalized, "interval": interval, "apikey": key, **extra_params},
                    timeout=12,
                )
            except requests.exceptions.RequestException as e:
                return None, f"連線失敗：{e}"
            if resp.status_code != 200:
                return None, f"API 回應異常（狀態碼 {resp.status_code}）。"
            try:
                data = resp.json()
            except ValueError:
                return None, "API 回傳格式異常。"
            if isinstance(data, dict) and data.get("status") == "error":
                return None, data.get("message", "未知錯誤")
            values = data.get("values") or []
            return (values[0] if values else None), None

        results, errors = {}, {}
        for ind in indicators:
            latest, err = _call(ind, self.INDICATOR_DEFAULTS.get(ind, {}))
            if err:
                errors[ind] = err
            elif latest:
                latest.pop("datetime", None)
                results[ind] = latest
        if not results:
            first_err = next(iter(errors.values()), "未知錯誤")
            return {"error": f"查詢「{normalized}」失敗：{first_err}"}
        return {"indicators": {"symbol_used": normalized, "interval": interval, "values": results, "errors": errors}}


def main():
    html_path = resource_path("xm_scorecard_web_v2.html")
    webview.create_window(
        title="XM 市場選擇五濾網評分系統（精簡版）",
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
