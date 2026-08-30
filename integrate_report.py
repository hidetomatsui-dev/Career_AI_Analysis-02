#!/usr/bin/env python3
"""職業興味×価値観レポート × 四柱推命 天命レポート → キャリア統合分析レポート。

使用例:
    export GEMINI_API_KEY=...        # または GOOGLE_API_KEY
    python integrate_report.py \\
        -i samples/interest_values_report.txt \\
        -t samples/tenmei_report.txt \\
        -o out/hideto_integrated.md

    # API を呼ばずに、組み立てたプロンプトと抽出サマリだけ確認
    python integrate_report.py -i ... -t ... --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from career_integrator.client import DEFAULT_MODEL, LLMError, call_llm
from career_integrator.parsers import (
    parse_interest_values_report,
    parse_tenmei_report,
)
from career_integrator.prompt import (
    build_user_message,
    load_system_prompt,
    resolve_name,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="integrate_report.py",
        description="職業興味×価値観レポートと四柱推命 天命レポートを統合し、キャリア統合分析レポートを生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("-i", "--interest", required=True, type=Path,
                   help="職業興味×価値観ワークショップ 提出用ワークシートのテキストファイル")
    p.add_argument("-t", "--tenmei", required=True, type=Path,
                   help="四柱推命 天命レポートのテキストファイル")
    p.add_argument("-o", "--output", type=Path,
                   help="出力 Markdown ファイル（省略時は標準出力）")
    p.add_argument("--name",
                   help="宛名（省略時: 天命レポート → ワークシート の順に氏名を採用）")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"使用する Gemini モデル（既定: {DEFAULT_MODEL}／速度優先なら gemini-2.5-flash）")
    p.add_argument("--temperature", type=float, default=0.7,
                   help="生成の temperature（既定: 0.7）")
    p.add_argument("--max-output-tokens", type=int, default=24000,
                   help="応答の最大トークン数（思考トークン込み。既定: 24000）")
    p.add_argument("--thinking-budget", type=int, default=None,
                   help="思考トークン上限。0 で思考オフ（flash 系のみ）。省略時はモデル既定")
    p.add_argument("--system-prompt", type=Path,
                   help="システムプロンプトの差し替えファイル（既定: career_integrator/integration_system.md）")
    p.add_argument("--dry-run", action="store_true",
                   help="API を呼ばず、抽出サマリと組み立てたプロンプトを表示して終了")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    for label, f in (("--interest", args.interest), ("--tenmei", args.tenmei)):
        if not f.is_file():
            print(f"エラー: {label} のファイルが見つかりません: {f}", file=sys.stderr)
            return 2

    iv = parse_interest_values_report(args.interest.read_text(encoding="utf-8"))
    tenmei = parse_tenmei_report(args.tenmei.read_text(encoding="utf-8"))
    name = resolve_name(iv, tenmei, args.name)

    try:
        system_prompt = load_system_prompt(args.system_prompt)
    except OSError as e:
        print(f"エラー: システムプロンプトを読めません: {e}", file=sys.stderr)
        return 2

    user_message = build_user_message(iv, tenmei, name=name)

    if args.dry_run:
        print(f"# 宛名: {name}様\n")
        print(f"# モデル: {args.model} / temperature={args.temperature} / "
              f"max_output_tokens={args.max_output_tokens} / thinking_budget={args.thinking_budget}\n")
        print("=" * 60)
        print("SYSTEM PROMPT")
        print("=" * 60)
        print(system_prompt)
        print("\n" + "=" * 60)
        print("USER MESSAGE")
        print("=" * 60)
        print(user_message)
        return 0

    try:
        report = call_llm(
            system_prompt,
            user_message,
            model=args.model,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            thinking_budget=args.thinking_budget,
        )
    except LLMError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.rstrip() + "\n", encoding="utf-8")
        print(f"書き出しました: {args.output}", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
