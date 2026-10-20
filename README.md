# Research Report Agent

전문 금융·산업 보고서를 일반 사용자가 대화로 쉽게 이해하도록 돕는 근거 기반 리서치 Agent입니다. 단순 PDF 챗봇과 달리 질문 의도를 분류하고, 관련 근거가 있을 때만 답변하며, 답변에 사용한 보고서 섹션을 함께 제시합니다.

> 포함된 반도체·게임·이차전지 문서는 기능 검증을 위한 가상 보고서이며 실제 투자 판단에 사용할 수 없습니다.

## 문제와 개선 목표

Baseline은 선택한 보고서 전체와 질문을 Qwen에 바로 전달합니다. 구현은 단순하지만 범위 밖 질문을 처리하지 못하고 관련 근거가 없어도 보고서 내용을 질문에 억지로 연결할 수 있습니다.

Improved Agent는 다음 흐름을 사용합니다.

```text
Vue UI → FastAPI → Singleton LangGraph Agent
                         ↓
                      Router
        ┌────────────────┼──────────────────┐
        ↓                ↓                  ↓
   report_qa       explain_term      clarification/out_of_scope
        ↓                ↓                  ↓
     retrieve          answer          clarify/refuse
        ↓
   Evidence Gate
     ├─ 근거 있음 → Qwen 답변 + 출처
     └─ 근거 없음 → 안전한 안내
```

## 핵심 기능

- LangGraph: `report_qa`, `explain_term`, `clarification`, `out_of_scope` 조건부 경로
- Structured Router: Pydantic으로 Qwen의 경로·이유·보고서 필요 여부 검증
- Hybrid Guard: 명백한 코드 생성·프롬프트 탈취 요청은 모델 호출 전에 차단
- Mini RAG: 보고서를 섹션 단위로 검색하고 동의어를 정규화
- Evidence Gate: 검색 근거가 없으면 Qwen 호출 전에 답변 중단
- FastAPI lifespan: Agent와 Ollama HTTP client를 한 번 생성하고 종료 시 정리
- Dependency Injection: LLM과 검색 함수를 `AgentDeps`로 graph node에 주입
- Vue 3: 보고서 선택, 채팅, Route 선택 이유와 근거 표시
- Baseline API: 동일 입력의 개선 전후 비교 지원
- Evaluation: 20개 질문으로 Route·근거 정확도와 지연시간 측정

## 프로젝트 구조

```text
backend/
├── main.py              # FastAPI, lifespan, REST API
├── agent.py             # LangGraph state, nodes, conditional edges
├── deps.py              # Agent dependency injection
├── ollama.py            # 재사용 가능한 Ollama HTTP client
├── report_store.py      # 보고서 로딩, section 검색, token 정규화
├── schemas.py           # API 및 Router Pydantic schema
├── data/reports/        # 데모 보고서 3종
└── static/              # Vue 3 사용자 UI
tests/                    # 모델 없이 실행되는 단위/API 테스트
evaluation/
├── questions.json       # 평가 질문 20개
└── run_eval.py          # Baseline/Improved 실험
```

## 실행

```bash
cd /Users/myeongro/Desktop/04_Project/research-report-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
ollama pull qwen3:0.6b
```

터미널 1:

```bash
ollama serve
```

