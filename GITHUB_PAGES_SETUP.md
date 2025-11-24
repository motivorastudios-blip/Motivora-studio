# Free GitHub Pages Setup for Motivora Studio

This guide will help you set up a **free** website for Lemon Squeezy verification using GitHub Pages.

## Step 1: Create GitHub Repository

1. Go to [github.com](https://github.com) and sign in
2. Click the **"+"** icon → **"New repository"**
3. Name it: `motivora-studio` (or any name you like)
4. Make it **Public** (required for free GitHub Pages)
5. Check **"Add a README file"**
6. Click **"Create repository"**

## Step 2: Upload Landing Page

### Option A: Using GitHub Web Interface (Easiest)

1. In your new repository, click **"Add file"** → **"Upload files"**
2. Drag and drop the `gh-pages/index.html` file from this project
3. Click **"Commit changes"**

### Option B: Using Git (If you have Git installed)

```bash
cd "/Users/gilbranlaureano/STL:3MF animation drop"
git init
git add gh-pages/index.html
git commit -m "Add landing page"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/motivora-studio.git
git push -u origin main
```

## Step 3: Enable GitHub Pages

1. In your repository, go to **Settings** (top menu)
2. Scroll down to **"Pages"** (left sidebar)
3. Under **"Source"**, select **"Deploy from a branch"**
4. Select branch: **`main`**
5. Select folder: **`/ (root)`**
6. Click **"Save"**

## Step 4: Get Your Free URL

After a few minutes, your site will be live at:
```
https://YOUR_USERNAME.github.io/motivora-studio/
```

**Example:**
- If your username is `gilbran`, your URL would be:
- `https://gilbran.github.io/motivora-studio/`

## Step 5: Use in Lemon Squeezy

1. Go to your Lemon Squeezy identity verification form
2. Enter your website URL: `https://YOUR_USERNAME.github.io/motivora-studio/`
3. Enter the product description (already provided in the form)
4. Submit!

## Customizing the Landing Page

The landing page is in `gh-pages/index.html`. You can edit it to:
- Add your actual contact email
- Update download links
- Add screenshots or demo videos
- Customize colors and content

## Updating the Site

Whenever you update `gh-pages/index.html`:
1. Upload the new file to GitHub (same way as Step 2)
2. Changes go live automatically in 1-2 minutes

## Optional: Custom Domain (Later)

If you get a custom domain later (e.g., `motivorastudio.com`):
1. Buy the domain
2. In GitHub Pages Settings → Custom domain
3. Enter your domain
4. Update DNS records (GitHub will show you how)

## That's It!

You now have a **free** website that works perfectly for Lemon Squeezy verification. No credit card, no hosting fees, just free GitHub Pages hosting.


