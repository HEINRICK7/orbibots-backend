# OrbiBots backend

## Database setup

The initial persistence layer uses PostgreSQL, SQLAlchemy models, and Alembic
migrations. `Company` is the tenant boundary; `MembershipScope` is a PostgreSQL
enum with the V1 values `COMPANY` and `ASSIGNED_AGENTS`.

Install the Python dependencies:

```powershell
.\venv\Scripts\python.exe -m pip install -r app/requirements.txt
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your PostgreSQL host, database, username, password, and
`DATABASE_URL`, then configure `APP_ENV` and `JWT_SECRET_KEY`. `.env` is ignored
by Git. Keep real credentials out of `.env.example` and encode special
characters in the URL password. The example signing key is for local
development only. For production, set a random key of at least 32 characters,
for example by running
`.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Run the API

In PowerShell, from the project root, install dependencies and create the local
environment file if it does not exist:

```powershell
.\venv\Scripts\python.exe -m pip install -r app/requirements.txt
Copy-Item .env.example .env
```

Edit `.env` if needed. Start PostgreSQL and apply database migrations:

```powershell
docker compose up -d --wait postgres
.\venv\Scripts\alembic.exe upgrade head
```

Start the development server:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.run:app --reload
```

The server is available at `http://127.0.0.1:8000`; interactive API
documentation is at `http://127.0.0.1:8000/docs`. Stop the development server
with Ctrl+C. Login is available at `POST /auth/login` with an email and
password; successful login returns a signed JWT bearer access token.
`GET /auth/me` demonstrates bearer token authentication. Production startup
requires `DATABASE_URL` and a `JWT_SECRET_KEY` of at least 32 characters. The
signing algorithm is HS256 and `ACCESS_TOKEN_EXPIRE_MINUTES` accepts values
from 1 to 1440.

The company invitation flow creates an account without setting a password and
returns a bearer session after the invite is accepted. Password-based login
after that session expires requires a separate password setup or recovery flow;
this repository does not currently expose that flow.

### Local development administrator

For a single local development administrator, set `BOOTSTRAP_ADMIN_EMAIL`,
`BOOTSTRAP_ADMIN_PASSWORD`, and `GLOBAL_ADMIN_ALLOWED_EMAILS` to the same email
in the ignored `.env` file. The password must contain at least 20 characters.
On API startup, the backend creates the account if it is missing and grants
global `ADMIN` only after validating the email against the allowlist. The
bootstrap flow does not replace an existing password. Do not use this
development bootstrap configuration in production.

## Initial company administrators

`COMPANY_ADMIN` is a company-scoped membership role. Global platform access is
separate: only users with global `ADMIN` may use routes protected by the
platform-administration dependency. A global role does not create or bypass
company memberships.

The migration adds nullable `users.global_role`, constrained to `ADMIN` or
`NULL`. For the initial company setup, set `INITIAL_COMPANY_NAME`, both
initial-admin names and emails, `GLOBAL_ADMIN_ALLOWED_EMAILS` to those exact
two email identities (comma separated), and two distinct passwords in the
ignored local `.env` file. The allowlist is trusted application configuration,
not a user-editable database setting. Downgrading the global-role migration
removes all role assignments; confirm the impact before rolling it back. Each
password must contain at least 20 characters. Generate a separate random
password for each user:

