from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from backend.agent import build_graph
from backend.deps import AgentDeps
from backend.ollama import OLLAMA_MODEL, OLLAMA_URL, OllamaClient
from backend.report_store import get_report, list_reports, search_report
from backend.schemas import ChatRequest, ChatResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 외부 자원과 Agent를 서버 시작 시 한 번 만들고 모든 요청에서 공유한다.
    llm = OllamaClient(url=OLLAMA_URL, model=OLLAMA_MODEL)
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
        "model": app.state.deps.llm.model,
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
        result = await app.state.agent.ainvoke({
            "message": payload.message.strip(),
            "report_id": payload.report_id,
            "sources": [],
        })
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Ollama 서버와 연결할 수 없습니다.") from exc
    return ChatResponse(
        answer=result["answer"],
        route=result["route"],
        route_reason=result.get("route_reason", ""),
        sources=result.get("sources", []),
        model=app.state.deps.llm.model,
    )
