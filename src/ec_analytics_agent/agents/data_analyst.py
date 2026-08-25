"""DataAnalystAgent 定義

ユーザー対応の主担当。要件が曖昧な場合のみ Root Agent にエスカレーションする。
"""

import google.auth
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.adk.tools.data_agent import DataAgentCredentialsConfig, DataAgentToolset
from google.adk.tools.data_agent.config import DataAgentToolConfig
from google.genai import types

from ..guards import block_destructive_sql_intent
from ..prompts import DATA_ANALYST_DESCRIPTION, DATA_ANALYST_SYSTEM_PROMPT
from ..skills import skill_toolset

# Gemini 2.5 系は動的共有クォータで運用されており 429 が一時的に返る。
# コンソールから上限を引き上げられないため指数バックオフで吸収する
RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=5, initial_delay=2, max_delay=60, exp_base=2, http_status_codes=[429, 503]
)

credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

data_toolset = DataAgentToolset(
    credentials_config=DataAgentCredentialsConfig(credentials=credentials),
    data_agent_tool_config=DataAgentToolConfig(max_query_result_rows=500),
)

data_analyst_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=RETRY_OPTIONS),
    name="data_analyst",
    description=DATA_ANALYST_DESCRIPTION,
    instruction=DATA_ANALYST_SYSTEM_PROMPT,
    tools=[data_toolset, skill_toolset],
    before_tool_callback=block_destructive_sql_intent,
    planner=BuiltInPlanner(thinking_config=types.ThinkingConfig(thinking_budget=8000)),
)
