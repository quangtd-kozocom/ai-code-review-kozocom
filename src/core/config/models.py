"""
SQLModel definitions for configuration database storage.

SQLModel = SQLAlchemy + Pydantic combined.
Same model works for DB operations AND validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


class ConfigBase(SQLModel):
    """Base fields shared across config models."""

    owner: str = Field(index=True, max_length=255)
    repo: str = Field(index=True, max_length=255)


class ConfigModel(ConfigBase, table=True):
    """
    Database table for repository configurations.

    Stores full config as JSONB for schema flexibility.
    """

    __tablename__ = "configs"
    __table_args__ = (
        UniqueConstraint("owner", "repo", name="uq_configs_owner_repo"),
    )

    # Primary key
    id: int | None = Field(default=None, primary_key=True)

    # Config stored as JSONB
    config_data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, default={}),
    )

    # Timestamps
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    # Audit
    created_by: str | None = Field(default=None, max_length=255)


class ConfigCreate(ConfigBase):
    """Schema for creating a new config."""

    config_data: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None


class ConfigUpdate(SQLModel):
    """Schema for updating config."""

    config_data: dict[str, Any]
    updated_by: str | None = None


class ConfigRead(ConfigBase):
    """Schema for reading config (API response)."""

    id: int
    config_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime
