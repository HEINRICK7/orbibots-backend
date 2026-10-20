from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.src.domain.entities.access.company_role import CompanyRole
from app.src.domain.dtos.company_onboarding import (
    AcceptedInvitation,
    InvitationAcceptanceContext,
    InvitationEmailJob,
)
from app.src.domain.entities.company_onboarding.errors import (
    CompanyOnboardingConflictError,
    InvalidCompanyOnboardingInputError,
    InvitationNotFoundError,
    InvitationStateError,
)
from app.src.domain.entities.company_onboarding.status import (
    AuditOutcome,
    CompanyStatus,
    InvitationStatus,
    MembershipStatus,
    OutboxStatus,
)
from app.src.domain.entities.company_onboarding.membership_scope import MembershipScope
from app.src.domain.entities.authentication.status import UserStatus
from app.src.domain.interfaces.gateways.company_onboarding import (
    CompanyOnboardingRepository,
    InvitationOutboxRepository,
)
from app.src.infra.adapters.persistence.company_onboarding_models import (
    AuditEvent,
    Company,
    Invitation,
    InvitationEmailOutbox,
    Membership,
)
from app.src.infra.adapters.persistence.authentication_models import UserRecord


class SqlAlchemyCompanyOnboardingRepository(
    CompanyOnboardingRepository,
    InvitationOutboxRepository,
):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_company(
        self, name: str, status: CompanyStatus, created_at: datetime
    ) -> UUID:
        company = Company(name=name, status=status, created_at=created_at)
        self._session.add(company)
        self._session.flush()
        return company.id

    def create_invitation(
        self,
        company_id: UUID,
        invited_name: str,
        email: str,
        phone: str | None,
        intended_role: CompanyRole,
        token_hash: str,
        status: InvitationStatus,
        expires_at: datetime,
        created_at: datetime,
    ) -> UUID:
        invitation = Invitation(
            company_id=company_id,
            invited_name=invited_name,
            email=email,
            phone=phone,
            intended_role=intended_role,
            token_hash=token_hash,
            status=status,
            expires_at=expires_at,
            created_at=created_at,
        )
        self._session.add(invitation)
        self._session.flush()
        return invitation.id

    def create_audit_event(
        self,
        actor_user_id: UUID | None,
        company_id: UUID | None,
        action: str,
        outcome: AuditOutcome,
    ) -> None:
        self._session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                company_id=company_id,
                action=action,
                outcome=outcome.value,
            )
        )
        self._session.flush()

    def create_invitation_outbox_event(
        self, invitation_id: UUID, created_at: datetime
    ) -> UUID:
        outbox_event = InvitationEmailOutbox(
            invitation_id=invitation_id,
            status=OutboxStatus.PENDING,
            next_attempt_at=created_at,
            created_at=created_at,
        )
        self._session.add(outbox_event)
        self._session.flush()
        return outbox_event.id

    def get_invitation_acceptance_context(
        self,
        token_hash: str,
        now: datetime,
    ) -> InvitationAcceptanceContext:
        invitation, company, user = self._load_invitation_acceptance(token_hash, now)
        return InvitationAcceptanceContext(
            invitation_id=invitation.id,
            company_id=company.id,
            company_name=company.name,
            invited_name=invitation.invited_name,
            email=invitation.email,
            expires_at=invitation.expires_at,
            requires_password_setup=user is None or user.password_hash is None,
        )

    def accept_invitation(
        self,
        token_hash: str,
        now: datetime,
        password_hash: str | None,
    ) -> AcceptedInvitation:
        invitation, company, user = self._load_invitation_acceptance(token_hash, now)
        if user is None:
            if password_hash is None:
                raise InvalidCompanyOnboardingInputError(
                    "A password is required to create the account."
                )
            user = UserRecord(
                name=invitation.invited_name,
                email=invitation.email,
                password_hash=password_hash,
                status=UserStatus.ACTIVE,
            )
            self._session.add(user)
            self._session.flush()
        elif user.password_hash is None:
            if password_hash is None:
                raise InvalidCompanyOnboardingInputError(
                    "A password is required to activate the account."
                )
            user.password_hash = password_hash

        active_membership = self._session.scalar(
            select(Membership)
            .where(
                Membership.company_id == company.id,
                Membership.user_id == user.id,
                Membership.status == MembershipStatus.ACTIVE,
            )
            .with_for_update()
        )
        if active_membership is not None:
            if CompanyRole(active_membership.role) is not CompanyRole.COMPANY_ADMIN:
                raise CompanyOnboardingConflictError(
                    "The user already has a different active role for this company."
                )
        else:
            self._session.add(
                Membership(
                    company_id=company.id,
                    user_id=user.id,
                    role=CompanyRole.COMPANY_ADMIN,
                    scope=MembershipScope.COMPANY,
                    status=MembershipStatus.ACTIVE,
                )
            )

        if CompanyStatus(company.status) is CompanyStatus.PENDING_ACTIVATION:
            company.status = CompanyStatus.ACTIVE
            company.activated_at = now
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = now
        self.create_audit_event(
            user.id,
            company.id,
            "invitation.accept",
            AuditOutcome.SUCCESS,
        )
        self._session.flush()
        return AcceptedInvitation(
            invitation_id=invitation.id,
            company_id=company.id,
            company_name=company.name,
            user_id=user.id,
        )

    def _load_invitation_acceptance(
        self,
        token_hash: str,
        now: datetime,
    ) -> tuple[Invitation, Company, UserRecord | None]:
        invitation = self._session.scalar(
            select(Invitation)
            .where(Invitation.token_hash == token_hash)
            .with_for_update()
        )
        if (
            invitation is None
            or InvitationStatus(invitation.status) is not InvitationStatus.PENDING
        ):
            raise InvitationNotFoundError()
        if _as_utc(invitation.expires_at) <= _as_utc(now):
            raise InvitationStateError()
        company = self._session.scalar(
            select(Company).where(Company.id == invitation.company_id).with_for_update()
        )
        if company is None or CompanyStatus(company.status) is CompanyStatus.SUSPENDED:
            raise InvitationStateError()
        user = self._session.scalar(
            select(UserRecord)
            .where(func.lower(UserRecord.email) == invitation.email.casefold())
            .with_for_update()
        )
        if user is not None and UserStatus(user.status) is not UserStatus.ACTIVE:
            raise InvitationStateError()
        return invitation, company, user

    def claim_invitation_email(
        self,
        outbox_id: UUID,
        now: datetime,
        stale_before: datetime,
        token_hash: str | None = None,
        expires_at: datetime | None = None,
    ) -> InvitationEmailJob | None:
        outbox = self._session.scalar(
            select(InvitationEmailOutbox)
            .where(InvitationEmailOutbox.id == outbox_id)
            .with_for_update()
        )
        if outbox is None:
            return None

        status = OutboxStatus(outbox.status)
        if status in {OutboxStatus.SENT, OutboxStatus.FAILED}:
            return None
        if (
            status is OutboxStatus.PENDING
            and _as_utc(outbox.next_attempt_at) > _as_utc(now)
        ):
            return None
        if (
            status is OutboxStatus.PROCESSING
            and outbox.claimed_at is not None
            and _as_utc(outbox.claimed_at) > _as_utc(stale_before)
        ):
            return None

        invitation = self._session.get(Invitation, outbox.invitation_id)
        if invitation is None or InvitationStatus(invitation.status) is not InvitationStatus.PENDING:
            outbox.status = OutboxStatus.FAILED
            self._session.flush()
            return None
        if _as_utc(invitation.expires_at) <= _as_utc(now):
            invitation.status = InvitationStatus.EXPIRED
            outbox.status = OutboxStatus.FAILED
            self._session.flush()
            return None

        if token_hash is not None and expires_at is not None:
            invitation.token_hash = token_hash
            invitation.expires_at = expires_at

        outbox.status = OutboxStatus.PROCESSING
        outbox.attempts += 1
        outbox.claimed_at = now
        outbox.next_attempt_at = now
        self._session.flush()
        company = self._session.get(Company, invitation.company_id)
        if company is None:
            outbox.status = OutboxStatus.FAILED
            self._session.flush()
            return None
        return InvitationEmailJob(
            outbox_id=outbox.id,
            invitation_id=invitation.id,
            company_name=company.name,
            invited_name=invitation.invited_name,
            email=invitation.email,
            status=OutboxStatus(outbox.status),
            attempts=outbox.attempts,
            expires_at=invitation.expires_at,
        )

    def mark_invitation_email_sent(self, outbox_id: UUID, delivered_at: datetime) -> None:
        outbox = self._session.get(InvitationEmailOutbox, outbox_id)
        if outbox is None or OutboxStatus(outbox.status) is OutboxStatus.SENT:
            return
        outbox.status = OutboxStatus.SENT
        outbox.delivered_at = delivered_at
        self._session.flush()

    def schedule_invitation_email_retry(
        self,
        outbox_id: UUID,
        attempted_at: datetime,
        retry_at: datetime,
    ) -> None:
        outbox = self._session.get(InvitationEmailOutbox, outbox_id)
        if outbox is None or OutboxStatus(outbox.status) is OutboxStatus.SENT:
            return
        outbox.status = OutboxStatus.PENDING
        outbox.claimed_at = None
        outbox.next_attempt_at = retry_at
        self._session.flush()

    def list_pending_invitation_emails(
        self,
        now: datetime,
        limit: int,
    ) -> tuple[UUID, ...]:
        stale_before = now - timedelta(minutes=5)
        ids = self._session.scalars(
            select(InvitationEmailOutbox.id)
            .where(
                or_(
                    and_(
                        InvitationEmailOutbox.status == OutboxStatus.PENDING,
                        InvitationEmailOutbox.next_attempt_at <= now,
                    ),
                    and_(
                        InvitationEmailOutbox.status == OutboxStatus.PROCESSING,
                        InvitationEmailOutbox.claimed_at <= stale_before,
                    ),
                )
            )
            .order_by(InvitationEmailOutbox.created_at)
            .limit(limit)
        ).all()
        return tuple(ids)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
