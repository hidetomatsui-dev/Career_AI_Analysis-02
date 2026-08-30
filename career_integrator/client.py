"""Google Gemini API（google-genai）の呼び出しラッパ。"""

from __future__ import annotations

import os
from typing import Optional

# 既定モデル。速度優先なら CLI の --model で gemini-2.5-flash 等を指定する。
DEFAULT_MODEL = "gemini-2.5-pro"

# API キーを探す環境変数（先に見つかった方を使う）
_KEY_ENVS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


class LLMError(RuntimeError):
    pass


def resolve_api_key(explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    for name in _KEY_ENVS:
        v = os.environ.get(name)
        if v:
            return v
    return None


def call_llm(
    system_prompt: str,
    user_message: str,
    *,
    model: str = DEFAULT_MODEL,
    max_output_tokens: int = 24000,
    temperature: float = 0.7,
    thinking_budget: Optional[int] = None,
    api_key: Optional[str] = None,
) -> str:
    """統合レポート本文（Markdown 文字列）を返す。

    thinking_budget:
        None … モデル既定（動的思考）。
        0    … 思考を無効化（flash / flash-lite のみ有効。pro は最小値へ丸められる）。
        >0   … 思考トークン数の上限。
    """
    try:
        from google import genai  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise LLMError(
            "google-genai が見つかりません。`pip install -r requirements.txt` を実行してください。"
        ) from e

    key = resolve_api_key(api_key)
    if not key:
        raise LLMError(
            "GEMINI_API_KEY（または GOOGLE_API_KEY）が設定されていません。"
        )

    client = genai.Client(api_key=key)

    config: dict = {
        "system_instruction": system_prompt,
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
    }
    if thinking_budget is not None:
        config["thinking_config"] = {"thinking_budget": thinking_budget}

    try:
        resp = client.models.generate_content(
            model=model,
            contents=user_message,
            config=config,
        )
    except Exception as e:  # google-genai の例外階層はバージョン差があるため広めに捕捉
        raise LLMError(f"Gemini API 呼び出しに失敗しました: {e}") from e

    try:
        text = (resp.text or "").strip()
    except Exception:
        text = ""

    if not text:
        detail = _failure_detail(resp)
        raise LLMError(f"空の応答が返りました（{detail}）。max_output_tokens やモデル設定を確認してください。")
    return text


def _failure_detail(resp) -> str:
    parts = []
    try:
        fr = resp.candidates[0].finish_reason
        parts.append(f"finish_reason={getattr(fr, 'name', fr)}")
    except Exception:
        pass
    try:
        fb = resp.prompt_feedback
        if fb:
            parts.append(f"prompt_feedback={fb}")
    except Exception:
        pass
    return ", ".join(parts) or "詳細不明"
