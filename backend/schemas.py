from enum import Enum

from pydantic import BaseModel, Field


class Route(str, Enum):
    """Router가 선택할 수 있는 실행 경로."""

    REPORT_QA = "report_qa"
    EXPLAIN_TERM = "explain_term"
    CLARIFICATION = "clarification"
    OUT_OF_SCOPE = "out_of_scope"


class EvidenceStatus(str, Enum):
    """검색된 근거가 질문을 뒷받침하는 정도."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"


class EvidenceDecision(BaseModel):
    status: EvidenceStatus
    reason: str = Field(min_length=1, max_length=300)
    confidence: float = Field(ge=0, le=1)


class RouterDecision(BaseModel):
    """LLM Router가 반환해야 하는 구조화된 판단 결과."""

    route: Route
    reason: str = Field(
        min_length=1,
        max_length=200,
        description="해당 경로를 선택한 이유",
    )
    needs_report: bool = Field(
        description="답변을 위해 보고서가 필요한지 여부",
    )


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=2,
        max_length=500,
        description="사용자가 입력한 질문",
    )
    report_id: str | None = Field(
        default=None,
        description="현재 선택한 보고서 ID",
    )
    thread_id: str = Field(
        default="demo",
        min_length=1,
        max_length=100,
        description="대화 세션 식별자",
    )


class Source(BaseModel):
    report_id: str
    title: str
    section: str
    content: str
    relevance_score: int = 0


class ChatResponse(BaseModel):
    answer: str
    route: Route
    route_reason: str = ""
    evidence_status: EvidenceStatus | None = None
    evidence_reason: str = ""
    evidence_confidence: float | None = None
    sources: list[Source] = Field(default_factory=list)
    model: str
