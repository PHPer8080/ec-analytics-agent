import os

from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.agents.llm_agent import LlmAgent
from google.adk.apps import App
from google.adk.models.google_llm import Gemini
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.genai import types

from .agents import data_analyst_agent
from .agents.data_analyst import RETRY_OPTIONS, SAFETY_SETTINGS
from .guards import DATA_AGENT_SUMMARY
from .plugins import build_bigquery_analytics_plugin, build_model_armor_plugin, build_reflect_retry_plugin
from .prompts import ROOT_DESCRIPTION, ROOT_SYSTEM_PROMPT

root_agent = LlmAgent(
    model=Gemini(model="gemini-3.8-flash", retry_options=RETRY_OPTIONS),
    name="ec_analytics_root",
    description=ROOT_DESCRIPTION,
    instruction=ROOT_SYSTEM_PROMPT.format(DATA_AGENT_SUMMARY=DATA_AGENT_SUMMARY),
    sub_agents=[data_analyst_agent],
    # handoff の判定だけなので思考量を絞る (Gemini 3 系は既定で思考が有効)
    planner=BuiltInPlanner(thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)),
    generate_content_config=types.GenerateContentConfig(safety_settings=SAFETY_SETTINGS),
)

plugins = [build_model_armor_plugin(), build_bigquery_analytics_plugin(), build_reflect_retry_plugin()]

# name はエージェントを読み込むディレクトリ名と揃える。揃えないと Runner が警告する
app = App(
    name="ec_analytics_agent",
    root_agent=root_agent,
    plugins=[plugin for plugin in plugins if plugin is not None],
    # 適用時は ADK が system_instruction を None にし評価が組み立てられないため、
    # make eval では ADK_DISABLE_CONTEXT_CACHE で無効化する。
    # min_tokens は gemini-3.8-flash の明示キャッシュの下限。下回ると作成が 400 になる
    context_cache_config=None if os.environ.get("ADK_DISABLE_CONTEXT_CACHE") else ContextCacheConfig(min_tokens=4096),
)
