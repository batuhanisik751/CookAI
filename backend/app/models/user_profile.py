from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_profiles"

    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dietary_restrictions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    allergies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    disliked_ingredients: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pantry_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
