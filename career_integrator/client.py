"""Claude (Anthropic Messages API) の呼び出しラッパ。"""

from __future__ import annotations

from typing import Optional

# 既定モデル。コスト優先で下げたい場合は CLI の --model で claude-sonnet-5 等を指定する。
DEFAULT_MODEL = "claude-opus-5"


class ClaudeError(RuntimeError):
    pass


def call_claude(
    system_prompt: str,
    user_message: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 16000,
    effort: str = "high",
    api_key: Optional[str] = None,
) -> str:
    """統合レポート本文（Markdown 文字列）を返す。"""
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise ClaudeError(
            "anthropic パッケージが見つかりません。`pip install -r requirements.txt` を実行してください。"
        ) from e

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
    )

    try:
        try:
            message = _stream_final(client, kwargs)
        except TypeError:
            # 新しめのサーバパラメータを受け付けない古い SDK 向けのフォールバック
            extra = {}
            for k in ("output_config", "thinking"):
                if k in kwargs:
                    extra[k] = kwargs.pop(k)
            kwargs["extra_body"] = extra
            message = _stream_final(client, kwargs)
    except anthropic.AuthenticationError as e:  # type: ignore[attr-defined]
        raise ClaudeError("認証に失敗しました。ANTHROPIC_API_KEY を確認してください。") from e
    except anthropic.APIStatusError as e:  # type: ignore[attr-defined]
        raise ClaudeError(f"API エラー ({getattr(e, 'status_code', '?')}): {getattr(e, 'message', e)}") from e
    except anthropic.APIConnectionError as e:  # type: ignore[attr-defined]
        raise ClaudeError("ネットワークエラー: 接続を確認してください。") from e

    if getattr(message, "stop_reason", None) == "refusal":
        raise ClaudeError(f"モデルが生成を拒否しました: {getattr(message, 'stop_details', None)}")

    text = "\n".join(
        block.text for block in message.content
        if getattr(block, "type", None) == "text" and getattr(block, "text", "")
    ).strip()

    if not text:
        raise ClaudeError("空の応答が返りました。max_tokens やモデル設定を確認してください。")
    return text


def _stream_final(client, kwargs):
    with client.messages.stream(**kwargs) as stream:
        return stream.get_final_message()
