# EC データ分析エージェント

自然言語で EC サイトのデータを分析する AI エージェント。
Google ADK + Gemini によるマルチエージェント構成で、Conversational Analytics Data Agent 経由で BigQuery にアクセスし、売上・顧客・商品・商戦などの問いに応答する。

## アーキテクチャ

### 技術スタック

- **Google ADK** 2.7.1 — マルチエージェント構成、Skill、Plugin、Guard
- **Gemini** — `gemini-2.5-flash-lite` (Root) / `gemini-2.5-flash` (DataAnalyst)
- **Conversational Analytics Data Agent** — 自然言語からの BigQuery 問い合わせ
- **BigQuery** — 分析対象データと行動ログの格納先
- **Model Armor** — 入出力の安全性検査 (インジェクション / RAI / 悪意ある URI / PII)
- **Python 3.12 / uv** — 実行環境と依存管理
- **ADK Web** — ローカル UI (`adk web`)

### 構成

`LlmAgent` のマルチエージェント構成。データアクセスは DataAnalyst のみが担う。

```
App (name="ec_analytics_agent")
├─ plugins                              両エージェントに適用
│  ├─ EmptyTurnRetryPlugin              常時有効。モデル失敗と空応答を検知してリトライ
│  ├─ ModelArmorPlugin                  env で有効化。before/after_model_callback で入出力を検査
│  └─ BigQueryAgentAnalyticsPlugin      env で有効化。行動ログを BigQuery に記録
└─ root_agent
   └─ ec_analytics_root                 オーケストレーター、データアクセスはしない
      ├─ model: gemini-2.5-flash-lite
      └─ sub_agents
         └─ data_analyst                ユーザー応答の主担当
            ├─ model: gemini-2.5-flash
            ├─ planner: thinking_budget=8000
            ├─ tools: DataAgentToolset, SkillToolset
            └─ before_tool_callback: [block_destructive_sql_intent, restrict_data_agent]
```

- EC データ分析以外の依頼は Root で弾き、DataAnalyst 側でも再判定する
- handoff の判断材料は各エージェントの `description` (ADK が `transfer_to_agent` の指示に埋め込む)
- 破壊的 SQL 意図と許可外の Data Agent 参照は `before_tool_callback` で遮断する
- 参照できる Data Agent は `data_agents/definitions/*.json` 由来の固定リスト。探索系ツールは公開せず、選択肢をプロンプトの表として渡して最適なものを選ばせる
- Root にも参照可能なデータの要約を渡し、handoff 可否と提案内容の根拠にする (リソース名は渡さない)
- スキルは Progressive Disclosure で段階ロードする

## エージェント品質評価

`eval/` にローカル評価一式を置く。機械的に判定できる観点はカスタムメトリクス、
判断が要る観点は LLM Judge の組み込みメトリクスで見る。
メトリクスは eval set 全体に一律で適用されるため、期待する結果が異なるケースはセットを分ける。
単体は模範解答と突き合わせ、シナリオはユーザーシミュレーターが対話を生成する。

```bash
make eval
```

| eval set | ケース | シミュレーター |
|---|---|---|
| `normal` | 通常の分析依頼 | なし |
| `abnormal_pii` | PII を含む入力 (Model Armor でのブロックを期待する) | なし |
| `abnormal_injection` | プロンプトインジェクション (エージェント自身の拒否を期待する) | なし |
| `scenario_quality` | 深掘りを重ねる分析 | あり |
| `scenario_conversation` | 曖昧な依頼からの要件明確化 | あり |

| eval set | 観点 | メトリクス | 種別 | rubrics |
|---|---|---|---|---|
| `normal` | 数値の正確性 | `numeric_accuracy` | カスタム | - |
| `normal` | 模範解答との一致 | `final_response_match_v2` | 組み込み (LLM Judge) | - |
| `normal` | ハルシネーション | `hallucinations_v1` | 組み込み (LLM Judge) | - |
| `normal` | スキルのロード | `skill_usage` | カスタム | - |
| `normal` | ツール呼び出しの実行 | `tool_call_integrity` | カスタム | - |
| `normal` | 空応答の検知 | `agent_completion` | カスタム | - |
| `abnormal_pii` | Model Armor の PII 検出 | `pii_guard` | カスタム | - |
| `abnormal_injection` | プロンプトインジェクション耐性 | `injection_guard` | カスタム | - |
| `abnormal_injection` | システムプロンプトの漏洩 | `prompt_leak_guard` | カスタム | - |
| `scenario_quality` | 回答品質 (9 項目) | `rubric_based_final_response_quality_v1` | 組み込み (LLM Judge) | ✅ |
| `scenario_quality` | ツール利用 (2 項目) | `rubric_based_tool_use_quality_v1` | 組み込み (LLM Judge) | ✅ |
| `scenario_quality` | 空応答の検知 | `agent_completion` | カスタム | - |
| `scenario_quality` | スキルのロード | `skill_usage` | カスタム | - |
| `scenario_quality` | ツール呼び出しの実行 | `tool_call_integrity` | カスタム | - |
| `scenario_conversation` | タスク達成 | `multi_turn_task_success_v1` | 組み込み (LLM Judge) | - |
| `scenario_conversation` | 軌跡品質 | `multi_turn_trajectory_quality_v1` | 組み込み (LLM Judge) | - |
| `scenario_conversation` | ツール利用 (3 項目) | `rubric_based_tool_use_quality_v1` | 組み込み (LLM Judge) | ✅ |
| `scenario_conversation` | シミュレーターの忠実性 | `per_turn_user_simulator_quality_v1` | 組み込み (LLM Judge) | - |
| `scenario_conversation` | 空応答の検知 | `agent_completion` | カスタム | - |
| `scenario_conversation` | ツール呼び出しの実行 | `tool_call_integrity` | カスタム | - |

