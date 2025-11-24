# Google OAuth Setup Guide

This guide will help you set up Google OAuth login for Motivora Studio.

## Prerequisites

- A Google Cloud Platform (GCP) account
- Access to the Google Cloud Console

## Step 1: Create OAuth 2.0 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** > **Credentials**
4. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
5. If prompted, configure the OAuth consent screen:
   - Choose **External** (for testing) or **Internal** (for workspace)
   - Fill in the required fields:
     - App name: `Motivora Studio`
     - User support email: Your email
     - Developer contact: Your email
   - Add scopes:
     - `.../auth/userinfo.email`
     - `.../auth/userinfo.profile`
     - `openid`
   - Save and continue through the remaining steps
6. Create OAuth client ID:
   - Application type: **Web application**
   - Name: `Motivora Studio Web`
   - Authorized JavaScript origins:
     - For local development: `http://localhost:8888`
     - For production: `https://yourdomain.com`
   - Authorized redirect URIs:
     - For local development: `http://localhost:8888/auth/google/callback`
     - For production: `https://yourdomain.com/auth/google/callback`
7. Click **Create**
8. Copy the **Client ID** and **Client Secret**

## Step 2: Configure Environment Variables

Add the following environment variables to your `.env` file or set them in your environment:

```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret-here

# Optional: Explicit redirect URI (will be auto-detected if not set)
GOOGLE_REDIRECT_URI=http://localhost:8888/auth/google/callback  # For local dev
# GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback  # For production
```

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

The required packages (`google-auth`, `google-auth-oauthlib`, `requests`) are already in `requirements.txt`.

## Step 4: Update Database Schema

If you already have a database, you'll need to migrate it to add the `google_id` field and make `password_hash` nullable:

```bash
python3 -c "from server import app, db; from models import User; app.app_context().push(); db.create_all()"
```

Or delete the existing database file (`motivora.db`) to start fresh.

## Step 5: Test Google Login

1. Start your server:
   ```bash
   python3 server.py
   ```

2. Navigate to the login/signup page
3. You should see a "Sign in with Google" button
4. Click it and complete the Google authentication flow
5. You should be redirected back and logged in

## Troubleshooting

### "Google login is not configured"
- Make sure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set in your environment
- Check that the packages are installed: `pip list | grep google-auth`

### "redirect_uri_mismatch" error
- Ensure the redirect URI in Google Cloud Console exactly matches:
  - Local: `http://localhost:8888/auth/google/callback`
  - Production: `https://yourdomain.com/auth/google/callback`
- The URI must match exactly, including the protocol (http/https) and port

### "invalid_state" error
- This usually means the session expired. Try again.

### Button doesn't appear
- Check that `GOOGLE_OAUTH_ENABLED` is `True` in the server logs
- Verify environment variables are loaded correctly

## Security Notes

- Never commit your `GOOGLE_CLIENT_SECRET` to version control
- Use environment variables or a secrets manager in production
- The `google_id` field links Google accounts to your user accounts
- Users can link their Google account to an existing email-based account if the emails match

## Production Deployment

1. Update the OAuth consent screen to **Published** status (may require verification)
2. Update authorized JavaScript origins and redirect URIs in Google Cloud Console
3. Set `GOOGLE_REDIRECT_URI` to your production URL
4. Ensure HTTPS is enabled for your production domain
5. Update the redirect URI environment variable to use `https://`


