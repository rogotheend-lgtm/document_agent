import os

import httpx


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")


async def chat(messages: list[dict], temperature: float = 0.1) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "think": False,
        "messages": messages,
        "options": {"temperature": temperature, "num_ctx": 4096, "num_predict": 500},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
    answer = response.json().get("message", {}).get("content", "").strip()
    if not answer:
        raise RuntimeError("Ollama가 빈 응답을 반환했습니다.")
    return answer

