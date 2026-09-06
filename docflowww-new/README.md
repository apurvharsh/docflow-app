# DocFlow AI

A full-stack document-workflow app: this React UI + a FastAPI backend
(merged in from the earlier DocFlow RAG prototype). The production-style local
runtime serves both the React UI and API from one FastAPI server.

**What's included**

- Email/password **and Google sign-in**, plus an instant no-signup demo login
- Projects with per-project document Sources, an AI Assistant chat, and a
  drafting Studio, laid out exactly like this UI's original 3-column design
- Document upload → text extraction (PDF/DOCX/DOC/PPTX/PPT/TXT/MD/JSON) →
  chunking → hybrid dense+sparse RAG indexing (Gemini + Qdrant)
- An **AI Assistant** chat that answers questions grounded in your uploaded
  documents, with cited sources
- A **Drafting Agent** (Studio → template card) that turns instructions into
  a structured first draft, plus a **Scanner Agent** that scores drafts
  against a structure/completeness/labeling rubric and can auto-revise ones
  that don't pass
- A **Gap-Detection Agent** ("Analyze Gaps" button) that compares uploaded
  documents against expected SDLC-stage coverage
- Project-scoped **RBAC** (member / reviewer / admin) and **ABAC**
  (sensitivity clearance, team visibility, document approval workflow)
- An **Admin** dashboard: user directory & role assignment, pending-approval
  queue, audit log, and a live RBAC/ABAC policy simulator
- **Personal Notes**, private to each user

## Project layout

```
docflow-app/
├── src/            ← this React (Vite + Tailwind) UI
├── package.json    ← frontend scripts and the combined-server shortcut
├── .env            ← VITE_API_URL, points the UI at the backend
└── backend/        ← FastAPI + SQLite + Qdrant API (see backend/README.md)
    ├── app/
    ├── requirements.txt
    └── .env.example
```

## Running it in VS Code

The combined local server uses one terminal and one browser-facing port.

**Install backend dependencies once**
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # optional: add GEMINI_API_KEY, Google OAuth creds, etc.
cd ..
npm install
```

**Start the combined app**
```bash
npm run dev
```

Then open your configured app host (for example, `https://your-domain.example.com`). The combined server serves the UI and API from the same origin, so the browser-facing API endpoints are `/docs`, `/openapi.json`, and `/health`.

### Fastest way to try it

Click **"Try the demo"** on the login screen — no signup, no API keys
required. You'll be logged in with full admin access. Document Q&A (`/ask`,
`/search`) needs a `GEMINI_API_KEY` in `backend/.env`; everything else
(projects, uploads, RBAC, admin, notes, the Scanner Agent's rubric scoring)
works without any keys at all.

## Setting up Google Sign-In

1. In Google Cloud Console, create an **OAuth 2.0 Client ID** (Web application).
2. Add this **Authorized redirect URI** exactly:
   `https://your-domain.example.com/api/auth/google/callback`
3. Put the client ID/secret in `backend/.env`:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REDIRECT_URI=https://your-domain.example.com/api/auth/google/callback
   FRONTEND_URL=https://your-domain.example.com
   ```
4. Restart the backend. "Continue with Google" on the login page will now work:
   it redirects to Google (via the internal backend), then Google redirects
   back through the frontend host, which verifies the identity and redirects
   the browser to `https://your-domain.example.com/?auth_token=...` — the frontend picks up that
   token automatically and logs you in.

## Email notifications

Project access assignment and removal emails are optional and use SMTP. Add
these settings to `backend/.env`, then restart the server:

```env
EMAIL_NOTIFICATIONS_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-provider-app-password
SMTP_USE_TLS=true
EMAIL_FROM=your-email@example.com
```

For Gmail, use an App Password rather than your normal account password.
Recipient addresses come from each user's signup/login email.

## Notes / known limitations

- SQLite + local on-disk Qdrant storage — fine for local dev/demo, not for
  multi-instance production deployment.
- The Drafting/Scanner agents use Agno + Groq when `GROQ_API_KEY` is set;
  without it they fall back to a deterministic template/rubric
  implementation, so nothing is required to try them.
- See `backend/README.md` for the full endpoint list and a map of which file
  implements which feature.
