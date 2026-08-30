"""システムプロンプトの読み込みと、ユーザーメッセージの組み立て。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .parsers import InterestValuesReport, TenmeiReport

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "integration_system.md"


def load_system_prompt(path: Optional[Union[str, Path]] = None) -> str:
    p = Path(path) if path else _PROMPT_PATH
    return p.read_text(encoding="utf-8")


def _bullet(label: str, value: Optional[str]) -> Optional[str]:
    return f"- {label}: {value}" if value else None


def _format_interest(iv: InterestValuesReport) -> str:
    lines = ["## 職業興味×価値観ワークショップ（抽出サマリ）"]
    candidates = [
        _bullet("氏名", iv.name),
        _bullet("作成日", iv.created_date),
    ]
    if iv.riasec_counts:
        candidates.append(
            "- RIASEC集計: "
            + "、".join(f"{k} {v}枚" for k, v in iv.riasec_counts.items())
        )
    if iv.riasec_selected:
        candidates.append("- 「興味がある」に該当したタイプ: " + "・".join(iv.riasec_selected))
    if iv.values_top3:
        for i, v in enumerate(iv.values_top3, 1):
            candidates.append(f"- 価値観 第{i}位: {v}")
    candidates += [
        _bullet("交差点を一言で", iv.intersection_phrase),
        _bullet("キャリアの方向性", iv.career_direction),
        _bullet("今日の一文まとめ", iv.one_line_summary),
    ]
    if iv.small_steps:
        candidates.append(
            "- 記入済みスモールステップ: "
            + " / ".join(iv.small_steps)
        )
    lines += [c for c in candidates if c]
    return "\n".join(lines)


def _format_tenmei(t: TenmeiReport) -> str:
    lines = ["## 四柱推命 天命レポート（抽出サマリ）"]
    candidates = [
        _bullet("お名前", t.name),
        _bullet("生年月日", t.birth_date),
        _bullet("天命タイプ", t.tenmei_type),
        _bullet("核心的な強み", t.core_strength),
        _bullet("働き方の傾向", t.work_tendency),
    ]
    if t.suited_fields:
        candidates.append("- 向いている仕事のフィールド: " + "、".join(t.suited_fields))
    candidates += [
        _bullet("やりがいの源泉", t.source_of_fulfillment),
        _bullet("自己理解への問いかけ", t.self_inquiry),
    ]
    lines += [c for c in candidates if c]
    return "\n".join(lines)


def resolve_name(
    iv: InterestValuesReport,
    tenmei: TenmeiReport,
    override: Optional[str] = None,
) -> str:
    return override or tenmei.name or iv.name or "ご本人"


def build_user_message(
    iv: InterestValuesReport,
    tenmei: TenmeiReport,
    *,
    name: str,
) -> str:
    return f"""以下は同一人物についての 2 つの自己理解レポートです。
システムプロンプトの指示に従って、両者を統合した「{name}様 キャリア統合分析レポート」を作成してください。

# 抽出サマリ
{_format_interest(iv)}

{_format_tenmei(tenmei)}

# 原文1: 職業興味×価値観ワークショップ 提出用ワークシート（全文）
<report_interest_values>
{iv.raw.strip()}
</report_interest_values>

# 原文2: お仕事占い 四柱推命 天命レポート（全文）
<report_tenmei>
{tenmei.raw.strip()}
</report_tenmei>

# 出力
「# {name}様 キャリア統合分析レポート」で始まる Markdown 本文のみを出力してください。前置き・後書き・全体を囲うコードフェンスは不要です。
"""
