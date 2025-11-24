# Fix OAuth Client Type - Desktop → Web Application

## Issue

Your OAuth client is set to **"Desktop"** type, but your Flask app needs a **"Web application"** type.

## Why This Matters

- **Desktop** clients are for native apps (Electron, mobile apps)
- **Web application** clients are for web apps (Flask, web browsers)
- Different redirect URI handling
- Different authentication flow

## Solution: Create New Web Application Client

Since you want everything on your Motivora Studio email, let's create a proper Web application client:

### Step 1: Create New OAuth Client (2 minutes)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Credentials**
3. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
4. If prompted, configure OAuth consent screen:
   - **App name**: `Motivora Studio` (singular, not "Studios")
   - **User support email**: Your Motivora Studio email
   - **Developer contact**: Your Motivora Studio email
   - Add scopes: `userinfo.email`, `userinfo.profile`, `openid`
   - Save and continue

5. **Create OAuth client ID:**
   - **Application type**: Select **"Web application"** (NOT Desktop!)
   - **Name**: `Motivora Studio Web`
   - **Authorized JavaScript origins**:
     - `http://localhost:8888` (for local development)
     - `https://yourdomain.com` (for production - add when ready)
   - **Authorized redirect URIs**:
     - `http://localhost:8888/auth/google/callback` (for local development)
     - `https://yourdomain.com/auth/google/callback` (for production - add when ready)
   - Click **CREATE**

6. **Copy the new credentials:**
   - Copy the **Client ID**
   - Copy the **Client Secret**

### Step 2: Update Your .env File

Replace the old credentials with the new Web application credentials.

### Step 3: Delete or Disable Old Desktop Client (Optional)

You can keep the Desktop client for your Electron app later, or delete it if you only need web.

---

## Alternative: Keep Desktop Client for Electron

If you plan to use Google OAuth in your Electron desktop app later, you can:
- Keep the Desktop client for Electron
- Create a separate Web application client for the Flask web app
- Use different credentials for each

---

## Quick Checklist

- [ ] OAuth consent screen uses Motivora Studio email ✅
- [ ] Created new **Web application** OAuth client
- [ ] Added redirect URIs (localhost + production)
- [ ] Updated .env file with new credentials
- [ ] Tested Google login works

---

## What You'll Have

After this:
- ✅ Everything on Motivora Studio email (not personal)
- ✅ Proper Web application client for Flask
- ✅ Desktop client available for Electron app (if needed)
- ✅ Clean separation of business/personal



