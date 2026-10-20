import json
import re
from functools import lru_cache
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data" / "reports"


@lru_cache(maxsize=1)
def list_reports() -> list[dict]:
    return json.loads((DATA_DIR / "metadata.json").read_text(encoding="utf-8"))


def get_report(report_id: str) -> dict | None:
    metadata = next((item for item in list_reports() if item["id"] == report_id), None)
    if not metadata:
        return None
    path = DATA_DIR / f"{report_id}.md"
    if not path.exists():
        return None
    return {**metadata, "content": path.read_text(encoding="utf-8")}


def split_sections(markdown: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    title = "본문"
    buffer: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            if buffer:
                sections.append({"section": title, "content": "\n".join(buffer).strip()})
            title, buffer = line[3:].strip(), []
        elif not line.startswith("# "):
            buffer.append(line)
    if buffer:
        sections.append({"section": title, "content": "\n".join(buffer).strip()})
    return [section for section in sections if section["content"]]


def search_report(report_id: str, query: str, limit: int = 3) -> list[dict]:
    """교육용 1차 RAG: 단어 겹침으로 관련 섹션을 고른다.

    추후 이 함수 내부만 embedding/vector DB 또는 MCP 호출로 교체할 수 있다.
    """
    report = get_report(report_id)
    if not report:
        return []
    query_tokens = set(re.findall(r"[가-힣A-Za-z0-9]+", query.lower()))
    scored = []
    for section in split_sections(report["content"]):
        text_tokens = set(re.findall(r"[가-힣A-Za-z0-9]+", section["content"].lower()))
        score = len(query_tokens & text_tokens)
        scored.append((score, section))
    scored.sort(key=lambda item: item[0], reverse=True)
    chosen = [item[1] for item in scored[:limit] if item[0] > 0]
    return [
        {
            "report_id": report_id,
            "title": report["title"],
            "section": item["section"],
            "content": item["content"],
        }
        for item in chosen
    ]
