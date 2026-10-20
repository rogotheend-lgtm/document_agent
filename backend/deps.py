from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from backend.ollama import OllamaClient


@dataclass(frozen=True)
class AgentDeps:
    """Agent 노드가 공유하는 외부 의존성.

    노드가 LLM이나 저장소를 직접 생성하지 않게 하여 테스트와 교체를 쉽게 한다.
    """

    llm: OllamaClient
    search_report: Callable[[str, str, int], list[dict[str, Any]]]

