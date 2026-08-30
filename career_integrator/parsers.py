"""2種類のレポート（テキスト）から構造化サマリを抽出するパーサ。

原文全体はそのまま LLM に渡すので、ここでの抽出は
「決定的に扱えるヘッダ情報」と「軽い検証・宛名決定」のための補助。
項目が取れなくても None のまま先へ進む（例外で止めない）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# 罫線だけの行（━ ═ ─ * - = などの連続）
_RULE_RE = re.compile(r"^\s*[━═─—―*=\-]{3,}\s*$")


def _is_header(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith(("【", "■")):
        return True
    return bool(_RULE_RE.match(line))


def _section(text: str, needle: str, *, to_eof: bool = False) -> List[str]:
    """`needle` を含む最初の行の次行から、次のヘッダ（to_eof の場合は EOF）までの行。

    先頭・末尾の空行と罫線行はトリムして返す。
    """
    out: List[str] = []
    capturing = False
    for line in text.splitlines():
        if not capturing:
            if needle in line:
                capturing = True
            continue
        if not to_eof and _is_header(line):
            break
        out.append(line)
    while out and (not out[0].strip() or _RULE_RE.match(out[0])):
        out.pop(0)
    while out and (not out[-1].strip() or _RULE_RE.match(out[-1])):
        out.pop()
    return out


def _first_line(text: str, needle: str) -> Optional[str]:
    for line in _section(text, needle):
        if line.strip():
            return line.strip()
    return None


def _search(pattern: str, text: str, group: int = 1) -> Optional[str]:
    m = re.search(pattern, text)
    return m.group(group).strip() if m else None


# --------------------------------------------------------------------------- #
# 職業興味×価値観ワークショップ
# --------------------------------------------------------------------------- #
@dataclass
class InterestValuesReport:
    raw: str
    name: Optional[str] = None
    created_date: Optional[str] = None
    riasec_counts: "dict[str, int]" = field(default_factory=dict)   # {"I型": 6, ...}
    riasec_selected: List[str] = field(default_factory=list)        # ["I型", "A型", "E型"]
    values_top3: List[str] = field(default_factory=list)            # ["美しさ（...）", ...]
    intersection_phrase: Optional[str] = None                       # 交差点を一言で
    career_direction: Optional[str] = None                          # キャリアの方向性
    one_line_summary: Optional[str] = None                          # 今日の一文まとめ
    small_steps: List[str] = field(default_factory=list)            # Action 1..3
    ai_analysis: Optional[str] = None                               # 【AI キャリア分析】本文


def parse_interest_values_report(raw: str) -> InterestValuesReport:
    r = InterestValuesReport(raw=raw)

    r.name = _search(r"氏名[：:]\s*([^\s　]+)", raw)
    r.created_date = _search(r"作成日[：:]\s*([0-9/年月日.\-]+)", raw)

    for line in _section(raw, "職業興味のタイプ集計"):
        m = re.search(
            r"\[(.)\]\s*[^（(]*[（(]\s*([RIASEC]型)\s*[）)]\s*[：:]\s*(\d+)", line
        )
        if not m:
            continue
        mark, typ, cnt = m.group(1).strip(), m.group(2), int(m.group(3))
        r.riasec_counts[typ] = cnt
        if mark in ("✓", "x", "X", "☑", "■", "●", "*") or cnt > 0:
            if typ not in r.riasec_selected:
                r.riasec_selected.append(typ)

    for line in _section(raw, "選択した価値観TOP3"):
        m = re.match(
            r"\s*\[(?:★\s*)?(?:TOP\s*1|第\s*[1-3１-３]\s*位)\]\s*(.+?)\s*$", line
        )
        if m:
            r.values_top3.append(m.group(1).strip())

    r.intersection_phrase = _first_line(raw, "交差点を一言で")
    r.career_direction = _first_line(raw, "キャリアの方向性")
    r.one_line_summary = _first_line(raw, "今日の一文まとめ")

    for line in _section(raw, "スモールステップ"):
        m = re.search(r"Action\s*\d+\s*[：:]\s*(.+)", line)
        if m:
            r.small_steps.append(m.group(1).strip())

    ai = (
        _section(raw, "【AI キャリア分析】", to_eof=True)
        or _section(raw, "AI キャリア分析", to_eof=True)
        or _section(raw, "AIキャリア分析", to_eof=True)
    )
    r.ai_analysis = "\n".join(ai).strip() or None

    return r


# --------------------------------------------------------------------------- #
# 四柱推命 天命レポート
# --------------------------------------------------------------------------- #
@dataclass
class TenmeiReport:
    raw: str
    name: Optional[str] = None
    birth_date: Optional[str] = None
    tenmei_type: Optional[str] = None                 # 天命タイプ
    core_strength: Optional[str] = None               # 核心的な強み
    work_tendency: Optional[str] = None               # 働き方の傾向
    suited_fields: List[str] = field(default_factory=list)  # 向いている仕事のフィールド
    source_of_fulfillment: Optional[str] = None       # やりがいの源泉
    self_inquiry: Optional[str] = None                # 自己理解への問いかけ


def parse_tenmei_report(raw: str) -> TenmeiReport:
    r = TenmeiReport(raw=raw)

    r.name = _search(r"お?名前[：:]\s*(.+)", raw)
    r.birth_date = _search(r"生年月日[：:]\s*(.+)", raw)
    r.tenmei_type = _first_line(raw, "【天命タイプ】")
    r.core_strength = _first_line(raw, "【核心的な強み】")

    wt = [l.strip() for l in _section(raw, "【働き方の傾向】") if l.strip()]
    r.work_tendency = " ".join(wt) or None

    for line in _section(raw, "【向いている仕事のフィールド】"):
        m = re.match(r"\s*\d+\s*[.．、)]\s*(.+)", line)
        if m:
            r.suited_fields.append(m.group(1).strip())

    r.source_of_fulfillment = _first_line(raw, "【やりがいの源泉】")
    r.self_inquiry = _first_line(raw, "【自己理解への問いかけ】")

    return r
