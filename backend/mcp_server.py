"""금융 보고서 데이터를 표준 MCP 인터페이스로 제공하는 독립 서버."""

import json

from mcp.server import MCPServer

from backend.report_store import get_report, list_reports, search_report


mcp = MCPServer(
    "research-report-tools",
    description="등록된 금융 리서치 보고서를 검색하고 원문을 제공한다.",
)


@mcp.tool()
def search_report_sections(report_id: str, query: str, limit: int = 3) -> list[dict]:
    """선택한 보고서에서 질문과 관련된 근거 섹션을 검색한다."""
    return search_report(report_id, query, limit)


@mcp.tool()
def get_report_catalog() -> list[dict]:
    """현재 조회할 수 있는 금융 보고서 목록을 반환한다."""
    return list_reports()


@mcp.resource("report://{report_id}", mime_type="application/json")
def report_resource(report_id: str) -> str:
    """보고서 원문과 메타데이터를 읽기 전용 Resource로 제공한다."""
    report = get_report(report_id)
    if not report:
        return json.dumps({"error": "보고서를 찾을 수 없습니다."}, ensure_ascii=False)
    return json.dumps(report, ensure_ascii=False)


@mcp.prompt()
def grounded_report_qa(report_id: str, question: str) -> str:
    """근거 기반 보고서 분석을 위한 재사용 가능한 Prompt를 제공한다."""
    return (
        f"보고서 ID: {report_id}\n"
        f"질문: {question}\n\n"
        "search_report_sections Tool로 근거를 먼저 찾고, 검색된 근거만 사용해 "
        "한국어로 답하세요. 근거가 없으면 찾지 못했다고 명시하세요."
    )


if __name__ == "__main__":
    mcp.run()
