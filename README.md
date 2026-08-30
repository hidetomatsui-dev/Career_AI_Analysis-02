# 職業興味×価値観 × 四柱推命　統合レポート生成ツール

2 つの自己理解レポートを 1 本の「キャリア統合分析レポート」に統合する CLI ツールです。

- **入力1**：職業興味×価値観ワークショップ 提出用ワークシート（RIASEC の職業興味タイプ集計＋価値観 TOP3＋統合マトリクス＋末尾の AI キャリア分析）
- **入力2**：お仕事占い 四柱推命 天命レポート（天命タイプ／核心的な強み／働き方の傾向／向いている仕事のフィールド ほか）
- **出力**：両者を突き合わせた統合レポート（Markdown）。構成の見本は [`samples/integrated_report.sample.md`](samples/integrated_report.sample.md)。

## 仕組み

```
integrate_report.py
  └─ career_integrator/
       ├─ parsers.py  … 2つのレポート原文から構造化サマリを抽出（氏名・RIASEC集計・価値観TOP3・天命タイプ など）
       ├─ prompt.py   … prompts/integration_system.md ＋ 抽出サマリ ＋ 原文全文 で Claude へのリクエストを組み立て
       └─ client.py   … Claude (Anthropic Messages API) を呼び出し、統合レポート本文を取得
  prompts/integration_system.md … 統合ロジック本体（セクション構成・トーン・禁止事項）。ここを編集すれば出力が変わる
```

原文は**全文をそのままモデルに渡す**（切り詰めない）。パーサは宛名決定と抽出サマリ提示のための補助で、項目が取れなくても処理は止まりません。

## セットアップ

```bash
cd "職業興味×価値観×四柱推命"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...        # または `ant auth login`
```

> Python 3.10 以上を推奨（`anthropic` 1.x の要件）。

## 使い方

```bash
# 統合レポートを生成してファイルに書き出す
python integrate_report.py \
  -i samples/interest_values_report.txt \
  -t samples/tenmei_report.txt \
  -o out/hideto_integrated.md

# 標準出力に出す
python integrate_report.py -i A.txt -t B.txt

# API を呼ばずに、抽出サマリと組み立てたプロンプトだけ確認（無料・オフライン）
python integrate_report.py -i samples/interest_values_report.txt -t samples/tenmei_report.txt --dry-run
```

### オプション

| オプション | 既定 | 説明 |
|---|---|---|
| `-i, --interest` | （必須） | 職業興味×価値観レポートのテキストファイル |
| `-t, --tenmei` | （必須） | 四柱推命 天命レポートのテキストファイル |
| `-o, --output` | 標準出力 | 出力 Markdown ファイル |
| `--name` | 天命→興味の順に氏名採用 | レポートの宛名（「〇〇様」の〇〇） |
| `--model` | `claude-opus-5` | 使用する Claude モデル。コスト優先なら `claude-sonnet-5` |
| `--effort` | `high` | 推論の effort（`low`〜`max`） |
| `--max-tokens` | `16000` | 応答の最大トークン数 |
| `--system-prompt` | `prompts/integration_system.md` | システムプロンプトの差し替え |
| `--dry-run` | off | API を呼ばずプロンプトを表示 |

## 入力フォーマットについて

パーサは各レポートの見出し記号（`【…】` `■` と罫線）を頼りに次を抽出します。

- 興味×価値観：`氏名` / `作成日` / `職業興味のタイプ集計`（`[✓] 研究的（I型）: 6枚` 形式）/ `選択した価値観TOP3`（`[★ TOP1]` `[第2位]` `[第3位]`）/ `交差点を一言で` / `キャリアの方向性` / `今日の一文まとめ` / `スモールステップ` の Action / `【AI キャリア分析】` 本文
- 天命：`お名前` / `生年月日` / `【天命タイプ】` / `【核心的な強み】` / `【働き方の傾向】` / `【向いている仕事のフィールド】`（番号付きリスト）/ `【やりがいの源泉】` / `【自己理解への問いかけ】`

多少表記が違っても原文全文はモデルに渡るため破綻しません。抽出結果は `--dry-run` で確認できます。

## テスト

```bash
python -m unittest discover -s tests -v
```
