# ReviewPilot Production Deployment Guide

This guide details the step-by-step instructions for deploying ReviewPilot to production without Docker or Kubernetes, utilizing cloud-hosted services (Render, Vercel, Supabase, and Qdrant Cloud).

---

## 1. Cloud Infrastructure Accounts
Before starting, ensure you have accounts with the following providers:
1.  **GitHub**: To host the repository and handle OAuth login.
2.  **Supabase**: For hosting the PostgreSQL database.
3.  **Qdrant Cloud**: For hosting the semantic Vector database.
4.  **Render**: For hosting the FastAPI backend.
5.  **Vercel**: For hosting the Next.js frontend.

---

## 2. Step-by-Step Deployment Guide

### Step 2.1: Supabase Database Setup
1.  Sign in to **Supabase** and create a new project named `ReviewPilot`.
2.  Set a strong database password and choose a region close to your Render hosting.
3.  Navigate to **Project Settings > Database** and copy the URI under **Connection string > URI** (Choose the transaction pooler `Session` mode on port 5432 or direct link, depending on preferences).
    *   Form: `postgresql://postgres.[username]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres`
    *   Make sure to replace the placeholder password with your actual password.

### Step 2.2: Qdrant Cloud Setup
1.  Sign in to **Qdrant Cloud** and create a free tier cluster named `reviewpilot-vectors`.
2.  Wait for the cluster provisioning to complete.
3.  Copy the cluster **Endpoint URL** (e.g. `https://xxx-yyyy-zzz.aws.qdrant.io:6333`).
4.  Navigate to **API Keys** and generate a new read-write token. Copy this API key.

### Step 2.3: GitHub App Configuration
To enable PR comments and webhooks:
1.  Go to your GitHub Account **Settings > Developer Settings > GitHub Apps** and click **New GitHub App**.
2.  Provide a name, and set the **Homepage URL** to your planned Vercel URL.
3.  Set the **Webhook URL** to your planned Render Backend URL endpoint (e.g. `https://reviewpilot-backend.onrender.com/api/v1/webhooks`).
4.  Specify a random **Webhook Secret** string (and save it).
5.  Under **Permissions**, enable:
    *   Repository: **Pull Requests** (Read & Write)
    *   Repository: **Checks** (Read & Write)
    *   Repository: **Commit statuses** (Read & Write)
    *   Repository: **Contents** (Read & Write)
    *   Repository: **Metadata** (Read-only)
6.  Under **Events**, subscribe to **Pull request** events.
7.  Generate a **Private Key** under client settings. Download the PEM key file.
8.  Go to **OAuth Credentials** of the App, copy the **Client ID**, and generate a **Client Secret**.

### Step 2.4: Render Backend Deployment (FastAPI)
1.  Sign in to **Render** and click **New > Blueprint**.
2.  Connect your GitHub repository containing the ReviewPilot files.
3.  Render will parse `render.yaml` from the root directory and configure the environment.
4.  Apply the blueprint. Render will ask you to input the environment variables. Ensure the variables match the required settings in the settings section below.

### Step 2.5: Vercel Frontend Deployment (Next.js)
1.  Sign in to **Vercel** and click **Add New > Project**.
2.  Import your GitHub repository.
3.  Configure:
    *   **Root Directory**: `frontend`
    *   **Framework Preset**: Next.js
4.  Add the environment variables (e.g., `NEXT_PUBLIC_API_URL` pointing to the Render backend URL).
5.  Click **Deploy**.

---

## 3. Environment Variable Setup

### FastAPI Backend (Render)
Configure the following inside Render Web Service **Environment**:

