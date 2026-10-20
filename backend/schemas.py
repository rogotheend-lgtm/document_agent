from typing import Literal

from pydantic import BaseModel, Field


Route = Literal["report_qa", "explain_term", "clarification", "out_of_scope"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)
    report_id: str | None = None
    thread_id: str = Field(default="demo", max_length=100)


class Source(BaseModel):
    report_id: str
    title: str
    section: str
    content: str


class ChatResponse(BaseModel):
    answer: str
    route: Route
    sources: list[Source]
    model: str

