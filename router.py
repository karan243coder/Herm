import os
import time
import requests
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

class ModelProviderRouter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            default_headers={
                "HTTP-Referer": "https://telegram.org",
                "X-Title": "Nous Hermes Autonomous Agent"
            }
        )
        self.active_free_models = ["openrouter/free"]
        self.refresh_models()

    def refresh_models(self):
        try:
            r = requests.get("https://openrouter.ai/api/v1/models", timeout=10).json()
            free_slugs = [m['id'] for m in r.get('data', []) if ':free' in m['id']]
            if free_slugs:
                self.active_free_models = ["openrouter/free"] + free_slugs[:6]
                logger.info(f"Loaded active free models: {self.active_free_models}")
        except Exception as e:
            logger.warning(f"Could not fetch models dynamically: {e}")
            self.active_free_models = ["openrouter/free"]

    def generate_completion(self, messages: list[dict], max_tokens: int = 3500, temperature: float = 0.7) -> str | None:
        for model_name in self.active_free_models:
            try:
                logger.info(f"Dispatching to provider model: {model_name}")
                resp = self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                content = resp.choices[0].message.content.strip()
                if content:
                    return content
            except Exception as e:
                logger.warning(f"Failed on model {model_name}: {e}")
                continue
        return None
