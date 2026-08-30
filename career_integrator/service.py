"""Web / API から使う統合処理の共通ロジック（入力検証・モード選択・LLM呼び出し）。"""

from __future__ import annotations

from typing import Any, Dict

from .client import call_llm
from .parsers import parse_interest_values_report, parse_tenmei_report
from .prompt import build_user_message, load_system_prompt, resolve_name

ALLOWED_MODELS = {"gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"}
MAX_CHARS = 60_000

# Vercel Hobby の実行上限は 60 秒。既定は速い構成、"deep" で高精度。
MODES: Dict[str, Dict[str, Any]] = {
    "fast": {"model": "gemini-2.5-flash", "max_output_tokens": 12000, "thinking_budget": None},
    "deep": {"model": "gemini-2.5-pro", "max_output_tokens": 24000, "thinking_budget": None},
}


def run_integration(payload: Dict[str, Any]) -> str:
    """payload: {interest, tenmei, name?, mode?, model?} -> 統合レポート Markdown。

    入力不正は ValueError、LLM 側の失敗は career_integrator.client.LLMError を送出。
    """
    interest_text = (payload.get("interest") or "").strip()
    tenmei_text = (payload.get("tenmei") or "").strip()
    if not interest_text or not tenmei_text:
        raise ValueError("『職業興味×価値観レポート』と『天命レポート』の両方を入力してください。")
    if len(interest_text) > MAX_CHARS or len(tenmei_text) > MAX_CHARS:
        raise ValueError(f"入力が長すぎます（各 {MAX_CHARS:,} 文字まで）。")

    cfg = dict(MODES.get(payload.get("mode", "fast"), MODES["fast"]))
    if payload.get("model") in ALLOWED_MODELS:
        cfg["model"] = payload["model"]

    iv = parse_interest_values_report(interest_text)
    tenmei = parse_tenmei_report(tenmei_text)
    name = resolve_name(iv, tenmei, (payload.get("name") or "").strip() or None)

    return call_llm(
        load_system_prompt(),
        build_user_message(iv, tenmei, name=name),
        **cfg,
    )
