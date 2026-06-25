# JWT and Magic Link Authentication Architecture

The Open-Source Contribution Atelier uses JSON Web Tokens (JWT) for secure, stateless authentication. The platform is configured using `rest_framework_simplejwt` to provide secure access and refresh tokens.

In addition to traditional password-based authentication, the platform supports **Passwordless Magic Link Login**.

## Magic Link Authentication Architecture
The Magic Link authentication provides a secure, passwordless login flow by verifying the user's access to their registered email address.
1. The user requests a magic link by submitting their email address.
2. The backend generates a cryptographically secure, single-use `MagicLinkToken` mapped to the user.
3. An email containing a secure login link with the embedded token is dispatched.
4. When the user clicks the link, the frontend extracts the token and sends it to the verification endpoint.
5. If the token is valid, unused, and unexpired, the backend marks it as used and issues JWT access and refresh tokens.

## Magic Link API Endpoints

### Request Magic Link
**POST** `/api/auth/magic-link/request/`
**Payload:**
```json
{
  "email": "user@example.com"
}
```
**Success Response (200 OK):**
```json
{
  "message": "If an account with that email exists, a magic login link has been sent."
}
```

### Verify Magic Link
**POST** `/api/auth/magic-link/verify/`
**Payload:**
```json
{
  "token": "123e4567-e89b-12d3-a456-426614174000"
}
```
**Success Response (200 OK):**
```json
{
  "refresh": "eyJhbGciOiJIUzI1...",
  "access": "eyJhbGciOiJIUzI1...",
  "user": {
    "username": "user",
    "email": "user@example.com",
    "is_staff": false
  },
  "message": "You have been successfully logged in."
}
```

## Email Service Configuration
Magic link emails are dispatched asynchronously using Celery via `send_magic_link_email_task`.
The default backend is `django.core.mail.backends.console.EmailBackend` for development. In production, configure an SMTP backend via the `EMAIL_BACKEND` environment variable.

## Token Lifecycle and Expiration Policies
- **Access Tokens**: Short-lived tokens used to authenticate requests to protected API endpoints. By default, they expire after **30 minutes** (configurable via `ACCESS_TOKEN_LIFETIME_MINUTES`).
- **Refresh Tokens**: Long-lived tokens used to securely obtain new access tokens without requiring the user to re-authenticate. By default, they expire after **7 days** (configurable via `REFRESH_TOKEN_LIFETIME_DAYS`).
- **Refresh Token Rotation**: When a valid refresh token is submitted to the `/api/auth/refresh/` endpoint, a *new* access token and a *new* refresh token are issued. The previously used refresh token is immediately blacklisted.
- **Magic Link Tokens**: Single-use tokens that expire after **15 minutes** (configurable via `MAGIC_LINK_TIMEOUT_MINUTES`). Once successfully verified, the token is permanently marked as used.

## Security Considerations
1. **Refresh Token Rotation & Blacklisting**: We have enabled rotation and blacklisting (`ROTATE_REFRESH_TOKENS=True` and `BLACKLIST_AFTER_ROTATION=True`).
2. **Token Storage**: Client applications should never store tokens in LocalStorage if they are vulnerable to XSS. Prefer secure HttpOnly cookies or secure memory storage where possible.
3. **No Revocation Lists for Access Tokens**: Because access tokens are stateless and short-lived, they cannot be individually revoked before expiration.
4. **Magic Link Security**:
   - Tokens are cryptographically secure (`uuid.uuid4`).
   - Tokens are single-use (`is_used` boolean flag).
   - Rate limits are applied to prevent email bombing (`3/minute` for request, `5/minute` for verify).
   - Generic responses are used for the request endpoint to prevent email enumeration attacks.

## Guidelines for Extending Passwordless Authentication
- When introducing new passwordless mechanisms (e.g., OTP via SMS), use the existing token generation and verification architecture as a baseline.
- Extract common token validation logic (checking expiration, usage status) into reusable model mixins or service classes.
- Ensure any new endpoint maintains strict rate limiting to prevent brute-forcing.

## Integration Examples for Client Applications

### Intercepting 401 Responses (Axios / JavaScript)
When an API call fails with a `401 Unauthorized` status (indicating an expired access token), the client should automatically attempt to refresh the session.

```javascript
import axios from 'axios';

const api = axios.create({ baseURL: 'https://api.atelier.dev' });

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // If the error is 401 and we haven't already retried this request
    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = getStoredRefreshToken(); // e.g. from secure storage
      
      try {
        const { data } = await axios.post('https://api.atelier.dev/api/auth/refresh/', {
          refresh: refreshToken
        });
        
        // Store the new tokens (rotation)
        storeAccessToken(data.access);
        storeRefreshToken(data.refresh);
        
        // Retry the original request with the new access token
        originalRequest.headers['Authorization'] = `Bearer ${data.access}`;
        return api(originalRequest);
        
      } catch (refreshError) {
        // The refresh token is invalid or expired. Force logout.
        logoutUser();
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);
```
