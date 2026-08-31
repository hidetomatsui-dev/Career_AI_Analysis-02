# 職業興味×価値観 × 四柱推命　統合レポート生成ツール

2 つの自己理解レポートを 1 本の「キャリア統合分析レポート」に統合します。**CLI** と **Web（Vercel）** の 2 つの使い方があります。

- **入力1**：職業興味×価値観ワークショップ 提出用ワークシート（RIASEC の職業興味タイプ集計＋価値観 TOP3＋統合マトリクス＋末尾の AI キャリア分析）
- **入力2**：お仕事占い 四柱推命 天命レポート（天命タイプ／核心的な強み／働き方の傾向／向いている仕事のフィールド ほか）
- **出力**：両者を突き合わせた統合レポート（Markdown）。構成の見本は [`samples/integrated_report.sample.md`](samples/integrated_report.sample.md)。

## 仕組み

```
career_integrator/                    … 統合ロジック（CLI と Web で共有）
  ├─ parsers.py             … 2つのレポート原文から構造化サマリを抽出（氏名・RIASEC集計・価値観TOP3・天命タイプ など）
  ├─ prompt.py              … integration_system.md ＋ 抽出サマリ ＋ 原文全文 でリクエストを組み立て
  ├─ client.py              … Google Gemini API (google-genai) を呼び出し、統合レポート本文を取得
  ├─ service.py             … 入力検証・モード選択・LLM呼び出し（Web から使う共通処理）
  └─ integration_system.md  … 統合ロジック本体（セクション構成・トーン・禁止事項）。ここを編集すれば出力が変わる
integrate_report.py                   … CLI エントリポイント
app.py                                … Web エントリポイント（WSGI）。静的配信 ＋ POST /api/integrate
public/index.html                     … Web フロントエンド（2レポートを貼り付け→統合レポート表示）
pyproject.toml                        … 依存とVercelエントリポイント（[tool.vercel] entrypoint = "app:app"）
vercel.json                           … maxDuration 60s / バンドル除外
```

原文は**全文をそのままモデルに渡す**（切り詰めない）。パーサは宛名決定と抽出サマリ提示のための補助で、項目が取れなくても処理は止まりません。

## セットアップ

```bash
cd "職業興味×価値観×四柱推命"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=...        # Google AI Studio で取得（GOOGLE_API_KEY でも可）
```

> Python 3.9 以上。LLM は Google Gemini（`google-genai`）を使用します。

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
| `--model` | `gemini-2.5-pro` | 使用する Gemini モデル。速度優先なら `gemini-2.5-flash` |
| `--temperature` | `0.7` | 生成の temperature |
| `--max-output-tokens` | `24000` | 応答の最大トークン数（思考トークン込み） |
| `--thinking-budget` | （モデル既定） | 思考トークン上限。`0` で思考オフ（`flash` 系のみ） |
| `--system-prompt` | `career_integrator/integration_system.md` | システムプロンプトの差し替え |
| `--dry-run` | off | API を呼ばずプロンプトを表示 |

## 入力フォーマットについて

パーサは各レポートの見出し記号（`【…】` `■` と罫線）を頼りに次を抽出します。

- 興味×価値観：`氏名` / `作成日` / `職業興味のタイプ集計`（`[✓] 研究的（I型）: 6枚` 形式）/ `選択した価値観TOP3`（`[★ TOP1]` `[第2位]` `[第3位]`）/ `交差点を一言で` / `キャリアの方向性` / `今日の一文まとめ` / `スモールステップ` の Action / `【AI キャリア分析】` 本文
- 天命：`お名前` / `生年月日` / `【天命タイプ】` / `【核心的な強み】` / `【働き方の傾向】` / `【向いている仕事のフィールド】`（番号付きリスト）/ `【やりがいの源泉】` / `【自己理解への問いかけ】`

多少表記が違っても原文全文はモデルに渡るため破綻しません。抽出結果は `--dry-run` で確認できます。

## Web でデプロイ（Vercel）

Vercel の **Python ランタイム**（WSGI エントリポイント）で動きます。`app.py` の `app` が全リクエストを処理し、
`/` は `public/` の静的ファイル、`POST /api/integrate` が統合 API です。
エントリポイントは `pyproject.toml` の `[tool.vercel] entrypoint = "app:app"` で明示しています。

### 1. プロジェクトを接続

- **ダッシュボード**: [vercel.com/new](https://vercel.com/new) で GitHub リポジトリ `hidetomatsui-dev/Career_AI_Analysis-02` を Import。Root Directory は既定のまま（Framework Preset は自動判定で可）。
- **CLI**: リポジトリ直下で
  ```bash
  npx vercel        # 初回：プロジェクト作成＋プレビューデプロイ
  npx vercel --prod # 本番デプロイ
  ```

### 2. 環境変数を設定（必須）

Vercel の Project → Settings → Environment Variables に追加（Production / Preview 両方）:

| Name | Value |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio で取得した API キー（`GOOGLE_API_KEY` でも可） |

設定後、Deployments から Redeploy すると反映されます。

### 3. 動作

- `/` … 入力フォーム（`public/index.html`）。2 レポートを貼り付けて生成する。
- `POST /api/integrate` … `{ interest, tenmei, name?, mode?, model? }` を受け取り `{ report }` を返す。
  - `mode: "fast"`（既定）… `gemini-2.5-flash`。目安 15〜35 秒。
  - `mode: "deep"` … `gemini-2.5-pro`。高精度だが Hobby プランの 60 秒上限で失敗することあり（その場合は Pro で `vercel.json` の `maxDuration` を延長）。

> ローカル確認:
> - 依存なしの簡易サーバ … `GEMINI_API_KEY=... python app.py` → http://localhost:8000
> - 本番同等 … `npx vercel dev`（`GEMINI_API_KEY` を `.env` か環境変数で渡す）

## テスト

```bash
python -m unittest discover -s tests -v
```
