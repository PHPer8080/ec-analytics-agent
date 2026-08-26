# Usage: GOOGLE_CLOUD_PROJECT=<project_id> python model_armor/deploy.py [name ...]
# ファイル名がテンプレート ID を兼ねる (ec_analytics.json -> ec-analytics)

import json
import logging
import os
import sys
from pathlib import Path

import google.auth
from google.auth.transport.requests import AuthorizedSession

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"
DEFAULT_LOCATION = "us-central1"
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def template_id(definition: Path) -> str:
    return definition.stem.replace("_", "-").lower()


def upsert(session: AuthorizedSession, definition: Path, project_id: str, location: str) -> str:
    endpoint = f"https://modelarmor.{location}.rep.googleapis.com/v1"
    parent = f"projects/{project_id}/locations/{location}"
    name = f"{parent}/templates/{template_id(definition)}"
    body = json.loads(definition.read_text())

    existing = session.get(f"{endpoint}/{name}")
    if existing.status_code == 200:
        logger.info("更新: %s", name)
        response = session.patch(f"{endpoint}/{name}?updateMask=filterConfig,templateMetadata", json=body)
    elif existing.status_code == 404:
        logger.info("作成: %s", name)
        response = session.post(f"{endpoint}/{parent}/templates?templateId={template_id(definition)}", json=body)
    else:
        logger.error("存在確認に失敗しました (%s): %s", existing.status_code, existing.text[:400])
        sys.exit(1)

    if not response.ok:
        logger.error("upsert に失敗しました (%s): %s", response.status_code, response.text[:600])
        sys.exit(1)
    return response.json()["name"]


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
    credentials, adc_project = google.auth.default(scopes=SCOPES)
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or adc_project
    if not project_id:
        logger.error("GCP project ID を解決できません。GOOGLE_CLOUD_PROJECT または ADC を確認してください")
        sys.exit(1)

    location = os.environ.get("MODEL_ARMOR_LOCATION", DEFAULT_LOCATION)
    definitions = resolve_definitions(sys.argv[1:])
    if not definitions:
        logger.error("定義ファイルがありません: %s", DEFINITIONS_DIR)
        sys.exit(1)

    session = AuthorizedSession(credentials)
    for definition in definitions:
        logger.info("デプロイ中: %s", definition.name)
        logger.info("完了: %s", upsert(session, definition, project_id, location))


if __name__ == "__main__":
    main()
