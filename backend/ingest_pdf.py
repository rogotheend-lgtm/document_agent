"""PDF 보고서를 페이지 단위 Markdown 데이터로 적재한다."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pypdf import PdfReader


DATA_DIR = Path(__file__).parent / "data" / "reports"


def make_report_id(value: str) -> str:
    report_id = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    if not report_id:
        raise ValueError("report-id는 영문 소문자, 숫자 또는 하이픈을 포함해야 합니다.")
    return report_id


def ingest_pdf(
    pdf_path: Path,
    report_id: str,
    title: str,
    publisher: str,
    category: str,
    published_date: str,
    description: str,
) -> Path:
    report_id = make_report_id(report_id)
    reader = PdfReader(pdf_path)
    pages: list[str] = []
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"## {number}페이지\n{text}")

    if not pages:
        raise ValueError("PDF에서 텍스트를 추출하지 못했습니다. OCR이 필요한 문서인지 확인하세요.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # 실제 보고서 원문은 공개 저장소에 올라가지 않도록 .local.md로 저장한다.
    output_path = DATA_DIR / f"{report_id}.local.md"
    output_path.write_text(
        f"# {title}\n\n" + "\n\n".join(pages) + "\n",
        encoding="utf-8",
    )

    metadata_path = DATA_DIR / "metadata.local.json"
    metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata_path.exists()
        else []
    )
    item = {
        "id": report_id,
        "title": title,
        "publisher": publisher,
        "category": category,
        "date": published_date,
        "description": description,
        "source_file": pdf_path.name,
        "page_count": len(reader.pages),
    }
    metadata = [entry for entry in metadata if entry["id"] != report_id]
    metadata.insert(0, item)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF 보고서를 데모 데이터로 적재합니다.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--publisher", required=True)
    parser.add_argument("--category", default="기업 분석")
    parser.add_argument("--date", required=True)
    parser.add_argument("--description", default="실제 공개 리서치 보고서에서 추출한 데이터입니다.")
    args = parser.parse_args()
    output = ingest_pdf(
        args.pdf,
        args.report_id,
        args.title,
        args.publisher,
        args.category,
        args.date,
        args.description,
    )
    print(f"적재 완료: {output}")


if __name__ == "__main__":
    main()
