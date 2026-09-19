"""Provider clients and the factory that picks one for a stored provider."""

import httpx

from sparklchat.models.provider import Provider, default_base_url
from sparklchat.services.crypto import decrypt
from sparklchat.services.providers.anthropic import AnthropicClient
from sparklchat.services.providers.base import (
    BaseClient,
    ChatMessage,
    ProviderConfig,
    ProviderError,
)
from sparklchat.services.providers.ollama import OllamaClient
from sparklchat.services.providers.openai import OpenAIClient

# KoboldCpp and `custom` both speak the OpenAI chat-completions protocol.
_CLIENTS: dict[str, type[BaseClient]] = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "ollama": OllamaClient,
    "koboldcpp": OpenAIClient,
    "custom": OpenAIClient,
}

__all__ = [
    "BaseClient",
    "ChatMessage",
    "ProviderConfig",
    "ProviderError",
    "api_key_for",
    "build_client",
    "config_for",
]


def api_key_for(provider: Provider) -> str | None:
    """Decrypt the provider's stored key, if it has one."""
    if not provider.api_key_encrypted:
        return None
    return decrypt(provider.api_key_encrypted)


def build_client(
    config: ProviderConfig, *, http_client: httpx.AsyncClient | None = None
) -> BaseClient:
    try:
        client_class = _CLIENTS[config.provider_type]
    except KeyError:
        raise ProviderError(f"unsupported provider type {config.provider_type!r}") from None
    return client_class(config, http_client=http_client)


def config_for(provider: Provider, api_key: str | None) -> ProviderConfig:
    """Build a client config from a stored provider row and its decrypted key."""
    return ProviderConfig(
        provider_type=provider.provider_type,
        base_url=provider.base_url or default_base_url(provider.provider_type),
        model=provider.model,
        api_key=api_key,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
        top_p=provider.top_p,
        extra_params=dict(provider.extra_params or {}),
    )
