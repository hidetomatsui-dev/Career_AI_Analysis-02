"""Vercel Serverless Function: POST /api/integrate

リクエスト JSON:
  {
    "interest": "<職業興味×価値観レポート全文>",   # 必須
    "tenmei":   "<四柱推命 天命レポート全文>",       # 必須
    "name":     "山田",                              # 任意（宛名の上書き）
    "mode":     "fast" | "deep",                     # 任意（既定 fast）
    "model":    "gemini-2.5-flash"                   # 任意（許可リスト内のみ、mode より優先）
  }

レスポンス JSON:
  200 -> {"report": "<統合レポート Markdown>"}
  4xx/5xx -> {"error": "<メッセージ>"}

必要な環境変数: GEMINI_API_KEY（または GOOGLE_API_KEY）
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from career_integrator.client import LLMError, call_llm, resolve_api_key
from career_integrator.parsers import (
    parse_interest_values_report,
    parse_tenmei_report,
)
from career_integrator.prompt import (
    build_user_message,
    load_system_prompt,
    resolve_name,
)

_ALLOWED_MODELS = {"gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"}
_MAX_CHARS = 60_000

# Vercel Hobby の実行上限は 60 秒。既定は速い構成にし、"deep" で高精度に切り替える。
# (model, max_output_tokens, thinking_budget)  thinking_budget=None はモデル既定（動的思考）
_MODES = {
    "fast": ("gemini-2.5-flash", 12000, None),
    "deep": ("gemini-2.5-pro", 24000, None),
}


def integrate(payload: dict) -> str:
    interest_text = (payload.get("interest") or "").strip()
    tenmei_text = (payload.get("tenmei") or "").strip()
    if not interest_text or not tenmei_text:
        raise ValueError("『職業興味×価値観レポート』と『天命レポート』の両方を入力してください。")
    if len(interest_text) > _MAX_CHARS or len(tenmei_text) > _MAX_CHARS:
        raise ValueError(f"入力が長すぎます（各 {_MAX_CHARS:,} 文字まで）。")

    model, max_output_tokens, thinking_budget = _MODES.get(
        payload.get("mode", "fast"), _MODES["fast"]
    )
    if payload.get("model") in _ALLOWED_MODELS:
        model = payload["model"]

    iv = parse_interest_values_report(interest_text)
    tenmei = parse_tenmei_report(tenmei_text)
    name = resolve_name(iv, tenmei, (payload.get("name") or "").strip() or None)

    return call_llm(
        load_system_prompt(),
        build_user_message(iv, tenmei, name=name),
        model=model,
        max_output_tokens=max_output_tokens,
        thinking_budget=thinking_budget,
    )


class handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def _json(self, status: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):  # noqa: N802
        try:
            length = int(self.headers.get("content-length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "リクエスト形式が不正です（JSON body が必要です）。"})

        if not resolve_api_key():
            return self._json(
                500,
                {"error": "サーバに GEMINI_API_KEY が設定されていません。Vercel の環境変数を確認してください。"},
            )

        try:
            report = integrate(payload)
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        except LLMError as e:
            return self._json(502, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"error": f"想定外のエラー: {e}"})

        return self._json(200, {"report": report})
