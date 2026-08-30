"""Vercel Python エントリポイント（WSGI アプリ）。

ルーティング:
  GET  /                     -> public/index.html
  GET  /samples/*.txt など    -> public/ 配下の静的ファイル
  POST /api/integrate         -> {interest, tenmei, name?, mode?} を統合し {report} を返す

必要な環境変数: GEMINI_API_KEY（または GOOGLE_API_KEY）
ローカル: `python app.py` で開発用サーバ（http://localhost:8000）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from career_integrator.client import LLMError, resolve_api_key
from career_integrator.service import run_integration

_PUBLIC = _ROOT / "public"
_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}
_CORS = [
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Headers", "Content-Type"),
    ("Access-Control-Allow-Methods", "POST, OPTIONS"),
]


def _json_response(start_response, status: str, obj: dict):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ] + _CORS
    start_response(status, headers)
    return [body]


def _resolve_static(path: str):
    rel = "index.html" if path in ("", "/") else path.lstrip("/")
    try:
        target = (_PUBLIC / rel).resolve()
        target.relative_to(_PUBLIC.resolve())
    except (ValueError, OSError):
        return None
    if not target.is_file():
        return None
    ctype = _CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
    return ctype, target.read_bytes()


def _handle_integrate(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    if method == "OPTIONS":
        start_response("204 No Content", list(_CORS))
        return [b""]
    if method != "POST":
        return _json_response(start_response, "405 Method Not Allowed",
                              {"error": "POST を使用してください。"})

    try:
        size = int(environ.get("CONTENT_LENGTH") or 0)
        raw = environ["wsgi.input"].read(size) if size > 0 else b"{}"
        payload = json.loads(raw or b"{}")
        if not isinstance(payload, dict):
            raise ValueError
    except (ValueError, json.JSONDecodeError):
        return _json_response(start_response, "400 Bad Request",
                              {"error": "リクエスト形式が不正です（JSON body が必要です）。"})

    if not resolve_api_key():
        return _json_response(start_response, "500 Internal Server Error",
                              {"error": "サーバに GEMINI_API_KEY が設定されていません。Vercel の環境変数を確認してください。"})

    try:
        report = run_integration(payload)
    except ValueError as e:
        return _json_response(start_response, "400 Bad Request", {"error": str(e)})
    except LLMError as e:
        return _json_response(start_response, "502 Bad Gateway", {"error": str(e)})
    except Exception as e:  # noqa: BLE001
        return _json_response(start_response, "500 Internal Server Error",
                              {"error": f"想定外のエラー: {e}"})

    return _json_response(start_response, "200 OK", {"report": report})


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/") or "/"
    method = environ.get("REQUEST_METHOD", "GET")

    if path == "/api/integrate":
        return _handle_integrate(environ, start_response)

    if method in ("GET", "HEAD"):
        served = _resolve_static(path)
        if served:
            ctype, data = served
            start_response("200 OK", [
                ("Content-Type", ctype),
                ("Content-Length", str(len(data))),
            ])
            return [b"" if method == "HEAD" else data]

    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"Not Found"]


if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    port = 8000
    print(f"http://localhost:{port}  (Ctrl+C で停止)")
    make_server("localhost", port, app).serve_forever()