## セットアップ

Python 3.12 / uv 管理、venv = `.venv`。ADK は `google-adk[bigquery-analytics]==2.7.1` にピン留め。

### 1. GCP プロジェクトと API

```bash
gcloud config set project <project_id>
gcloud services enable \
  geminidataanalytics.googleapis.com \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  modelarmor.googleapis.com
```

### 2. 認証

```bash
gcloud auth login --update-adc
```

エージェントは `google.auth.default()` で ADC を読むため、初回は `--update-adc` が必要。
ADC は一度作れば残るので、2 回目以降は `gcloud auth login` だけでよい。

必要なロール:

| ロール | 用途 |
|---|---|
| `roles/geminidataanalytics.dataAgentUser` | エージェントが Data Agent を一覧・参照し、チャットする |
| `roles/geminidataanalytics.dataAgentCreator` | `make deploy-data-agent` で Data Agent を新規作成する |
| `roles/geminidataanalytics.dataAgentEditor` | 既存 Data Agent を更新する (再デプロイ時) |
| `roles/bigquery.dataViewer` | Data Agent が参照する分析対象テーブルを読む |
| `roles/bigquery.jobUser` | BigQuery のクエリジョブを実行する |
| `roles/aiplatform.user` | Gemini を呼び出す |
| `roles/bigquery.dataEditor` | 行動ログを有効化する場合のみ (テーブル作成・書き込み) |
| `roles/modelarmor.user` | Model Armor を有効化する場合のみ (sanitize 呼び出し) |
| `roles/modelarmor.admin` | `make deploy-model-armor` でテンプレートを作成・更新する |

デプロイしない場合は `dataAgentCreator` / `dataAgentEditor` は不要。

### 3. 分析対象データと Data Agent

分析対象は [dbt-labs/jaffle-shop](https://github.com/dbt-labs/jaffle-shop) のテストデータ。
clone して BigQuery (us-central1) に `jaffle_shop` データセットを作る。

```bash
git clone https://github.com/dbt-labs/jaffle-shop && cd jaffle-shop
# profiles.yml で project/dataset=jaffle_shop/location=us-central1 を設定
dbt seed --vars 'load_source_data: true'
dbt build
```

作成した mart テーブル (orders / order_items / customers / products / locations / supplies) を
参照する Data Agent をデプロイする。

```bash
make deploy-data-agent
```

別のデータセットを使う場合は `data_agents/definitions/` に定義ファイルを追加する (ファイル名 = データセット名)。

### 4. Model Armor テンプレート

```bash
make deploy-model-armor
```

### 5. 行動ログのデータセット

プラグインはデータセットを作らないため事前に用意する (テーブルとスキーマは自動作成)。

```bash
make deploy-analytics-dataset
```

### 6. env var

```bash
cp .env.example .env
```

`EmptyTurnRetryPlugin` は常時有効 (設定不要)。残り 2 つは既定で無効で、`.env` に値を入れると有効になる。

| env var | 値 |
|---|---|
| `MODEL_ARMOR_TEMPLATE` | `ec-analytics` (手順 4 で作成したテンプレート ID) |
| `AGENT_ANALYTICS_DATASET` | `ec_analytics_agent_logs` (手順 5 で作成したデータセット ID) |

### 7. 起動

```bash
make web
```

### 動作確認のプロンプト

jaffle-shop テストデータ (2024-09-01 〜 2025-08-31 / 注文 61,948 件 / 顧客 935 人 / Philadelphia・Brooklyn の 2 店舗) 向けの例。

```
どんな分析ができるの？
月次の売上推移を教えて
Philadelphia と Brooklyn の売上を比較して
売上トップ5の商品は？
フードとドリンクの売上構成比は？
リピート顧客の割合と、初回購入から2回目までの傾向を教えて
売上が落ち込んだ月を特定して、原因を商品別に分解して
```
