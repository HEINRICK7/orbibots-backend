from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.authentication.global_role import GlobalRole
from app.src.domain.entities.company_onboarding.membership_scope import MembershipScope


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class CompanyAccessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_id: UUID
    company_name: str
    role: CompanyRole
    scope: MembershipScope | None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    global_role: GlobalRole | None
    company_accesses: tuple[CompanyAccessResponse, ...]
