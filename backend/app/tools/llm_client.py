"""
LLM Client (Tools & Services Layer).

Model-agnostic and ENV-driven: which provider and model get called is
decided entirely by app.config.Settings (LLM_PROVIDER / LLM_MODEL), never
hardcoded here or in any agent. Swapping providers/models is a config
change, not a code change.

To add a new provider: implement a `_call_<provider>` function with the
same signature and register it in _PROVIDERS below.
"""
from app.config import get_settings


class LLMUnavailableError(RuntimeError):
    pass


def _call_anthropic(system: str, prompt: str, model: str, max_tokens: int) -> str:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LLMUnavailableError("ANTHROPIC_API_KEY is not configured")

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
    return "\n".join(parts).strip()


def _call_openai(system: str, prompt: str, model: str, max_tokens: int) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMUnavailableError("OPENAI_API_KEY is not configured")

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()


_PROVIDERS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    # "azure_openai": _call_azure_openai,   # add future providers here, then flip
    #                                          LLM_PROVIDER in .env -- no
    #                                          agent/router code changes.
}


def generate(system: str, prompt: str) -> str:
    """Call the currently configured LLM provider/model.

    Raises LLMUnavailableError if no key is configured or the provider is
    unknown -- callers (Composer) fall back to a deterministic template in
    that case rather than failing the request.
    """
    settings = get_settings()
    handler = _PROVIDERS.get(settings.llm_provider)
    if handler is None:
        raise LLMUnavailableError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")
    return handler(system, prompt, settings.llm_model, settings.llm_max_tokens)
