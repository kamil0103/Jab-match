import os
import json
from typing import Optional, Dict, Any
from app.config import Config

class AIClient:
    def __init__(self):
        self.gemini_key = Config.GEMINI_API_KEY
        self.openai_key = Config.OPENAI_API_KEY
        self.provider = "gemini" if self.gemini_key else ("openai" if self.openai_key else None)

    def chat(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None, response_format: Optional[str] = None) -> str:
        if self.provider == "gemini":
            return self._gemini_chat(prompt, system_prompt, model, response_format)
        elif self.provider == "openai":
            return self._openai_chat(prompt, system_prompt, model, response_format)
        else:
            raise RuntimeError("No AI provider configured. Set GEMINI_API_KEY or OPENAI_API_KEY in .env")

    def _gemini_chat(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None, response_format: Optional[str] = None) -> str:
        from google import genai
        client = genai.Client(api_key=self.gemini_key)
        m = model or "gemini-2.5-flash"
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = client.models.generate_content(model=m, contents=full_prompt)
        return response.text

    def _openai_chat(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None, response_format: Optional[str] = None) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_key)
        m = model or "gpt-4o-mini"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        kwargs = {}
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(model=m, messages=messages, **kwargs)
        return response.choices[0].message.content
