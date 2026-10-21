import os

import httpx


OPENAI_API_URL = os.getenv(
    "OPENAI_API_URL",
    "https://api.openai.com/v1/chat/completions",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")


class OpenAIClient:
    """서버 수명 동안 하나의 OpenAI HTTP 연결 풀을 재사용한다."""

    def __init__(
        self,
        api_key: str = OPENAI_API_KEY,
        model: str = OPENAI_MODEL,
        url: str = OPENAI_API_URL,
    ):
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")
        if not model:
            raise RuntimeError("OPENAI_MODEL이 설정되지 않았습니다.")

        self.api_key = api_key
        self.model = model
        self.url = url
        self._client = httpx.AsyncClient(timeout=120)

    async def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        response = await self._client.post(
            self.url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"].strip()
        if not answer:
            raise RuntimeError("OpenAI가 빈 응답을 반환했습니다.")
        return answer

    async def aclose(self) -> None:
        await self._client.aclose()
