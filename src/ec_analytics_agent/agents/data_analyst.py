import google.auth
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.adk.tools.data_agent import DataAgentCredentialsConfig, DataAgentToolset
from google.adk.tools.data_agent.config import DataAgentToolConfig
from google.genai import types

from ..guards import DATA_AGENT_TABLE, block_destructive_sql_intent, restrict_data_agent
from ..prompts import DATA_ANALYST_DESCRIPTION, DATA_ANALYST_SYSTEM_PROMPT
from ..skills import skill_toolset

# Gemini 2.5 系は動的共有クォータで運用されており 429 が一時的に返る。
# コンソールから上限を引き上げられないため指数バックオフで吸収する
RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=5, initial_delay=2, max_delay=60, exp_base=2, http_status_codes=[429, 503]
)

# Gemini 組み込みのコンテンツフィルタを既定任せにせず明示する
SAFETY_SETTINGS = [
    types.SafetySetting(category=category, threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE)
    for category in (
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    )
]

credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

# 探索系ツール (list_accessible_data_agents / get_data_agent_info) は公開しない
data_toolset = DataAgentToolset(
    tool_filter=["ask_data_agent"],
    credentials_config=DataAgentCredentialsConfig(credentials=credentials),
    data_agent_tool_config=DataAgentToolConfig(max_query_result_rows=500),
)

data_analyst_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash", retry_options=RETRY_OPTIONS),
    name="data_analyst",
    description=DATA_ANALYST_DESCRIPTION,
    instruction=DATA_ANALYST_SYSTEM_PROMPT.format(DATA_AGENT_TABLE=DATA_AGENT_TABLE),
    tools=[data_toolset, skill_toolset],
    before_tool_callback=[block_destructive_sql_intent, restrict_data_agent],
    planner=BuiltInPlanner(thinking_config=types.ThinkingConfig(thinking_budget=8000)),
    generate_content_config=types.GenerateContentConfig(safety_settings=SAFETY_SETTINGS),
)
