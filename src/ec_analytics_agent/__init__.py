"""ADK 内部由来の警告を抑止してからエージェントを公開する

いずれも ADK 自身の実験的機能・非推奨に関する通知で、こちらのコードでは対処できない。
ADK 更新時に見落とさないよう、抑止対象はメッセージ単位で列挙する。
"""

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
