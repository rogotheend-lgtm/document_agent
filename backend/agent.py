import json
import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.ollama import OLLAMA_MODEL, chat
from backend.report_store import search_report
from backend.schemas import Route


class AgentState(TypedDict, total=False):
    message: str
    report_id: str | None
    route: Route
    sources: list[dict]
    answer: str


OUT_OF_SCOPE_WORDS = {"맛집", "날씨", "게임", "코딩", "파이썬", "번역", "연애"}
FINANCE_TERMS = {"ebitda", "per", "pbr", "roe", "영업이익률", "밸류에이션", "변동성"}


async def router_node(state: AgentState) -> dict:
    message = state["message"].lower()
    # 명백한 경우는 모델을 호출하지 않아 빠르고 예측 가능하게 처리한다.
    if any(word in message for word in OUT_OF_SCOPE_WORDS):
        return {"route": "out_of_scope"}
    if any(term in message for term in FINANCE_TERMS) and not state.get("report_id"):
        return {"route": "explain_term"}
    if not state.get("report_id"):
        return {"route": "clarification"}

    prompt = """질문을 다음 중 하나로 분류하세요.
report_qa: 선택한 보고서의 내용, 수치, 결론, 위험, 비교에 관한 질문
explain_term: 보고서를 이해하기 위한 금융·산업 용어 질문
clarification: 대상이나 질문이 모호하여 추가 정보가 필요한 경우
out_of_scope: 보고서·금융·산업 리서치와 무관한 요청
JSON만 출력하세요. 예: {\"route\":\"report_qa\"}"""
    raw = await chat([
        {"role": "system", "content": prompt},
        {"role": "user", "content": state["message"]},
    ], temperature=0)
    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    try:
        route = json.loads(match.group(0))["route"] if match else "report_qa"
    except (json.JSONDecodeError, KeyError):
        route = "report_qa"
    allowed = {"report_qa", "explain_term", "clarification", "out_of_scope"}
    return {"route": route if route in allowed else "report_qa"}


def retrieve_node(state: AgentState) -> dict:
    return {"sources": search_report(state["report_id"], state["message"])}


async def answer_node(state: AgentState) -> dict:
    sources = state.get("sources", [])
    context = "\n\n".join(
        f"[{item['section']}]\n{item['content']}" for item in sources
    )
    prompt = """당신은 전문 리서치 보고서를 일반 사용자가 이해하기 쉽게 설명하는 도우미입니다.
제공된 근거만 사용하고, 근거에 없는 사실은 추측하지 마세요.
먼저 한 줄 결론을 말하고, 이어서 쉬운 설명을 2~4개 항목으로 작성하세요.
투자 권유가 아니라 보고서 이해를 돕는 설명임을 지키세요."""
    if state["route"] == "explain_term":
        context = "선택된 문서가 없는 금융 용어 설명입니다. 일반적 정의만 간결하게 설명하세요."
    answer = await chat([
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"근거:\n{context}\n\n질문: {state['message']}"},
    ])
    return {"answer": answer}


def refusal_node(_: AgentState) -> dict:
    return {"answer": "저는 등록된 리서치 보고서의 요약, 비교, 용어 설명과 근거 확인을 돕는 챗봇입니다. 분석할 보고서나 금융·산업 리서치에 관해 질문해 주세요.", "sources": []}


def clarification_node(_: AgentState) -> dict:
    return {"answer": "먼저 분석할 보고서를 선택하거나, 어떤 기업·산업·기간에 관한 질문인지 조금 더 구체적으로 알려주세요.", "sources": []}


def choose_route(state: AgentState) -> str:
    return state["route"]


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("router", router_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("answer", answer_node)
    graph.add_node("refusal", refusal_node)
    graph.add_node("clarification", clarification_node)
    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", choose_route, {
        "report_qa": "retrieve",
        "explain_term": "answer",
        "clarification": "clarification",
        "out_of_scope": "refusal",
    })
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    graph.add_edge("refusal", END)
    graph.add_edge("clarification", END)
    return graph.compile()


AGENT = build_graph()

