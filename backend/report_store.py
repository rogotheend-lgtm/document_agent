import json
import math
import re
from collections import Counter
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
    "적정주가": "목표주가",
    "매수의견": "투자의견",
    "실적전망": "실적",
}

QUERY_EXPANSIONS = {
    "위험": {"우려", "하회", "지연", "감익", "하락", "변동"},
    "성장": {"증가", "확대", "증익", "개선", "상승"},
    "목표주가": {"투자의견", "매수", "하향", "상향"},
    "실적": {"매출", "영업이익", "순이익", "이익"},
    "수주": {"수주잔고", "파이프라인", "프로젝트"},
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
    # '수', '것' 같은 한 글자 토큰은 거의 모든 문단과 우연히 겹치므로 제외한다.
    return {
        token
        for token in normalized - SEARCH_STOPWORDS
        if len(token) >= 2
    }


@lru_cache(maxsize=1)
def list_reports() -> list[dict]:
    reports = json.loads((DATA_DIR / "metadata.json").read_text(encoding="utf-8"))
    local_metadata = DATA_DIR / "metadata.local.json"
    if local_metadata.exists():
        local_reports = json.loads(local_metadata.read_text(encoding="utf-8"))
        local_ids = {item["id"] for item in local_reports}
        reports = local_reports + [item for item in reports if item["id"] not in local_ids]
    return reports


def get_report(report_id: str) -> dict | None:
    metadata = next((item for item in list_reports() if item["id"] == report_id), None)
    if not metadata:
        return None
    local_path = DATA_DIR / f"{report_id}.local.md"
    path = local_path if local_path.exists() else DATA_DIR / f"{report_id}.md"
    if not path.exists():
        return None
    return {**metadata, "content": path.read_text(encoding="utf-8")}


def _split_long_block(block: str, max_chars: int) -> list[str]:
    """표처럼 빈 줄이 없는 긴 블록을 행 경계에서 나눈다."""
    if len(block) <= max_chars:
        return [block]
    chunks: list[str] = []
    buffer: list[str] = []
    size = 0
    for line in block.splitlines():
        if buffer and size + len(line) + 1 > max_chars:
            chunks.append("\n".join(buffer).strip())
            buffer, size = [], 0
        buffer.append(line)
        size += len(line) + 1
    if buffer:
        chunks.append("\n".join(buffer).strip())
    return [chunk for chunk in chunks if chunk]


def _chunk_content(content: str, max_chars: int = 1200) -> list[str]:
    """문단 경계를 우선 보존하면서 검색에 적합한 크기로 묶는다."""
    raw_blocks = [block.strip() for block in re.split(r"\n\s*\n", content) if block.strip()]
    blocks = [part for block in raw_blocks for part in _split_long_block(block, max_chars)]
    chunks: list[str] = []
    buffer: list[str] = []
    size = 0
    for block in blocks:
        if buffer and size + len(block) + 2 > max_chars:
            chunks.append("\n\n".join(buffer))
            buffer, size = [], 0
        buffer.append(block)
        size += len(block) + 2
    if buffer:
        chunks.append("\n\n".join(buffer))
    return chunks


def split_sections(markdown: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    title = "본문"
    buffer: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            if buffer:
                content = "\n".join(buffer).strip()
                chunks = _chunk_content(content)
                for index, chunk in enumerate(chunks, start=1):
                    label = title if len(chunks) == 1 else f"{title} · 청크 {index}"
                    sections.append({"section": label, "content": chunk})
            title, buffer = line[3:].strip(), []
        elif not line.startswith("# "):
            buffer.append(line)
    if buffer:
        content = "\n".join(buffer).strip()
        chunks = _chunk_content(content)
        for index, chunk in enumerate(chunks, start=1):
            label = title if len(chunks) == 1 else f"{title} · 청크 {index}"
            sections.append({"section": label, "content": chunk})
    return [section for section in sections if section["content"]]


def search_report(report_id: str, query: str, limit: int = 3) -> list[dict]:
    """문단 청킹과 TF-IDF 가중치를 이용한 로컬 sparse RAG 검색."""
    report = get_report(report_id)
    if not report:
        return []
    query_tokens = tokenize(query)
    expanded_tokens = set(query_tokens)
    for token in query_tokens:
        expanded_tokens.update(QUERY_EXPANSIONS.get(token, set()))
    sections = split_sections(report["content"])
    token_sets = [tokenize(f"{item['section']} {item['content']}") for item in sections]
    document_frequency = Counter(
        token for tokens in token_sets for token in tokens
    )
    scored = []
    total = max(len(sections), 1)
    for section, text_tokens in zip(sections, token_sets):
        direct = query_tokens & text_tokens
        expanded = (expanded_tokens - query_tokens) & text_tokens
        score = sum(
            1.0 + math.log((total + 1) / (document_frequency[token] + 1))
            for token in direct
        )
        score += 0.35 * len(expanded)
        # 면책·컴플라이언스 문단은 관련 단어가 직접 질의된 경우가 아니면 후순위로 둔다.
        if "Compliance Notice" in section["content"] or "법적 책임소재" in section["content"]:
            score *= 0.15
        scored.append((score, section))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "report_id": report_id,
            "title": report["title"],
            "section": item["section"],
            "content": item["content"],
            "relevance_score": round(score, 3),
        }
        for score, item in scored[:limit]
        if score > 0
    ]
