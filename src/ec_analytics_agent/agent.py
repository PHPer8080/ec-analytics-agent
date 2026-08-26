"""Root Agent と ADK App の定義

Root は初回の意図判定と DataAnalystAgent への handoff を担い、自身はデータアクセスを行わない。
"""

import os

from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.agents.llm_agent import LlmAgent
from google.adk.apps import App
from google.adk.models.google_llm import Gemini

from .agents import data_analyst_agent
from .agents.data_analyst import RETRY_OPTIONS
from .guards import DATA_AGENT_SUMMARY
from .plugins import build_bigquery_analytics_plugin, build_model_armor_plugin
from .prompts import ROOT_DESCRIPTION, ROOT_SYSTEM_PROMPT

root_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=RETRY_OPTIONS),
    name="ec_analytics_root",
    description=ROOT_DESCRIPTION,
    instruction=ROOT_SYSTEM_PROMPT.format(DATA_AGENT_SUMMARY=DATA_AGENT_SUMMARY),
    sub_agents=[data_analyst_agent],
)

plugins = [build_model_armor_plugin(), build_bigquery_analytics_plugin()]

# name はエージェントを読み込むディレクトリ名と揃える。揃えないと Runner が警告する
app = App(
    name="ec_analytics_agent",
    root_agent=root_agent,
    plugins=[plugin for plugin in plugins if plugin is not None],
    # handoff のたびに system instruction とツールが入れ替わり、プロンプト全体が再送される。
    # エージェントごとにキャッシュを持たせて再送を避ける。
    # ただしキャッシュ適用時は ADK が system_instruction を None にするため、
    # 評価の AgentDetails が組み立てられない。make eval では無効化する
    context_cache_config=None if os.environ.get("ADK_DISABLE_CONTEXT_CACHE") else ContextCacheConfig(min_tokens=2048),
)
