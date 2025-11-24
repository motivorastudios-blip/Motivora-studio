# Update Google OAuth to Use Motivora Studio Email

## Quick Steps (5 minutes)

### Option 1: Update Existing OAuth Credentials (Recommended)

1. **Go to Google Cloud Console**
   - Visit: [console.cloud.google.com](https://console.cloud.google.com/)
   - Select your project

2. **Update OAuth Consent Screen**
   - Go to **APIs & Services** → **OAuth consent screen**
   - Click **EDIT APP**
   - Update these fields:
     - **User support email**: Change to `your-motivora-email@motivora.studio` (or your domain)
     - **Developer contact information**: Change to your Motivora Studio email
   - Click **SAVE AND CONTINUE** through all steps
   - Click **BACK TO DASHBOARD**

3. **Your existing Client ID and Secret still work!**
   - No need to create new credentials
   - Just update the email in the consent screen
   - Your current `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` will continue to work

### Option 2: Create New OAuth Credentials (Fresh Start)

If you want to create new credentials with the Motivora Studio email from scratch:

1. **Go to Google Cloud Console**
   - Visit: [console.cloud.google.com](https://console.cloud.google.com/)
   - Create a new project: "Motivora Studio" (or use existing)

2. **Set Up OAuth Consent Screen**
   - Go to **APIs & Services** → **OAuth consent screen**
   - Choose **External** (for public use)
   - Fill in:
     - **App name**: `Motivora Studio`
     - **User support email**: `your-email@motivora.studio` (your Motivora email)
     - **Developer contact information**: `your-email@motivora.studio`
     - **App logo**: Upload Motivora Studio logo (optional)
     - **App domain**: Your domain (e.g., `motivora.studio`)
     - **Authorized domains**: Add your domain
   - Add scopes:
     - `.../auth/userinfo.email`
     - `.../auth/userinfo.profile`
     - `openid`
   - Save and continue

3. **Create OAuth Client ID**
   - Go to **APIs & Services** → **Credentials**
   - Click **+ CREATE CREDENTIALS** → **OAuth client ID**
   - Application type: **Web application**
   - Name: `Motivora Studio Web`
   - Authorized JavaScript origins:
     - `http://localhost:8888` (for local dev)
     - `https://yourdomain.com` (for production)
   - Authorized redirect URIs:
     - `http://localhost:8888/auth/google/callback` (for local dev)
     - `https://yourdomain.com/auth/google/callback` (for production)
   - Click **CREATE**

4. **Copy New Credentials**
   - Copy the **Client ID** (looks like: `xxxxx.apps.googleusercontent.com`)
   - Copy the **Client Secret** (looks like: `GOCSPX-xxxxx`)

5. **Update Your .env File**
   ```bash
   GOOGLE_CLIENT_ID=your-new-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-new-client-secret
   ```

---

## What Email Address Should You Use?

**Recommended**: Use your Motivora Studio business email
- Example: `hello@motivora.studio` or `support@motivora.studio`
- This is what users will see when they authenticate
- This is where Google will send OAuth-related notifications

---

## Important Notes

### Email in OAuth Consent Screen
- This is the **support email** users see
- This is where Google sends OAuth notifications
- Should be a real, monitored email address

### Email in User Accounts
- The **user's email** (from their Google account) is what gets stored in your database
- This is separate from the OAuth consent screen email
- Users sign in with their own Google accounts

### No Code Changes Needed
- The code doesn't care what email is in the consent screen
- Only the Client ID and Secret matter for authentication
- You can update the consent screen email without changing code

---

## Verification Checklist

After updating:

- [ ] OAuth consent screen shows Motivora Studio email
- [ ] Client ID and Secret are in your `.env` file
- [ ] Redirect URIs match your app URLs
- [ ] Test Google login works
- [ ] Users see "Motivora Studio" when authenticating

---

## Testing

1. Restart your server:
   ```bash
   python3 server.py
   ```

2. Go to login page
3. Click "Sign in with Google"
4. You should see "Motivora Studio" in the Google consent screen
5. Complete authentication
6. Verify you're logged in

---

## Troubleshooting

### "redirect_uri_mismatch"
- Make sure redirect URIs in Google Console match exactly
- Include `http://` or `https://` and port number
- Check both local and production URLs are added

### "Access blocked: This app's request is invalid"
- OAuth consent screen might need to be published
- For testing, add test users in OAuth consent screen
- Go to **Test users** → **+ ADD USERS**

### Email Not Updating
- Changes to OAuth consent screen can take a few minutes
- Try clearing browser cache
- Make sure you saved all steps in the consent screen

---

## Production Notes

When going live:

1. **Publish OAuth Consent Screen**
   - Go to OAuth consent screen
   - Click **PUBLISH APP**
   - May require verification if using sensitive scopes

2. **Update Redirect URIs**
   - Add your production domain
   - Remove localhost URLs (or keep for testing)

3. **Domain Verification**
   - Google may require domain verification
   - Follow their verification process

---

## Quick Reference

**Where to update email:**
- Google Cloud Console → APIs & Services → OAuth consent screen → User support email

**What doesn't need to change:**
- Your `.env` file (unless creating new credentials)
- Your code
- Your database

**What users will see:**
- "Sign in with Google" button
- Google consent screen showing "Motivora Studio"
- Your Motivora Studio email as support contact