터미널 2:

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8200
```

- Vue UI: <http://127.0.0.1:8200>
- OpenAPI: <http://127.0.0.1:8200/docs>
- Health: <http://127.0.0.1:8200/health>

`/health`의 `creation_count=1`과 변하지 않는 `instance_id`로 서버 수명 동안 Agent 하나가 재사용되는지 확인할 수 있습니다.

## REST API

| Method | Path | 설명 |
|---|---|---|
| GET | `/health` | 모델, Agent 생성 횟수와 인스턴스 ID |
| GET | `/api/reports` | 보고서 목록 |
| GET | `/api/reports/{report_id}` | 보고서 상세 |
| POST | `/api/chat` | Router·RAG·Evidence Gate가 적용된 Agent |
| POST | `/api/chat/baseline` | 비교용 단순 Qwen 호출 |

요청 예시:

```json
{
  "message": "가장 중요한 리스크는 뭐야?",
  "report_id": "sample-semiconductor-2026",
  "thread_id": "demo-user"
}
```

## 테스트

```bash
source .venv/bin/activate
pytest -q
```

테스트는 보고서 검색, 동의어 정규화, 명백한 범위 밖 요청, API validation과 singleton health를 확인합니다. LLM 응답의 비결정성 때문에 단위 테스트는 실제 Ollama 답변 문구에 의존하지 않습니다.

## Before/After 평가

Ollama와 FastAPI 서버를 실행한 상태에서:

```bash
python evaluation/run_eval.py
```

결과는 `evaluation/results.json`에 저장되며 Route 정확도, 근거 유무 판단 정확도, Baseline/Improved 평균 응답시간과 질문별 결과를 포함합니다. 작은 로컬 모델의 응답은 실행마다 달라질 수 있으므로 발표 자료에는 실행 시각과 모델명을 함께 기록합니다.

### 2026-10-20 실측 결과 (`qwen3:0.6b`, 20문항)

| 지표 | 결과 |
|---|---:|
| Route 정확도 | 100% |
| 근거 유무 판단 정확도 | 100% |
| Improved 평균 지연 | 0.810초 |
| Baseline 평균 지연 | 0.576초 |
| 안전성 개선에 따른 추가 지연 | 0.234초 |

첫 평가에서는 Route 75%, 근거 판단 90%였습니다. 실패 사례를 분석해 한국어 조사 정규화, 저정보 stopword 제거, 명백한 용어 설명·범위 밖 요청의 hybrid guard를 추가한 뒤 100%로 개선했습니다. 이 수치는 작은 데모 데이터셋에 대한 결과이며 일반화 성능을 의미하지 않습니다.

## Before/After 설명

| 항목 | Baseline | Improved |
|---|---|---|
| 질문 처리 | 보고서 전체를 Qwen에 전달 | Router로 의도 분류 |
| 검색 | 없음 | 관련 section 검색 |
| 범위 밖 요청 | 별도 처리 없음 | 규칙 + LLM Router |
| 근거 없음 | 환각 가능 | Evidence Gate에서 중단 |
| 출처 | 없음 | 보고서·section·원문 표시 |
| 자원 관리 | 요청 로직과 결합 | lifespan singleton + DI |

## 한계와 트레이드오프

- 현재 RAG는 임베딩이 아닌 token overlap 방식이라 의미가 유사한 새 표현을 놓칠 수 있습니다.
- `qwen3:0.6b`는 가볍지만 복잡하거나 모호한 질문의 Route를 오분류할 수 있습니다.
- 규칙 기반 조기 차단은 빠르지만 패턴을 지나치게 넓히면 정상 질문을 차단할 수 있습니다.
- Router 호출 때문에 Baseline보다 응답 지연이 증가할 수 있습니다.
- 표, 차트와 이미지의 정보는 아직 추출하지 않습니다.
- 데모는 단일 선택 보고서 질문에 집중하며 다중 보고서 비교는 향후 기능입니다.

## 향후 개선(Optional)

1. embedding 기반 hybrid search 및 reranking
2. 보고서 목록·검색 기능을 별도 MCP Server로 분리
3. 여러 기관 보고서의 공통점·차이점 비교
4. SSE 기반 Router·검색·생성 진행 상태 표시
5. LangSmith trace, dataset evaluation과 관리자 지표
6. PDF 표·차트 및 페이지 단위 출처 처리

## 학습 포인트

1. `backend/main.py`: lifespan에서 자원 생성·종료
2. `backend/deps.py`: node에 전달할 의존성
3. `backend/agent.py`: State, node, conditional edge
4. `backend/report_store.py`: 검색 성공과 근거 없음의 차이
5. `evaluation/run_eval.py`: 동일 입력의 Before/After 비교
