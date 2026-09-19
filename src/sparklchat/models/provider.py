"""AI provider configuration.

API keys are stored Fernet-encrypted and are never returned by the API; clients
only learn whether a key is set (`has_api_key`).
"""

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from sparklchat.models.base import utcnow

ChatRole = Literal["system", "user", "assistant"]

ProviderType = Literal["openai", "anthropic", "ollama", "koboldcpp", "custom"]

DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "ollama": "http://127.0.0.1:11434",
    # KoboldCpp and `custom` are driven through the OpenAI-compatible client.
    "koboldcpp": "http://127.0.0.1:5001/v1",
    "custom": "",
}


def default_base_url(provider_type: str) -> str:
    return DEFAULT_BASE_URLS.get(provider_type, "")


class Provider(SQLModel, table=True):
    __tablename__ = "providers"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    name: str = Field(max_length=100)
    provider_type: str = Field(default="openai", max_length=32)
    base_url: str = Field(default="", max_length=500)
    api_key_encrypted: str | None = Field(default=None)
    model: str = Field(default="", max_length=200)
    temperature: float | None = Field(default=None)
    max_tokens: int | None = Field(default=None)
    top_p: float | None = Field(default=None)
    extra_params: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ProviderCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    provider_type: ProviderType = "openai"
    # Left blank, the type's default endpoint is used.
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=1_000_000)
    top_p: float | None = Field(default=None, gt=0, le=1)
    extra_params: dict[str, Any] = Field(default_factory=dict)


class ProviderUpdate(SQLModel):
    """Partial update; omitted fields are left unchanged.

    An explicit `null` for `api_key` clears the stored key.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    provider_type: ProviderType | None = None
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=1_000_000)
    top_p: float | None = Field(default=None, gt=0, le=1)
    extra_params: dict[str, Any] | None = None


class ProviderPublic(SQLModel):
    id: int
    name: str
    provider_type: str
    base_url: str
    model: str
    temperature: float | None
    max_tokens: int | None
    top_p: float | None
    extra_params: dict[str, Any]
    has_api_key: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ProviderTestResult(SQLModel):
    ok: bool
    message: str
    reply: str | None = None


class CompletionMessage(SQLModel):
    role: ChatRole = "user"
    content: str = ""


class CompletionRequest(SQLModel):
    messages: list[CompletionMessage] = Field(min_length=1)


class CompletionResult(SQLModel):
    reply: str
