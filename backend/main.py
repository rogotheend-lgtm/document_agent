import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from backend.agent import build_graph
from backend.deps import AgentDeps
from backend.ollama import OLLAMA_MODEL, OLLAMA_URL, OllamaClient
from backend.openai_client import OpenAIClient
from backend.report_store import get_report, list_reports, search_report
from backend.schemas import ChatRequest, ChatResponse


def create_llm():
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "openai":
        return OpenAIClient()
    if provider == "ollama":
        return OllamaClient(url=OLLAMA_URL, model=OLLAMA_MODEL)
    raise RuntimeError(f"지원하지 않는 LLM_PROVIDER입니다: {provider}")


def agent_input(payload: ChatRequest) -> dict:
    return {
        "message": payload.message.strip(),
        "report_id": payload.report_id,
        "sources": [],
    }


def agent_config(payload: ChatRequest) -> dict:
    return {
        "run_name": "research-report-supervisor",
        "configurable": {"thread_id": payload.thread_id},
        "metadata": {"report_id": payload.report_id or "none"},
    }


def to_chat_response(result: dict, model: str) -> ChatResponse:
    return ChatResponse(
        answer=result["answer"],
        route=result["route"],
        route_reason=result.get("route_reason", ""),
        evidence_status=result.get("evidence_status"),
        evidence_reason=result.get("evidence_reason", ""),
        evidence_confidence=result.get("evidence_confidence"),
        sources=result.get("sources", []),
        model=model,
    )


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 외부 자원과 Agent를 서버 시작 시 한 번 만들고 모든 요청에서 공유한다.
    llm = create_llm()
    deps = AgentDeps(llm=llm, search_report=search_report)
    agent = build_graph(deps)

    app.state.deps = deps
    app.state.agent = agent
    app.state.creation_count = getattr(app.state, "creation_count", 0) + 1
    app.state.instance_id = id(agent)

    try:
        yield
    finally:
        # 서버 종료 시 공유 HTTP client의 연결 풀을 명시적으로 닫는다.
        await llm.aclose()


app = FastAPI(title="Research Report Agent", version="0.1.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": os.getenv("LLM_PROVIDER", "ollama"),
        "model": app.state.deps.llm.model,
        "langsmith_tracing": os.getenv("LANGSMITH_TRACING", "false").lower() == "true",
        "creation_count": app.state.creation_count,
        "instance_id": app.state.instance_id,
    }


@app.get("/api/reports")
def reports():
    return {"reports": list_reports()}


@app.get("/api/reports/{report_id}")
def report_detail(report_id: str):
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="보고서를 찾을 수 없습니다.")
    return report


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    try:
        result = await app.state.agent.ainvoke(
            agent_input(payload),
            config=agent_config(payload),
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="LLM 서비스와 연결할 수 없습니다.") from exc
    return to_chat_response(result, app.state.deps.llm.model)


@app.post("/api/chat/stream")
async def stream_chat(payload: ChatRequest):
    """LangGraph 노드 진행 상태와 최종 답변을 SSE로 전송한다."""
    async def event_stream():
        state = agent_input(payload)
        try:
            async for update in app.state.agent.astream(
                state,
                config=agent_config(payload),
                stream_mode="updates",
            ):
                for node, values in update.items():
                    state.update(values)
                    yield sse("progress", {"node": node})
            response = to_chat_response(state, app.state.deps.llm.model)
            yield sse("result", response.model_dump(mode="json"))
        except httpx.HTTPError:
            yield sse("error", {"detail": "LLM 서비스와 연결할 수 없습니다."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat/baseline")
async def baseline_chat(payload: ChatRequest):
    """개선 전 비교용: Router와 검색 없이 보고서 전체를 LLM에 전달한다."""
    if not payload.report_id:
        raise HTTPException(status_code=422, detail="Baseline은 보고서 선택이 필요합니다.")
    report = get_report(payload.report_id)
    if not report:
        raise HTTPException(status_code=404, detail="보고서를 찾을 수 없습니다.")

    answer = await app.state.deps.llm.chat([
        {
            "role": "system",
            "content": (
                "제공된 보고서를 바탕으로 질문에 한국어로 답하세요. "
                "Markdown 기호 없이 간결하게 작성하세요."
            ),
        },
        {
            "role": "user",
            "content": f"보고서:\n{report['content']}\n\n질문: {payload.message}",
        },
    ])
    return {
        "answer": answer,
        "model": app.state.deps.llm.model,
        "report_id": payload.report_id,
        "version": "baseline",
    }