| Variable Key | Sample / Form Value | Description |
| :--- | :--- | :--- |
| `SQLALCHEMY_DATABASE_URI` | `postgresql+asyncpg://postgres...` | Connection URL using `asyncpg` |
| `SQLALCHEMY_SYNC_DATABASE_URI` | `postgresql://postgres...` | Connection URL for sync operations (Alembic) |
| `JWT_SECRET_KEY` | `your_secret_signing_key` | Secret string for token authorization |
| `ENCRYPTION_KEY` | `32_byte_base64_encryption_key` | Fernet key used for token storage protection |
| `GITHUB_CLIENT_ID` | `Iv1.xxxxxxxxxxxx` | GitHub OAuth client identification token |
| `GITHUB_CLIENT_SECRET` | `xxxxxxxxxxxxxxxx` | GitHub OAuth security client key |
| `GITHUB_APP_ID` | `123456` | Main App ID of the configured GitHub App |
| `GITHUB_WEBHOOK_SECRET` | `webhook_secret_here` | Secret verifying webhook triggers |
| `GITHUB_PRIVATE_KEY` | `-----BEGIN RSA PRIVATE KEY-----...` | Private key PEM content parsed as string |
| `QDRANT_URL` | `https://xxx.aws.qdrant.io:6333` | Cloud cluster endpoint of Qdrant Vector DB |
| `QDRANT_API_KEY` | `xxxxxxxxxxxxxx` | API token validating Qdrant access |
| `GROQ_API_KEY` | `gsk_xxxxxxxxxxxxxx` | Llama API key validation |
| `GROQ_MODEL` | `llama3-70b-8192` | Core LLM model choice |
| `BACKEND_CORS_ORIGINS` | `https://your-vercel-domain.vercel.app` | Origins permitted for frontend dashboard access |
| `FRONTEND_URL` | `https://your-frontend-domain.netlify.app` | Frontend URL for OAuth callback redirect after GitHub login |

### Next.js Frontend (Vercel)
Configure the following inside Vercel Project **Settings > Environment Variables**:

| Variable Key | Value | Description |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `https://reviewpilot-backend.onrender.com/api/v1` | Public API endpoint of your Render backend |

---

## 4. SSL Configuration
*   **Render Backend**: Render automatically provisions and renews Let's Encrypt SSL certificates for all web services out of the box. No manual intervention is needed. Secure `https` endpoints are mapped immediately.
*   **Vercel Frontend**: Vercel handles SSL certificates automatically for all custom domains and `vercel.app` domains. Direct HTTPS encryption is enforced by default.

---

## 5. Monitoring Setup
1.  **Render Dashboard Metrics**: Navigate to your service in the Render panel. The **Metrics** tab displays real-time CPU utilization, RAM usage, and bandwidth charts.
2.  **Health Checks**: Render utilizes the `/health` endpoint configured on the web service to execute periodical checks. If a service becomes unresponsive, Render restarts it automatically.
3.  **Vercel Web Vitals**: In the Vercel dashboard, enable **Analytics** and **Speed Insights** to monitor real-time user metrics, TTFB, and layout shifts.
4.  **Error Tracking (Optional)**: Set up Sentry (`sentry-sdk` for Python, `@sentry/nextjs` for Next.js) by setting the `SENTRY_DSN` env variables to trace production bugs automatically.

---

## 6. Backup Strategy
*   **PostgreSQL (Supabase)**: Supabase runs automatic daily database backups containing schema and values. For premium plans, Point-In-Time recovery is enabled. Manual sql backups can be extracted via:
    `pg_dump -h aws-0-us-west-1.pooler.supabase.com -U postgres.username -d postgres > backup.sql`
*   **Vector Database (Qdrant)**: Guidelines stored in Qdrant can be re-seeded at any time by triggering the sync command inside the Settings page of the dashboard. Thus, vector storage is safely rebuildable from the database.

---

## 7. Rollback Strategy
*   **Render Web Service**: If a bug breaks the production backend, go to the Render web service panel, navigate to **Events**, click **Deploy**, and select a previous successful git commit hash. Render will instantly build and deploy that version.
*   **Vercel Frontend**: If a layout error occurs on the frontend, navigate to **Deployments** inside Vercel, select the previous successful build, click the options menu (`...`), and select **Rollback**. Vercel redirects traffic to the previous deployment immediately.
