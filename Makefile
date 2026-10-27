.PHONY: help web eval deploy-data-agent deploy-model-armor deploy-analytics-dataset

UV     ?= uv
ADK    ?= $(UV) run adk
PYTHON ?= $(UV) run python

# ADK 内部由来の実験的機能・非推奨の警告を抑止する
export ADK_SUPPRESS_EXPERIMENTAL_FEATURE_WARNINGS := 1
export PYTHONWARNINGS := ignore::UserWarning:google.adk.dependencies.vertexai

# gemini-3.8-flash は us-central1 に無く、eval の judge (gemini-2.5-*) は us に無い。両方が動くのは global だけ。
# ADK はシェルの env を .env より優先するため、.env ではなくここで上書きする
export GOOGLE_CLOUD_LOCATION := global

# 行動ログの保存先。GOOGLE_CLOUD_PROJECT 未設定なら gcloud config から解決する
PROJECT_ID       ?= $(or $(GOOGLE_CLOUD_PROJECT),$(shell gcloud config get-value project 2>/dev/null))
ANALYTICS_DATASET ?= ec_analytics_agent_logs
ANALYTICS_LOCATION ?= us-central1

# 評価結果の同期先 (gs://<bucket>)。ローカルに書き出した後で <bucket>/evals/ に同期する
EVAL_STORAGE_URI ?=

help:  ## 利用可能なターゲットを表示
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

web:  ## ADK Dev UI をローカル起動
	$(UV) sync
	$(ADK) web src

deploy-data-agent:  ## Conversational Analytics Data Agent をデプロイ (要 ADC)
	$(UV) sync
	$(PYTHON) data_agents/deploy.py

deploy-model-armor:  ## Model Armor テンプレートをデプロイ (要 ADC)
	$(UV) sync
	$(PYTHON) model_armor/deploy.py

eval:  ## ローカル評価を実行 (要 ADC, MODEL_ARMOR_TEMPLATE)
	$(UV) sync
	@# キャッシュ適用時は system_instruction が None になり AgentDetails を組み立てられない
	$(eval export ADK_DISABLE_CONTEXT_CACHE := 1)
	@for name in normal abnormal_pii abnormal_injection scenario_quality scenario_conversation; do \
		echo "--- $$name ---"; \
		$(ADK) eval src/ec_analytics_agent eval/evalsets/$$name.json \
		  --config_file_path eval/configs/$$name.json || exit 1; \
	done
	$(if $(EVAL_STORAGE_URI),gcloud storage rsync src/ec_analytics_agent/.adk/eval_history \
	  $(EVAL_STORAGE_URI)/evals)

deploy-analytics-dataset:  ## 行動ログ用の BigQuery データセットを作成 (要 ADC)
	@bq --project_id=$(PROJECT_ID) show --dataset $(PROJECT_ID):$(ANALYTICS_DATASET) >/dev/null 2>&1 \
	  && echo "既存: $(PROJECT_ID):$(ANALYTICS_DATASET)" \
	  || bq --project_id=$(PROJECT_ID) --location=$(ANALYTICS_LOCATION) mk --dataset \
	       --description="ADK エージェントの行動ログ" $(PROJECT_ID):$(ANALYTICS_DATASET)
