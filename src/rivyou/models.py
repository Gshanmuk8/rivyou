from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .config import RULE_VERSION


def now() -> str:
    return datetime.now(UTC).isoformat()


class Evidence(BaseModel):
    field: str
    value: Any
    source_url: str
    rule: str
    excerpt: str = ""
    observed_at: str = Field(default_factory=now)
    content_hash: str = ""
    family: str = ""


class Store(BaseModel):
    store_id: str
    domain_url: str
    name: str = ""
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    socials: dict[str, list[str]] = Field(default_factory=dict)
    category: str | None = None
    description: str | None = None
    logo_url: str | None = None
    logo_path: str | None = None
    logo_background: str = "light"
    state: str | None = None
    shop_identity: str | None = None
    shopify: Literal["verified", "unconfirmed", "conflict"] = "unconfirmed"
    india: Literal["verified", "unconfirmed", "conflict"] = "unconfirmed"
    status: str = "review"
    reason: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    missing: dict[str, str] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    pages_checked: int = 0
    observed_at: str = Field(default_factory=now)
    rule_version: str = RULE_VERSION
