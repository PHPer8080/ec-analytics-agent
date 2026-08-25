"""破壊的SQL意図の検出ガードレール"""

import re
from typing import Any

from google.adk.tools import BaseTool, ToolContext

DESTRUCTIVE_SQL_PATTERN = re.compile(
    r"\b(DELETE|DROP|TRUNCATE|UPDATE|INSERT|ALTER|CREATE|MERGE)\b",
    re.IGNORECASE,
)


def block_destructive_sql_intent(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> dict | None:
    """ask_data_agent への入力に破壊的SQL意図が含まれていないか検査する

    Conversational Analytics API 自体が参照専用のため、不正な意図を Data Agent に
    渡さないための defense-in-depth として機能する。
    """
    if tool.name != "ask_data_agent":
        return None
    query_text = args.get("query", "")
    if DESTRUCTIVE_SQL_PATTERN.search(query_text):
        return {"error": "データの参照のみ対応しています。"}
    return None