```powershell
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Keep passwords out of chat, Git, migration files, and command-line arguments.
Run the explicit provisioning command after PostgreSQL is running and the
Alembic migrations have been applied:

```powershell
.\venv\Scripts\python.exe -m app.src.infra.setup.initial_admins
```

The command creates the company as `ACTIVE`, creates missing users with
Argon2 password hashes, assigns active `COMPANY_ADMIN` memberships, and grants
global `ADMIN` only to the two allowlisted identities. The allowlist must
contain exactly two distinct valid email addresses and match the initial
account identities; otherwise provisioning fails before database changes.
Provisioning is safe to rerun: existing accounts are not given new passwords,
and conflicting inactive accounts or memberships cause an explicit error.

## Company onboarding by invitation

Company onboarding is available under `/company-onboarding`:

- `POST /company-onboarding/companies` lets a global `ADMIN` create a pending
  company and invite its first `COMPANY_ADMIN`. It returns the company and
  invitation IDs and the outbox delivery state; it never returns the invitation
  token.
- `GET /company-onboarding/companies` lists companies and their invitation
  summaries for the global `ADMIN` console. It returns canonical company and
  invitation statuses without invitation tokens, hashes, or outbox data.
- `GET /company-onboarding/companies/{company_id}/invitations`, plus `POST`
  `/company-onboarding/invitations/{invitation_id}/resend` and `/revoke`, require
  a global `ADMIN`.
- `POST /company-onboarding/public/invitations/validate` accepts the invitation
  token in the JSON body and returns the company, invitee name, masked email,
  and expiry.
- `POST /company-onboarding/public/invitations/accept` accepts the same one-time
  token, activates the company membership, and returns a short-lived bearer
  access token. The invitation token itself is never returned. New users do not
  set a password during acceptance; they can use the returned session to enter
  their company.

Configure `COMPANY_INVITATION_URL`, `SMTP_HOST`, and `EMAIL_FROM` to deliver
invitation emails. `SMTP_USERNAME` and `SMTP_PASSWORD` are optional together;
port 465 uses implicit TLS and other ports use STARTTLS. Delivery uses a
transactional outbox with retries. SMTP is optional in development and tests,
but required in staging and production, where the invitation URL must use
HTTPS. The one-time invitation token is stored only as a hash and expires after
24 hours.

## Project layout

```text
orbibots-backend/
├── .github/
├── app/
│   ├── src/
│   │   ├── application/
│   │   │   ├── configuration/
│   │   │   ├── gateways/
│   │   │   └── usecases/
│   │   ├── domain/
│   │   │   ├── config/
│   │   │   ├── dtos/
│   │   │   ├── entities/
│   │   │   └── interfaces/
│   │   │       ├── adapters/
│   │   │       ├── gateways/
│   │   │       └── usecases/
│   │   └── infra/
│   │       ├── adapters/
│   │       ├── controllers/
│   │       ├── di/
│   │       ├── entrypoints/
│   │       ├── exceptions/
│   │       └── setup/
│   ├── tests/
│   │   ├── unitary/
│   │   │   ├── application/
│   │   │   ├── domain/
│   │   │   └── infra/
│   │   └── integration/
│   │       ├── api/
│   │       ├── health_check/
│   │       └── infrastructure/
│   ├── Dockerfile
│   ├── logging.conf
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── requirements_tests.txt
│   └── run.py
├── deploy/
├── migrations/
├── .dockerignore
├── .env.example
├── .gitignore
├── alembic.ini
├── docker-compose.yml
└── README.md
```

Dependencies point inward: `domain/` defines entities, DTOs, and interfaces;
`application/usecases/` implements those contracts and receives dependencies
through constructors. `infra/adapters/` contains SQLAlchemy, password hashing,
and token implementations. FastAPI controllers translate HTTP and call use
cases. `infra/di/` is the composition root and uses Punq to assemble
request-scoped dependencies, which can be replaced with mocks in tests.
`infra/exceptions/` maps known failures to HTTP statuses while keeping the
existing `{"detail": ...}` response shape. `infra/entrypoints/` creates the
ASGI app, exposed locally as `app.run:app`.

## Access roles

Global and company access are separate grants:

- `users.global_role = ADMIN` grants access to platform administration (`/admin`).
- An active `COMPANY_ADMIN` membership in an active company grants access only
  to that company's area (`/app`). `AGENT_EDITOR` is a company membership role,
  not a global administrator role.
- A global administrator is not automatically authorized for every company.
  A company-scoped operation must check the requested company against the user's
  active memberships.

`GET /auth/me` returns `global_role` and the active `company_accesses`. FastAPI
dependencies at the controller boundary call use cases in
`app/src/application/usecases/`; those use cases apply the rules in
`app/src/domain/entities/access/policy.py`. Attach `require_global_admin` to platform
operations and `require_company_admin` to company operations whose route
includes a `company_id`. The current backend has no administrative
business-operation routes yet; those routes must apply the appropriate
dependency when added. Frontend route guards control navigation only and do not
replace backend authorization.

Start the isolated PostgreSQL test database and wait for its health check:

```powershell
docker compose up -d --wait postgres
```

Compose, Alembic, and the integration tests load connection settings from
`.env`. Run migrations and the full suite:

```powershell
.\venv\Scripts\alembic.exe upgrade head
.\venv\Scripts\python.exe -m unittest discover -s app/tests -v
```
