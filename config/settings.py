"""Central application settings.

All configuration is read from environment variables (loaded from .env locally).
The API key is stored with repr=False so it can never leak via printing or logging
a Settings object.
"""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()  # reads .env if present; harmless if absent (e.g., in deployment)


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Business Process Automation Auditor"
    openrouter_base_url: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    )
    openrouter_model: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    )
    openrouter_api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""), repr=False
    )

    @property
    def ai_enabled(self) -> bool:
        key = self.openrouter_api_key.strip()
        return bool(key) and key != "your_key_here"


def get_settings() -> Settings:
    return Settings()