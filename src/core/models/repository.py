# src/core/models/repository.py
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel


class Repository(SQLModel, table=True):
    __tablename__ = "repositories"

    id: int | None = Field(default=None, primary_key=True)
    owner: str = Field(max_length=255)
    name: str = Field(max_length=255)
    installation_id: int
    is_active: bool = True
    connected_at: datetime = Field(default_factory=datetime.now)
    last_review_at: datetime | None = None

    reviews: list["PRReview"] = Relationship(back_populates="repository", cascade_delete=True)
    config: "RepoConfig" = Relationship(back_populates="repository", cascade_delete=True, sa_relationship_kwargs={"uselist": False})

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner": self.owner,
            "name": self.name,
            "full_name": self.full_name,
            "installation_id": self.installation_id,
            "is_active": self.is_active,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_review_at": self.last_review_at.isoformat() if self.last_review_at else None,
        }
