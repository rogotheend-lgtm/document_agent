from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from backend.agent import AGENT
from backend.ollama import OLLAMA_MODEL
from backend.report_store import get_report, list_reports
from backend.schemas import ChatRequest, ChatResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 그래프와 보고서 캐시는 프로세스 시작 시 한 번 만들어져 모든 요청이 공유한다.
    app.state.agent = AGENT
    yield


app = FastAPI(title="Research Report Agent", version="0.1.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "model": OLLAMA_MODEL}


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
        sources=result.get("sources", []),
        model=OLLAMA_MODEL,
    )

