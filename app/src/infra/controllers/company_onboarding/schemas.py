from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.src.domain.dtos.company_onboarding import CompanyInvitationRequest
from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.entities.company_onboarding.status import (
    CompanyStatus,
    InvitationStatus,
    OutboxStatus,
)


class ProvisionCompanyRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    admin_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=32)

    def to_command(self) -> CompanyInvitationRequest:
        return CompanyInvitationRequest(
            company_name=self.company_name,
            admin_name=self.admin_name,
            email=self.email,
            phone=self.phone,
        )


class ProvisionCompanyResponse(BaseModel):
    company_id: UUID
    invitation_id: UUID
    invitation_status: InvitationStatus
    email_delivery_status: OutboxStatus
    expires_at: datetime


class InvitationValidationRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class InvitationValidationResponse(BaseModel):
    company_name: str
    invited_name: str
    email_masked: str
    role: CompanyRole
    expires_at: datetime


class AcceptInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)


class AcceptInvitationResponse(BaseModel):
    accepted: bool
    company_id: UUID
    company_name: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class InvitationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    company_name: str
    invited_name: str
    email: str
    intended_role: CompanyRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


class CompanyOnboardingSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: CompanyStatus
    created_at: datetime
    activated_at: datetime | None
    invitations: list[InvitationSummaryResponse]


class ResendInvitationResponse(BaseModel):
    invitation_id: UUID
    email_delivery_status: OutboxStatus
    expires_at: datetime


class RevokeInvitationResponse(BaseModel):
    invitation_id: UUID
    status: InvitationStatus
