"""Secure backend call to OpenRouter (OpenAI-compatible). The key is read from settings and never displayed or logged."""
from config.settings import Settings


class AIError(Exception):
    """Carries a message that is safe to show to the user (never contains secrets)."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


_MESSAGES = {
    "AuthenticationError": "The AI service rejected the API key. Check OPENROUTER_API_KEY in your .env file.",
    "PermissionDeniedError": "The AI service refused this request. Check your key's permissions and credits.",
    "RateLimitError": "The AI service is rate-limiting requests or the account is out of credit. Try again shortly.",
    "APITimeoutError": "The AI service took too long to respond.",
    "APIConnectionError": "The AI service could not be reached. Check your internet connection.",
    "NotFoundError": "The configured model was not found. Check OPENROUTER_MODEL in your .env file.",
}


def call_llm(settings: Settings, system: str, user: str) -> str:
    from openai import OpenAI   # imported here so the rest of the app works without the package

    client = OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url,
                    timeout=60.0, max_retries=2,
                    default_headers={"X-Title": "AI Business Process Automation Auditor"})
    try:
        resp = client.chat.completions.create(
            model=settings.openrouter_model, temperature=0.2, max_tokens=2800,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    except Exception as exc:
        raise AIError(_MESSAGES.get(type(exc).__name__, "The AI service returned an error.")) from None
    content = resp.choices[0].message.content if resp.choices else None
    if not content:
        raise AIError("The AI service returned an empty response.")
    return content