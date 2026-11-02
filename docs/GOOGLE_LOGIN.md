# Sign in with Google — setup & troubleshooting

This guide covers the "Continue with Google" flow used on the Login, Signup and Landing pages:

```
Browser (Google popup)  →  frontend /api/auth/google/  →  backend GoogleLoginView
                                                        →  verify with Google
                                                        →  create/link account
                                                        →  issue JWT access + refresh tokens
```

## 1) Create a Google OAuth client (required)

Google Sign-In will not work with the hardcoded placeholder client ID unless you register your own OAuth client and authorize the origins your app runs on.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. **APIs & Services → OAuth consent screen**: configure it (support email, app name). For local testing you can keep it in "Testing" mode and add your own Google account as a test user.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**.
   - Application type: **Web application**.
   - Name: e.g. `Atelier (localhost)`.
   - **Authorized JavaScript origins**: add `http://localhost:5173` (and your production domain, e.g. `https://atelier.example.com`).
   - **Authorized redirect URIs**: only needed if you use the authorization-code flow; add `http://localhost:5173` (and prod) in that case.
5. Copy the **Client ID** and (for auth-code flow) the **Client secret**.

## 2) Configure environment variables

### Frontend (`frontend/.env`)

```env
# Must match the backend's GOOGLE_CLIENT_ID exactly (audience check).
VITE_GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com

# "implicit" (default): popup returns an access token; no backend secret needed.
# "auth-code": popup returns an authorization code the backend exchanges;
#              requires GOOGLE_CLIENT_SECRET on the backend.
VITE_GOOGLE_OAUTH_FLOW=implicit

# Backend address (same-origin /api works in dev via the Vite proxy).
VITE_API_BASE_URL=http://localhost:8000/api
```

### Backend (`backend/.env`)

```env
# Must match VITE_GOOGLE_CLIENT_ID exactly.
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com

# Required ONLY for VITE_GOOGLE_OAUTH_FLOW=auth-code.
GOOGLE_CLIENT_SECRET=YOUR_CLIENT_SECRET
```

The defaults shipped in `.env.example` are a placeholder client ID — they will **not** pass Google's audience verification unless you register that exact client in Google Cloud Console. Always override both sides with your own client ID.

> **Key rule:** `VITE_GOOGLE_CLIENT_ID` (frontend) and `GOOGLE_CLIENT_ID` (backend) must be identical, otherwise every ID-token/access-token audience check fails with `google_audience_mismatch`.

## 3) How the two flows differ

| Flow | Frontend setting | Backend requirement | When to use |
|------|------------------|---------------------|-------------|
| **implicit** (default) | `VITE_GOOGLE_OAUTH_FLOW=implicit` | None beyond `GOOGLE_CLIENT_ID` | Local dev and most deployments. Simplest — no client secret. |
| **auth-code** | `VITE_GOOGLE_OAUTH_FLOW=auth-code` | `GOOGLE_CLIENT_SECRET` must be set | When you need the backend to exchange a code (e.g. stricter token handling). Also requires authorized redirect URIs in Google Cloud Console. |

## 4) Troubleshooting

The backend returns a machine-readable `code` with every failure. The frontend turns it into a user-facing message. Match what you see:

| Error you see | Likely cause | Fix |
|---------------|--------------|-----|
| `google_audience_mismatch` | Frontend and backend client IDs differ. | Set `VITE_GOOGLE_CLIENT_ID` == `GOOGLE_CLIENT_ID`. |
| `google_oauth_not_configured` | Using `auth-code` flow but `GOOGLE_CLIENT_SECRET` is missing on the backend. | Set the secret, or switch to `VITE_GOOGLE_OAUTH_FLOW=implicit`. |
| `google_email_unverified` | The Google account's email isn't verified (and `DEBUG=False`). | Verify the email with Google, then retry. |
| `google_no_email` | Google didn't return an email (scope missing). | Request the `email` scope (`openid email profile` is already configured). |
| `google_token_invalid` / `google_code_rejected` | Token expired, revoked, or issued to another client. | Re-click "Continue with Google" to get a fresh token. |
| `google_unreachable` | Backend couldn't reach Google's tokeninfo/userinfo endpoints. | Check network / firewall; retry. |
| `Could not reach the API…` / `VITE_API_BASE_URL` | Frontend can't reach `/api/auth/google/`. | Start the backend, set `VITE_API_BASE_URL`, or rely on the dev proxy (`/api` → `127.0.0.1:8000`). |
| Popup closes immediately / "could not start" | Browser blocked the popup, or `VITE_GOOGLE_CLIENT_ID` isn't an authorized JS origin in Google Cloud Console. | Allow popups for the site; add `http://localhost:5173` to Authorized JavaScript Origins. |
| No error, but not logged in | The server returned tokens but `login()` requires both `access` and `refresh`. | Confirm the backend response contains both tokens; check the Network tab. |

### Quick checklist

- [ ] Google Cloud Console OAuth client created (Web application).
- [ ] `http://localhost:5173` added to Authorized JavaScript Origins.
- [ ] `VITE_GOOGLE_CLIENT_ID` == backend `GOOGLE_CLIENT_ID`.
- [ ] `GOOGLE_CLIENT_SECRET` set if using `VITE_GOOGLE_OAUTH_FLOW=auth-code`.
- [ ] Backend running and reachable at `VITE_API_BASE_URL` (or dev proxy active).
- [ ] Test Google account is added as a Test User if the consent screen is in Testing mode.

## 5) Related

- `backend/apps/accounts/views.py` — `GoogleLoginView`
- `frontend/src/lib/googleOAuth.ts` — frontend OAuth helpers
- `frontend/src/pages/LoginPage.tsx`, `SignupPage.tsx`, `LandingPage.tsx` — Google sign-in buttons
- `docs/AUTHENTICATION.md` — JWT & auth architecture
