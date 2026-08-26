import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import google.auth
from google.adk.tools import BaseTool, ToolContext

# data_agents/deploy.py の agent_id() / LOCATION と同一規則。ずれると実在しない名前を参照する
LOCATION = "global"
AGENT_ID_PREFIX = "ec-analytics"
DEFINITIONS_DIR = Path(__file__).resolve().parents[3] / "data_agents" / "definitions"


@dataclass(frozen=True)
class DataAgentEntry:
    name: str
    display_name: str
    description: str


def load_data_agents() -> tuple[DataAgentEntry, ...]:
    if not DEFINITIONS_DIR.is_dir():
        raise RuntimeError(f"Data Agent の定義ディレクトリが見つかりません: {DEFINITIONS_DIR}")

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or google.auth.default()[1]
    entries = []
    for definition in sorted(DEFINITIONS_DIR.glob("*.json")):
        body = json.loads(definition.read_text())
        agent_id = f"{AGENT_ID_PREFIX}-{definition.stem.replace('_', '-').lower()}"
        entries.append(
            DataAgentEntry(
                name=f"projects/{project_id}/locations/{LOCATION}/dataAgents/{agent_id}",
                display_name=body.get("displayName") or agent_id,
                description=body.get("description") or "",
            )
        )

    if not entries:
        raise RuntimeError(f"Data Agent の定義が 1 件もありません: {DEFINITIONS_DIR}")
    return tuple(entries)


DATA_AGENTS = load_data_agents()
ALLOWED_DATA_AGENT_NAMES = frozenset(entry.name for entry in DATA_AGENTS)

# {DATA_AGENT_TABLE} 用。ask_data_agent に渡す値なのでリソース名を含める
DATA_AGENT_TABLE = "\n".join(
    ["| リソース名 | 対象 |", "|---|---|"]
    + [f"| `{entry.name}` | {entry.display_name}<br>{entry.description} |" for entry in DATA_AGENTS]
)

# {DATA_AGENT_SUMMARY} 用。Root はデータアクセスをしないためリソース名は渡さない
DATA_AGENT_SUMMARY = "\n".join(f"- **{entry.display_name}**: {entry.description}" for entry in DATA_AGENTS)


# 参照先はプロンプトの表で固定しているが、表に無い名前を組み立てる余地は残る
def restrict_data_agent(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> dict | None:
    if tool.name != "ask_data_agent":
        return None
    if args.get("data_agent_name") not in ALLOWED_DATA_AGENT_NAMES:
        return {"error": "指定された Data Agent は参照できません。提示されたリソース名から選んでください。"}
    return None
