# src/core/models/repo_config.py
from datetime import datetime
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, Relationship, SQLModel


class RepoConfig(SQLModel, table=True):
    __tablename__ = "repo_configs"

    id: int | None = Field(default=None, primary_key=True)
    repository_id: int = Field(foreign_key="repositories.id", unique=True, ondelete="CASCADE")
    
    # Review behavior
    enabled: bool = True
    auto_review: bool = True
    review_on_update: bool = False
    
    # File filtering
    include_patterns: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String), default=[]))
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.min.js",
            "*.min.css",
            "*.map",
            "**/*.lock",
            "**/package-lock.json",
            "**/composer.lock",
            "**/yarn.lock",
            "**/.DS_Store",
            "**/public/build/**",
            "**/public/hot",
            "**/storage/**",
            "**/bootstrap/cache/**",
        ],
        sa_column=Column(ARRAY(String), default=[])
    )
    
    # Output
    output_language: str = Field(default="en", max_length=10)
    
    # Notifications
    slack_channel: str | None = Field(default=None, max_length=100)
    slack_notify_on: str = Field(default="critical", max_length=20)
    github_comment: bool = True
    
    # Agents toggle
    agents: dict = Field(default_factory=lambda: {"breaking_change": True, "code_review": True}, sa_column=Column(JSONB, default={}))
    
    # Commands toggle
    commands: dict = Field(default_factory=lambda: {"fix": True}, sa_column=Column(JSONB, default={}))
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    repository: "Repository" = Relationship(back_populates="config")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "enabled": self.enabled,
            "auto_review": self.auto_review,
            "review_on_update": self.review_on_update,
            "include_patterns": self.include_patterns or [],
            "exclude_patterns": self.exclude_patterns or [],
            "output_language": self.output_language,
            "slack_channel": self.slack_channel,
            "slack_notify_on": self.slack_notify_on,
            "github_comment": self.github_comment,
            "agents": self.agents or {},
            "commands": self.commands or {},
        }
