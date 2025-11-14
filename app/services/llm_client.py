from __future__ import annotations

import asyncio
from typing import Any

from openai import AsyncOpenAI  # type: ignore

from app.utils.logging import get_logger


class LLMClient:
    """Wrapper around the OpenAI SDK for deterministic calls."""

    def __init__(self, api_key: str | None, model: str = "gpt-4o-mini") -> None:
        if not api_key:
            raise ValueError("OpenAI (or compatible) API key is required.")
        self._client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.logger = get_logger("LLMClient")

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> str:
        """Execute a chat completion call."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_output_tokens is not None:
            kwargs["max_tokens"] = max_output_tokens

        self.logger.info(
            "llm_request",
            model=self.model,
            system_prompt_len=len(system_prompt),
            user_prompt_len=len(user_prompt),
            max_output_tokens=max_output_tokens,
        )

        response = await self._client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        self.logger.info(
            "llm_response",
            model=self.model,
            output_tokens=response.usage.completion_tokens if response.usage else None,
        )
        return text.strip()

    async def summarize_chunks(
        self,
        chunks: list[str],
        *,
        max_tokens: int = 600,
        temperature: float = 0.0,
    ) -> str:
        """Summarize large content by chunking sequentially."""
        if not chunks:
            return ""

        summary = chunks[0]
        for chunk in chunks[1:]:
            summary = await self.complete(
                system_prompt="You are a compression assistant. Combine information from the existing summary and the new chunk. Respond with a concise but complete merged summary.",
                user_prompt=f"Existing summary:\n{summary}\n\nNew chunk:\n{chunk}\n\nReturn the merged summary.",
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        return summary


class AsyncSemaphore:
    """Simple async semaphore wrapper to guard LLM concurrency."""

    def __init__(self, value: int = 1) -> None:
        self._semaphore = asyncio.Semaphore(value)

    async def __aenter__(self) -> None:
        await self._semaphore.acquire()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._semaphore.release()


