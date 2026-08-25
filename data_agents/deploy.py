"""Conversational Analytics Data Agent のデプロイ CLI

Usage:
    GOOGLE_CLOUD_PROJECT=<project_id> python data_agents/deploy.py [name ...]

definitions/*.json を順に upsert する。引数でファイル名 (拡張子なし) を指定すると対象を絞れる。
ファイル名が参照先データセット名と Data Agent ID を兼ねる (jaffle_shop.json -> ec-analytics-jaffle-shop)。
project_id は GOOGLE_CLOUD_PROJECT env var を最優先で解決し、なければ ADC から取得する。
"""

import logging
import os
import sys
from pathlib import Path
from string import Template

import google.auth
from google.api_core import exceptions
from google.cloud import geminidataanalytics
from google.protobuf import field_mask_pb2

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"
# Conversational Analytics の Data Agent は global のみ対応 (他リージョンは 403)
LOCATION = "global"
AGENT_ID_PREFIX = "ec-analytics"
UPDATE_MASK_PATHS = ["display_name", "description", "data_analytics_agent"]


def agent_id(definition: Path) -> str:
    return f"{AGENT_ID_PREFIX}-{definition.stem.replace('_', '-').lower()}"


def upsert(
    client: geminidataanalytics.DataAgentServiceClient,
    definition: Path,
    project_id: str,
) -> str:
    body_json = Template(definition.read_text()).safe_substitute(
        PROJECT_ID=project_id,
        DATASET_ID=definition.stem,
    )
    data_agent = geminidataanalytics.DataAgent.from_json(body_json)

    parent = f"projects/{project_id}/locations/{LOCATION}"
    name = f"{parent}/dataAgents/{agent_id(definition)}"
    try:
        client.get_data_agent(name=name)
    except exceptions.NotFound:
        logger.info("作成: %s", name)
        result = client.create_data_agent_sync(parent=parent, data_agent_id=agent_id(definition), data_agent=data_agent)
    else:
        logger.info("更新: %s", name)
        data_agent.name = name
        result = client.update_data_agent_sync(
            data_agent=data_agent,
            update_mask=field_mask_pb2.FieldMask(paths=UPDATE_MASK_PATHS),
        )
    return result.name


def resolve_definitions(names: list[str]) -> list[Path]:
    if not names:
        return sorted(DEFINITIONS_DIR.glob("*.json"))
    definitions = []
    for name in names:
        path = DEFINITIONS_DIR / f"{Path(name).stem}.json"
        if not path.is_file():
            logger.error("定義ファイルが見つかりません: %s", path)
            sys.exit(1)
        definitions.append(path)
    return definitions


def main() -> None:
    credentials, adc_project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or adc_project
    if not project_id:
        logger.error("GCP project ID を解決できません。GOOGLE_CLOUD_PROJECT または ADC を確認してください")
        sys.exit(1)

    definitions = resolve_definitions(sys.argv[1:])
    if not definitions:
        logger.error("定義ファイルがありません: %s", DEFINITIONS_DIR)
        sys.exit(1)

    client = geminidataanalytics.DataAgentServiceClient(credentials=credentials)
    for definition in definitions:
        logger.info("デプロイ中: %s (dataset=%s)", definition.name, definition.stem)
        logger.info("完了: %s", upsert(client, definition, project_id))


if __name__ == "__main__":
    main()
