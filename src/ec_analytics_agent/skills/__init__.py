"""SkillToolset 定義

ADK の段階的開示により、起動時は L1 (frontmatter) のみロードし、
実行時に L2 (本文)、必要時に L3 (references) をロードする。
"""

import pathlib

from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

SKILLS_DIR = pathlib.Path(__file__).parent

skill_toolset = SkillToolset(
    skills=[
        load_skill_from_dir(SKILLS_DIR / "metric-interpretation"),
        load_skill_from_dir(SKILLS_DIR / "analysis-workflow"),
        load_skill_from_dir(SKILLS_DIR / "response-format"),
    ]
)
