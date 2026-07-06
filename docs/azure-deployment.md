# Deploying reels to Azure

This describes moving the whole stack (backend, frontend, database, LLM, and
auth) to Azure. Nothing here is Azure-exclusive — the app still runs locally on
docker-compose — but these are the pieces that light up in a cloud deployment.

## Components

| Piece      | Azure service                                   | How it's wired |
|------------|-------------------------------------------------|----------------|
| Backend    | Azure Container Apps or App Service (container)  | Build `reels-be/Dockerfile`, expose `:8000` |
| Frontend   | Azure Static Web Apps or Container Apps          | Build `reels-fe/Dockerfile`; set `VITE_API_BASE_URL` to the backend URL |
| Database   | Azure Database for PostgreSQL (Flexible Server)  | `DATABASE_URL` + `DB_SSLMODE=require` |
| LLM        | Azure OpenAI / Azure AI Foundry                  | `MODEL_PROVIDER=azure_openai` + endpoint/key/deployment |
| Auth       | Microsoft Entra ID (Azure AD) SSO                | `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `ADMIN_EMAILS` |

## 1. Database — Azure Database for PostgreSQL

The backend already speaks Postgres via `psycopg2`. Azure's managed Postgres
mandates TLS and drops idle connections, both of which are handled by config:

```
DATABASE_URL=postgresql+psycopg2://<user>:<password>@<server>.postgres.database.azure.com:5432/reels
DB_SSLMODE=require       # psycopg2 sslmode; required by Azure
DB_POOL_PRE_PING=true    # default; transparently replaces dropped connections
```

Schema is created/migrated on boot (`app.db.migrate()` / `entrypoint.sh`), so no
manual migration step is needed. `create_all` plus the in-place
`ALTER TABLE ... ADD COLUMN` healers use plain SQL types that Postgres accepts.

## 2. LLM — Azure OpenAI / Azure AI Foundry

Set `MODEL_PROVIDER=azure_openai` to call an Azure OpenAI (Azure AI Foundry)
deployment directly. Provide the resource endpoint, key, and the *deployment*
name you created in the portal (the deployment selects the model):

```
MODEL_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT=<deployment name>
AZURE_OPENAI_API_VERSION=2024-12-01-preview   # optional; this is the default
```

This hits the same REST endpoint the `openai.AzureOpenAI` client uses
(`{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=…`
with the `api-key` header), so no extra SDK dependency is pulled in.

### Alternative: Azure Function gateway

Instead, set `MODEL_PROVIDER=azure_function` to route summarisation/explanation
through an HTTP-triggered Azure Function that fronts your model of choice.

Contract the function must implement:

- **Request** (`POST`, `application/json`): `{ "task": "summarize" | "explain", "system": "<system prompt>", "prompt": "<user prompt>" }`, with the Azure Functions key in the `x-functions-key` header.
- **Response**: JSON `{ "content": "<model text>" }` (also accepts `text`/`output`/`result`, or a plain-text body).

For `explain`, the function should return a JSON object as text
(`{"short","long","technical","category"}`); the backend tolerates fenced or
noisy output.

```
MODEL_PROVIDER=azure_function
AZURE_FUNCTION_URL=https://<app>.azurewebsites.net/api/llm
AZURE_FUNCTION_KEY=<functions key>
```

## 3. Auth — Entra ID SSO with a password fallback

Users are managed by SSO. Register a SPA app in Entra ID and configure:

```
SSO_ENABLED=true
AZURE_TENANT_ID=<tenant guid>
AZURE_CLIENT_ID=<app registration client id>
ADMIN_EMAILS=alice@corp.com,bob@corp.com   # these users get admin
PASSWORD_AUTH_ENABLED=false                 # disable the legacy fallback in prod
```

- The frontend calls `GET /api/auth/config`, then redirects to Entra's authorize
  endpoint and posts the returned access token to `POST /api/auth/sso`.
- The backend resolves the token via the OIDC userinfo endpoint
  (`SSO_USERINFO_URL`, default Microsoft Graph) and grants **admin** to anyone in
  `ADMIN_EMAILS`; everyone else who signs in is a non-admin user.
- Set `PASSWORD_AUTH_ENABLED=true` to re-enable the name + `ADMIN_PASSWORD`
  fallback (handy locally, or if SSO is unavailable). Both methods can be on at
  once; the login screen shows whichever are enabled.

In the SPA app registration, add the frontend origin as a redirect URI and
enable the implicit **access token** grant (or swap the dependency-free client in
`reels-fe/src/sso.ts` for `@azure/msal-browser` auth-code + PKCE — the backend
contract is unchanged).

## 4. CORS

Point the backend at the deployed frontend origin:

```
CORS_ORIGINS=https://<your-frontend-host>
```
