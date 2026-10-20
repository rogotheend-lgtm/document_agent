# Research Report Agent

전문 보고서를 일반 사용자가 대화로 쉽게 이해하도록 돕는 교육용 미니 프로젝트입니다.

## Core

- LangGraph: Router에 따라 `report_qa`, `explain_term`, `clarification`, `out_of_scope` 경로 선택
- FastAPI: 보고서 목록과 채팅 REST API
- Vue 3: 보고서 선택, 채팅, Router 결과와 근거 표시
- Ollama/Qwen: 로컬 답변 생성
- Mini RAG: 관련 보고서 섹션 검색

## 실행

```bash
cd /Users/myeongro/Desktop/04_Project/research-report-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
ollama pull qwen3:0.6b
uvicorn backend.main:app --reload --port 8200
```

브라우저에서 <http://127.0.0.1:8200>을 엽니다. API 문서는 <http://127.0.0.1:8200/docs>입니다.

## 학습 순서

1. `backend/main.py`에서 REST API 확인
2. `backend/agent.py`에서 LangGraph 노드와 edge 확인
3. `backend/report_store.py`에서 검색 함수 확인
4. `backend/static/app.js`에서 Vue가 API를 호출하는 부분 확인
5. `OUT_OF_SCOPE_WORDS`와 system prompt를 직접 변경해 결과 비교

## 다음 단계(Optional)

1. `search_report()`를 embedding 검색으로 개선
2. 보고서 저장·검색 함수를 MCP 서버로 분리
3. `/api/chat/stream`과 SSE 추가
4. LangSmith trace 및 baseline/improved 평가 추가

`metadata.json`과 Markdown 파일을 같은 ID로 추가하면 샘플 보고서를 확장할 수 있습니다.
