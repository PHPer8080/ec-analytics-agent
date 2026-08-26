"""参照可能な Data Agent を固定リストに制限するガードレール

許可リストは `data_agents/definitions/*.json` から導出する。定義ファイルを追加すれば
参照先は自動で増える。リソース名の組み立ては `data_agents/deploy.py` の
`agent_id()` / `LOCATION` と同一規則で、デプロイ側とずれると実在しない名前を参照するため
規則を変える場合は両方を直すこと。

プロンプトに載せる選択肢の表 (DATA_AGENT_TABLE) も同じ導出結果から作る。
許可リストと表示が別々の情報源になると、遮断される名前を提示してしまうため。
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import google.auth
from google.adk.tools import BaseTool, ToolContext

LOCATION = "global"
AGENT_ID_PREFIX = "ec-analytics"
DEFINITIONS_DIR = Path(__file__).resolve().parents[3] / "data_agents" / "definitions"


@dataclass(frozen=True)
class DataAgentEntry:
    """1 つの Data Agent。name はフルリソース名"""

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

# DATA_ANALYST_SYSTEM_PROMPT の {DATA_AGENT_TABLE} に差し込む。
# ask_data_agent に渡す値なのでリソース名を含める
DATA_AGENT_TABLE = "\n".join(
    ["| リソース名 | 対象 |", "|---|---|"]
    + [f"| `{entry.name}` | {entry.display_name}<br>{entry.description} |" for entry in DATA_AGENTS]
)

# ROOT_SYSTEM_PROMPT の {DATA_AGENT_SUMMARY} に差し込む。
# Root はデータアクセスをしないため、リソース名は渡さず「何が分析できるか」だけを示す
DATA_AGENT_SUMMARY = "\n".join(f"- **{entry.display_name}**: {entry.description}" for entry in DATA_AGENTS)


def restrict_data_agent(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> dict | None:
    """ask_data_agent に許可外の Data Agent リソース名が渡されていないか検査する

    参照先はプロンプトの表で固定しているが、モデルが表に無い名前を組み立てる余地は残る。
    その場合に API へ到達する前に遮断する defense-in-depth として機能する。
    """
    if tool.name != "ask_data_agent":
        return None
    if args.get("data_agent_name") not in ALLOWED_DATA_AGENT_NAMES:
        return {"error": "指定された Data Agent は参照できません。提示されたリソース名から選んでください。"}
    return None
