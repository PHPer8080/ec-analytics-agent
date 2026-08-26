import re
from typing import Any

from google.adk.tools import BaseTool, ToolContext

DESTRUCTIVE_SQL_PATTERN = re.compile(
    r"\b(DELETE|DROP|TRUNCATE|UPDATE|INSERT|ALTER|CREATE|MERGE)\b",
    re.IGNORECASE,
)


# API 自体が参照専用なので defense-in-depth
def block_destructive_sql_intent(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> dict | None:
    if tool.name != "ask_data_agent":
        return None
    query_text = args.get("query", "")
    if DESTRUCTIVE_SQL_PATTERN.search(query_text):
        return {"error": "データの参照のみ対応しています。"}
    return None
