# Quick Start: Lemon Squeezy Setup (15 minutes)

## Step-by-Step Setup

### 1. Create Lemon Squeezy Account (5 min)
1. Go to [lemonsqueezy.com](https://lemonsqueezy.com)
2. Click "Sign Up" (free account)
3. Complete your store setup
4. Verify your email

### 2. Create Products (5 min)

#### Create Pro Tier Product:
1. Go to **Products** → **New Product**
2. Name: `Motivora Studio - Pro`
3. Description: `Unlock watermark-free downloads and unlimited renders`
4. Price: Your choice (e.g., $9.99/month or $99/year)
5. Billing: Recurring subscription
6. Click **Create Product**
7. **Copy the Variant ID** (you'll need this)

#### Create Enterprise Tier (Optional):
1. Same process, name it `Motivora Studio - Enterprise`
2. Higher price (e.g., $29.99/month or $299/year)
3. **Copy the Variant ID**

### 3. Get API Credentials (3 min)
1. Go to **Settings** → **API**
2. Click **Create API Key**
3. Name it: `Motivora Studio API`
4. **Copy the API Key** (starts with `ls_`)
5. **Copy your Store ID** (found in URL: `https://app.lemonsqueezy.com/stores/{STORE_ID}`)

### 4. Get Checkout URLs (2 min)
1. Go to each product you created
2. Click **"View Checkout"** or **"Get Checkout URL"**
3. **Copy the checkout URL** for each product
   - Example: `https://motivora.lemonsqueezy.com/checkout/buy/{VARIANT_ID}`

### 5. Add to Your .env File

Add these to your `.env` file:

```bash
# Lemon Squeezy Configuration
LEMON_SQUEEZY_API_KEY=ls_your_api_key_here
LEMON_SQUEEZY_STORE_ID=your_store_id_here
LEMON_SQUEEZY_VARIANT_ID_PRO=variant_id_for_pro
LEMON_SQUEEZY_VARIANT_ID_ENTERPRISE=variant_id_for_enterprise

# Checkout URLs (for upgrade buttons)
LEMON_SQUEEZY_CHECKOUT_URL_PRO=https://your-store.lemonsqueezy.com/checkout/buy/{PRO_VARIANT_ID}
LEMON_SQUEEZY_CHECKOUT_URL_ENTERPRISE=https://your-store.lemonsqueezy.com/checkout/buy/{ENTERPRISE_VARIANT_ID}
```

**Important**: Replace `{PRO_VARIANT_ID}` and `{ENTERPRISE_VARIANT_ID}` with your actual variant IDs!

### 6. Test It (Optional)
1. Use Lemon Squeezy's **Test Mode**
2. Create a test product
3. Try purchasing with test card: `4242 4242 4242 4242`
4. Verify license key is sent via email

---

## What You'll Get

After setup, you'll have:
- ✅ API key for license validation
- ✅ Store ID for API calls
- ✅ Variant IDs for tier mapping
- ✅ Checkout URLs for upgrade buttons

---

## Next Steps

Once you have these values:
1. Add them to your `.env` file
2. Let me know and I'll add the checkout buttons throughout the app
3. Test the full flow: Click button → Purchase → Get license key → Activate in app

---

## Quick Reference

**Where to find things:**
- **API Key**: Settings → API → Create API Key
- **Store ID**: URL when viewing your store
- **Variant ID**: Product page → Variant section
- **Checkout URL**: Product page → "View Checkout" button

**Need help?** Check `LEMON_SQUEEZY_SETUP.md` for detailed instructions.



