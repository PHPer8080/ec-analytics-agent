import os
import warnings

# ADK 側が用意している抑止スイッチ (@experimental デコレータが参照する)
os.environ.setdefault("ADK_SUPPRESS_EXPERIMENTAL_FEATURE_WARNINGS", "1")

for category, message in (
    (UserWarning, r"\[EXPERIMENTAL\] feature"),
    (DeprecationWarning, r"BaseAgentConfig is deprecated"),
    (DeprecationWarning, r"GOOGLE_GENAI_USE_VERTEXAI is deprecated"),
):
    warnings.filterwarnings("ignore", message=message, category=category)

from .agent import app, root_agent  # noqa: E402

__all__ = ["app", "root_agent"]
