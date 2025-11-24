# Lemon Squeezy Setup Guide

This guide will help you set up Lemon Squeezy for license management in your Motivora Studio desktop app.

## Why Lemon Squeezy?

- **Simple**: No complex cloud API to maintain
- **Handles Everything**: Payments, subscriptions, license keys, invoices
- **Developer-Friendly**: Easy API integration
- **Desktop App Ready**: Works great for Electron apps

## Step 1: Create Lemon Squeezy Account

1. Go to [lemonsqueezy.com](https://lemonsqueezy.com)
2. Sign up for a free account
3. Complete your store setup

## Step 2: Create Products

Create three products for your subscription tiers:

### Free Tier (Optional)
- Name: "Motivora Studio - Free"
- Price: $0 (or free)
- Billing: One-time or lifetime

### Pro Tier
- Name: "Motivora Studio - Pro"
- Price: Your choice (e.g., $9.99/month or $99/year)
- Billing: Recurring subscription

### Enterprise Tier
- Name: "Motivora Studio - Enterprise"
- Price: Your choice (e.g., $29.99/month or $299/year)
- Billing: Recurring subscription

## Step 3: Get API Credentials

1. Go to **Settings** → **API** in your Lemon Squeezy dashboard
2. Create a new API key
3. Copy the **API Key** (starts with `ls_`)
4. Copy your **Store ID** (found in the URL: `https://app.lemonsqueezy.com/stores/{STORE_ID}`)

## Step 4: Get Product Variant IDs

1. Go to each product you created
2. Click on the product
3. Copy the **Variant ID** from the URL or product settings
   - URL format: `https://app.lemonsqueezy.com/products/{PRODUCT_ID}/variants/{VARIANT_ID}`

You'll need:
- `LEMON_SQUEEZY_VARIANT_ID_PRO` - Pro tier variant ID
- `LEMON_SQUEEZY_VARIANT_ID_ENTERPRISE` - Enterprise tier variant ID

## Step 5: Configure Environment Variables

Add these to your `.env` file:

```bash
# Lemon Squeezy Configuration
LEMON_SQUEEZY_API_KEY=ls_your_api_key_here
LEMON_SQUEEZY_STORE_ID=your_store_id_here
LEMON_SQUEEZY_VARIANT_ID_PRO=variant_id_for_pro
LEMON_SQUEEZY_VARIANT_ID_ENTERPRISE=variant_id_for_enterprise

# Upgrade/Checkout URLs
LEMON_SQUEEZY_UPGRADE_URL=https://motivora.lemonsqueezy.com/checkout/buy/{VARIANT_ID}
```

**Note**: Replace `motivora.lemonsqueezy.com` with your actual Lemon Squeezy store URL.

## Step 6: How It Works

### In the Desktop App:

1. **User purchases** a subscription on your Lemon Squeezy store
2. **Lemon Squeezy sends** a license key via email
3. **User enters** license key in the desktop app
4. **App validates** license via Lemon Squeezy API
5. **License is cached** locally for offline use
6. **App re-checks** periodically (daily/weekly)

### License Validation Flow:

```python
# In your desktop app
from license_checker import LicenseChecker

checker = LicenseChecker()
result = checker.validate_license(license_key, user_email)

if result["valid"]:
    tier = result["tier"]  # "free", "pro", "enterprise"
    # Enable features based on tier
```

## Step 7: Set Up Webhooks (Optional)

For automatic license updates when subscriptions change:

1. Go to **Settings** → **Webhooks** in Lemon Squeezy
2. Add webhook endpoint: `https://your-api.com/webhooks/lemonsqueezy`
3. Select events: `subscription_created`, `subscription_updated`, `subscription_cancelled`

The webhook will notify you when subscriptions change so you can update user licenses in real-time.

## Step 8: Testing

1. Create a test product in Lemon Squeezy (use Test Mode)
2. Purchase a test subscription
3. Copy the license key from the email
4. Enter it in your desktop app
5. Verify license validation works

## Integration in Your Desktop App

### Add License Entry UI

Add a "License" or "Activate License" option in your app's settings/preferences:

```javascript
// In your Electron app's renderer process
async function activateLicense(licenseKey) {
  const response = await fetch('/api/license/activate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ license_key: licenseKey })
  });
  
  const result = await response.json();
  if (result.tier === 'pro' || result.tier === 'enterprise') {
    // Enable Pro features
  }
}
```

### Check License on Startup

```python
# In server.py on app startup
if current_user.is_authenticated:
    license_key = session.get("license_key")
    if license_key:
        result = license_checker.validate_license(license_key, current_user.email)
        # Cache result, enable features
```

## Pricing Recommendations

- **Free**: Unlimited watermarked previews (current implementation)
- **Pro**: $9.99/month or $99/year - Download watermark-free videos
- **Enterprise**: $29.99/month or $299/year - All Pro features + priority support

## Troubleshooting

### License Not Validating

1. Check API key is correct in `.env`
2. Verify Store ID matches your Lemon Squeezy store
3. Check variant IDs match your products
4. Ensure license key format is correct (from Lemon Squeezy email)

### API Errors

- Check API key permissions in Lemon Squeezy dashboard
- Verify internet connection (license validation requires API call)
- Check cache file: `~/.motivora_license_cache.json`

### Offline Mode

The license checker caches valid licenses for 1 hour. Users can work offline during this period. After 1 hour, they'll need internet to re-validate.

## Next Steps

1. ✅ Set up Lemon Squeezy account and products
2. ✅ Configure environment variables
3. ✅ Test license validation
4. ✅ Add license entry UI to desktop app
5. ✅ Set up webhooks (optional)
6. ✅ Test purchase flow end-to-end

## Resources

- [Lemon Squeezy API Docs](https://docs.lemonsqueezy.com/api)
- [Lemon Squeezy Help Center](https://help.lemonsqueezy.com)
- Your license checker module: `license_checker.py`


