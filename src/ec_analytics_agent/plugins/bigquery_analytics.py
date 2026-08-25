"""行動ログを BigQuery に記録する `BigQueryAgentAnalyticsPlugin` の組み立て

env var と事前準備は README を参照。データセットはプラグインが作らないため事前に用意する。
"""

import logging
import os

import google.auth
from google.adk.plugins.bigquery_agent_analytics_plugin import (
    BigQueryAgentAnalyticsPlugin,
    BigQueryLoggerConfig,
)

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
DEFAULT_LOCATION = "us-central1"
DEFAULT_TABLE_ID = "agent_events"


def env_bool(key: str, default: bool = False) -> bool:
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def build_bigquery_analytics_plugin() -> BigQueryAgentAnalyticsPlugin | None:
    """AGENT_ANALYTICS_DATASET が設定されていればプラグインを返す。未設定なら None"""
    dataset_id = os.environ.get("AGENT_ANALYTICS_DATASET")
    if not dataset_id:
        logger.info("AGENT_ANALYTICS_DATASET が未設定のため、行動ログの BigQuery 記録は無効です。")
        return None

    credentials, adc_project = google.auth.default(scopes=SCOPES)
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or adc_project
    if not project_id:
        raise ValueError("GCP project ID を解決できません。GOOGLE_CLOUD_PROJECT または ADC を確認してください。")

    config = BigQueryLoggerConfig(
        table_id=os.environ.get("AGENT_ANALYTICS_TABLE", DEFAULT_TABLE_ID),
        exactly_once_delivery=env_bool("AGENT_ANALYTICS_EXACTLY_ONCE"),
        create_views=False,
        custom_tags={"app": "ec-analytics"},
    )

    logger.info("行動ログを BigQuery に記録します: %s.%s.%s", project_id, dataset_id, config.table_id)
    return BigQueryAgentAnalyticsPlugin(
        project_id=project_id,
        dataset_id=dataset_id,
        location=os.environ.get("AGENT_ANALYTICS_LOCATION", DEFAULT_LOCATION),
        credentials=credentials,
        config=config,
    )
