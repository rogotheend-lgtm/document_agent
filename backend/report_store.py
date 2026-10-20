import json
import re
from functools import lru_cache
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data" / "reports"

TOKEN_ALIASES = {
    "리스크": "위험",
    "위험요인": "위험",
    "위험요소": "위험",
    "수익성": "이익",
    "영업이익률": "이익",
    "매출액": "매출",
    "전망치": "전망",
    "성장성": "성장",
}

SEARCH_STOPWORDS = {
    "가장",
    "주요",
    "산업",
    "섹터",
    "전망",
    "뭐야",
    "알려줘",
    "설명해줘",
    "어떻게",
}

KOREAN_SUFFIXES = (
    "에서",
    "으로",
    "에게",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "로",
    "와",
    "과",
    "도",
    "만",
)


def normalize_token(token: str) -> str:
    for suffix in KOREAN_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            token = token[: -len(suffix)]
            break
    return TOKEN_ALIASES.get(token, token)


def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text.lower())
    normalized = {normalize_token(token) for token in tokens}
    return normalized - SEARCH_STOPWORDS


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
    query_tokens = tokenize(query)
    scored = []
    for section in split_sections(report["content"]):
        text_tokens = tokenize(f"{section['section']} {section['content']}")
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
