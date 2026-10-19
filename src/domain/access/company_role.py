from enum import Enum


class CompanyRole(str, Enum):
    COMPANY_ADMIN = "COMPANY_ADMIN"
    AGENT_EDITOR = "AGENT_EDITOR"
