.PHONY: help web eval deploy-data-agent deploy-model-armor deploy-analytics-dataset

UV     ?= uv
ADK    ?= $(UV) run adk
PYTHON ?= $(UV) run python

# ADK 内部由来の実験的機能・非推奨の警告を抑止する
export ADK_SUPPRESS_EXPERIMENTAL_FEATURE_WARNINGS := 1
export PYTHONWARNINGS := ignore::UserWarning:google.adk.dependencies.vertexai

# 行動ログの保存先。GOOGLE_CLOUD_PROJECT 未設定なら gcloud config から解決する
PROJECT_ID       ?= $(or $(GOOGLE_CLOUD_PROJECT),$(shell gcloud config get-value project 2>/dev/null))
ANALYTICS_DATASET ?= ec_analytics_agent_logs
ANALYTICS_LOCATION ?= us-central1

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
	@for name in normal abnormal scenario_quality scenario_conversation; do \
		echo "--- $$name ---"; \
		$(ADK) eval src/ec_analytics_agent eval/evalsets/$$name.json \
		  --config_file_path eval/configs/$$name.json || exit 1; \
	done

deploy-analytics-dataset:  ## 行動ログ用の BigQuery データセットを作成 (要 ADC)
	@bq --project_id=$(PROJECT_ID) show --dataset $(PROJECT_ID):$(ANALYTICS_DATASET) >/dev/null 2>&1 \
	  && echo "既存: $(PROJECT_ID):$(ANALYTICS_DATASET)" \
	  || bq --project_id=$(PROJECT_ID) --location=$(ANALYTICS_LOCATION) mk --dataset \
	       --description="ADK エージェントの行動ログ" $(PROJECT_ID):$(ANALYTICS_DATASET)
