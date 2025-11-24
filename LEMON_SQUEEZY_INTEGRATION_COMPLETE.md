# Lemon Squeezy Integration - Implementation Complete ✅

## What's Been Implemented

### 1. Webhook Endpoint ✅
- **Route**: `/webhooks/lemonsqueezy` (POST)
- **Handles Events**:
  - `subscription_created` - New subscription
  - `subscription_updated` - Subscription renewed/changed
  - `subscription_cancelled` - Subscription cancelled
  - `subscription_expired` - Subscription expired
  - `subscription_payment_failed` - Payment failed

**How it works:**
- Receives webhook from Lemon Squeezy
- Extracts customer email from subscription data
- Finds user in database by email
- Maps variant ID to subscription tier (pro/enterprise)
- Updates `user.subscription_tier` in database
- Sets `user.subscription_expires_at` if available
- Automatically downgrades to "free" on cancellation/expiration

### 2. Upgrade URL Function ✅
- **Function**: `get_upgrade_url(tier="pro")`
- **Location**: `server.py`
- **Features**:
  - Uses variant IDs from environment variables
  - Supports both Pro and Enterprise tiers
  - Falls back to generic URL if variant ID not set
  - Uses `LEMON_SQUEEZY_STORE_URL` for store domain

### 3. Subscription Tier Checking ✅
- **Function**: `get_user_tier()`
- **Updated to**:
  - First check database `subscription_tier` (updated by webhooks)
  - Check if subscription has expired
  - Auto-downgrade expired subscriptions to "free"
  - Fallback to license key validation if needed

### 4. Dashboard Upgrade Button ✅
- **Location**: `templates/dashboard.html`
- **Shows**: "Upgrade to Pro" button for free tier users
- **Links to**: Lemon Squeezy checkout URL with Pro variant ID

### 5. License Activation ✅
- **Route**: `/api/license/activate` (POST)
- **Updates**: Database subscription tier when license is activated
- **Stores**: License key in session and updates user tier

---

## Environment Variables Needed

Add these to your `.env` file:

```bash
# Lemon Squeezy API Configuration
LEMON_SQUEEZY_API_KEY=ls_your_api_key_here
LEMON_SQUEEZY_STORE_ID=your_store_id_here
LEMON_SQUEEZY_STORE_URL=https://your-store.lemonsqueezy.com

# Product Variant IDs (from Lemon Squeezy dashboard)
LEMON_SQUEEZY_VARIANT_ID_PRO=variant_id_for_pro_tier
LEMON_SQUEEZY_VARIANT_ID_ENTERPRISE=variant_id_for_enterprise_tier

# Optional: Webhook secret for signature verification
LEMON_SQUEEZY_WEBHOOK_SECRET=your_webhook_secret_here
```

---

## Next Steps to Complete Setup

### 1. Get Your Lemon Squeezy Credentials
- [ ] API Key: Settings → API → Create API Key
- [ ] Store ID: Found in URL when viewing your store
- [ ] Store URL: Your Lemon Squeezy store domain
- [ ] Variant IDs: Product page → Variant section

### 2. Create Products in Lemon Squeezy
- [ ] Create "Motivora Studio - Pro" product
- [ ] Set price (e.g., $9.99/month)
- [ ] Copy Variant ID
- [ ] Create "Motivora Studio - Enterprise" product (optional)
- [ ] Set price (e.g., $29.99/month)
- [ ] Copy Variant ID

### 3. Set Up Webhook in Lemon Squeezy
1. Go to **Settings** → **Webhooks** in Lemon Squeezy
2. Click **Add Webhook**
3. **Endpoint URL**: `https://your-domain.com/webhooks/lemonsqueezy`
   - For local testing: Use ngrok or similar: `https://your-ngrok-url.ngrok.io/webhooks/lemonsqueezy`
4. **Events to Subscribe**:
   - ✅ `subscription_created`
   - ✅ `subscription_updated`
   - ✅ `subscription_cancelled`
   - ✅ `subscription_expired`
   - ✅ `subscription_payment_failed`
5. **Secret** (optional): Generate a secret and add to `LEMON_SQUEEZY_WEBHOOK_SECRET`
6. Click **Save**

### 4. Update Environment Variables
- [ ] Add all Lemon Squeezy credentials to `.env`
- [ ] Restart your Flask server

### 5. Test the Integration

#### Test Webhook (Local Development):
1. Use ngrok to expose your local server:
   ```bash
   ngrok http 8888
   ```
2. Copy the ngrok URL (e.g., `https://abc123.ngrok.io`)
3. Add webhook in Lemon Squeezy with URL: `https://abc123.ngrok.io/webhooks/lemonsqueezy`
4. Make a test purchase in Lemon Squeezy (use test mode)
5. Check your server logs for webhook events
6. Verify user subscription tier updated in database

#### Test Upgrade Flow:
1. Log in as a free tier user
2. Go to dashboard
3. Click "Upgrade to Pro" button
4. Complete purchase in Lemon Squeezy
5. Webhook should fire and update subscription
6. User should now be able to download videos

#### Test Download Restrictions:
1. As free user: Try to download a render → Should see upgrade message
2. As Pro user: Try to download → Should work

---

## How It Works End-to-End

### User Purchase Flow:
1. User clicks "Upgrade to Pro" button on dashboard
2. Redirects to Lemon Squeezy checkout
3. User completes purchase
4. Lemon Squeezy sends webhook to `/webhooks/lemonsqueezy`
5. Webhook handler:
   - Finds user by email
   - Updates `subscription_tier` to "pro"
   - Sets `subscription_expires_at`
6. User can now download videos

### Subscription Renewal:
- When subscription renews, Lemon Squeezy sends `subscription_updated` webhook
- Webhook updates `subscription_expires_at` in database
- User continues to have Pro access

### Subscription Cancellation:
- When cancelled, Lemon Squeezy sends `subscription_cancelled` webhook
- Webhook sets `subscription_tier` to "free"
- User loses download access

---

## Troubleshooting

### Webhook Not Firing
- Check webhook URL is correct in Lemon Squeezy dashboard
- Verify server is accessible (use ngrok for local testing)
- Check server logs for incoming requests
- Verify webhook events are subscribed in Lemon Squeezy

### User Tier Not Updating
- Check webhook is receiving events (check server logs)
- Verify user email matches Lemon Squeezy customer email
- Check database for subscription_tier updates
- Verify variant IDs match in environment variables

### Upgrade Button Not Working
- Check `LEMON_SQUEEZY_VARIANT_ID_PRO` is set
- Verify `LEMON_SQUEEZY_STORE_URL` is correct
- Test checkout URL manually in browser

---

## Files Modified

1. **server.py**:
   - Updated `get_upgrade_url()` to use variant IDs
   - Updated `get_user_tier()` to check database first
   - Added `/webhooks/lemonsqueezy` endpoint
   - Updated `/api/license/activate` to update database

2. **templates/dashboard.html**:
   - Added "Upgrade to Pro" button for free tier users

---

## Production Deployment Notes

### Before Deploying:
1. Set all environment variables in production
2. Update webhook URL to production domain
3. Test webhook with test purchase
4. Verify SSL certificate (required for webhooks)

### Webhook Security (Optional):
- Implement signature verification using `LEMON_SQUEEZY_WEBHOOK_SECRET`
- Add rate limiting to webhook endpoint
- Log all webhook events for debugging

---

## Status: ✅ Ready for Testing

The integration is complete! Next steps:
1. Get your Lemon Squeezy credentials
2. Set up products and get variant IDs
3. Configure webhook endpoint
4. Test the full flow

Once tested, you're ready to accept payments! 🎉

