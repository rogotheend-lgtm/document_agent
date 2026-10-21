import asyncio

from backend.agent import evidence_check_node
from backend.deps import AgentDeps
from backend.schemas import EvidenceStatus


class FakeLLM:
    def __init__(self, response: str = ""):
        self.response = response
        self.call_count = 0

    async def chat(self, messages: list[dict], temperature: float = 0) -> str:
        self.call_count += 1
        return self.response


def deps_with(llm: FakeLLM) -> AgentDeps:
    return AgentDeps(llm=llm, search_report=lambda *_: [])


def test_no_sources_is_unsupported_without_llm_call():
    llm = FakeLLM()
    result = asyncio.run(evidence_check_node(
        {"message": "게임 전망", "sources": []},
        deps=deps_with(llm),
    ))
    assert result["evidence_status"] == EvidenceStatus.UNSUPPORTED
    assert llm.call_count == 0


def test_high_retrieval_score_is_supported_without_llm_call():
    llm = FakeLLM()
    result = asyncio.run(evidence_check_node(
        {
            "message": "주요 위험",
            "sources": [{"section": "주요 위험", "content": "공급 과잉", "relevance_score": 2}],
        },
        deps=deps_with(llm),
    ))
    assert result["evidence_status"] == EvidenceStatus.SUPPORTED
    assert llm.call_count == 0


def test_explicit_downside_facts_support_risk_question_without_llm_call():
    llm = FakeLLM()
    result = asyncio.run(evidence_check_node(
        {
            "message": "가장 중요한 위험은 뭐야?",
            "sources": [
                {
                    "section": "1페이지 · 청크 2",
                    "content": "PPA 지연 우려와 연료전지 비용 증가로 감익이 예상된다.",
                    "relevance_score": 0.7,
                }
            ],
        },
        deps=deps_with(llm),
    ))
    assert result["evidence_status"] == EvidenceStatus.SUPPORTED
    assert result["evidence_confidence"] == 0.85
    assert llm.call_count == 0


def test_ambiguous_retrieval_uses_llm_checker():
    llm = FakeLLM(
        '{"status":"unsupported","reason":"질문과 직접 관련이 없습니다.","confidence":0.95}'
    )
    result = asyncio.run(evidence_check_node(
        {
            "message": "개인 일정은?",
            "sources": [{"section": "전망", "content": "시장 전망", "relevance_score": 1}],
        },
        deps=deps_with(llm),
    ))
    assert result["evidence_status"] == EvidenceStatus.UNSUPPORTED
    assert llm.call_count == 1
