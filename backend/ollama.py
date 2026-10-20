import os

import httpx


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")


class OllamaClient:
    """서버 수명 동안 하나의 HTTP 연결 풀을 재사용하는 Ollama client."""

    def __init__(self, url: str = OLLAMA_URL, model: str = OLLAMA_MODEL):
        self.url = url
        self.model = model
        self._client = httpx.AsyncClient(timeout=120)

    async def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "messages": messages,
            "options": {"temperature": temperature, "num_ctx": 4096, "num_predict": 500},
        }
        response = await self._client.post(self.url, json=payload)
        response.raise_for_status()
        answer = response.json().get("message", {}).get("content", "").strip()
        if not answer:
            raise RuntimeError("Ollama가 빈 응답을 반환했습니다.")
        return answer

    async def aclose(self) -> None:
        await self._client.aclose()
