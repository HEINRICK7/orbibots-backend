import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.database import Base


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'SUSPENDED')", name="ck_users_status"),
        CheckConstraint("length(trim(name)) > 0", name="ck_users_name_not_empty"),
        CheckConstraint(
            "global_role IS NULL OR global_role = 'ADMIN'",
            name="ck_users_global_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    global_role: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


Index("uq_users_email_lower", func.lower(UserRecord.email), unique=True)
