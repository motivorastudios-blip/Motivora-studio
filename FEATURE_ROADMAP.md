# Feature Roadmap - What's Missing & What We Can Add

## 🔴 Critical Missing Features (Must Have)

### 1. **Payment/Checkout Integration** ⚠️ PARTIAL
**Status**: Lemon Squeezy API integrated, but no checkout flow
**Priority**: CRITICAL

**What's Missing:**
- [ ] Checkout page/button that links to Lemon Squeezy
- [ ] Webhook handler to update user subscription when payment succeeds
- [ ] Subscription management page (view current plan, cancel)
- [ ] Pricing page with clear plans
- [ ] "Upgrade to Pro" buttons throughout the app

**Quick Win**: Add simple checkout buttons that link to your Lemon Squeezy store URL

---

### 2. **Password Reset** ❌ NOT IMPLEMENTED
**Status**: Users can't recover forgotten passwords
**Priority**: HIGH

**What's Needed:**
- [ ] "Forgot Password" link on login page
- [ ] Password reset request route
- [ ] Email service integration (SendGrid/Mailgun)
- [ ] Reset token generation & validation
- [ ] Reset password form

**Impact**: Users locked out if they forget password

---

### 3. **Email Service** ❌ NOT IMPLEMENTED
**Status**: No email sending capability
**Priority**: HIGH

**What's Needed:**
- [ ] Email service setup (SendGrid, Mailgun, AWS SES)
- [ ] Welcome emails for new users
- [ ] Password reset emails
- [ ] Render completion notifications (optional)
- [ ] Subscription confirmation emails

**Quick Win**: Start with SendGrid (free tier: 100 emails/day)

---

### 4. **Terms of Service & Privacy Policy** ❌ NOT CREATED
**Status**: Legal pages don't exist
**Priority**: MEDIUM (required for launch)

**What's Needed:**
- [ ] Terms of Service page
- [ ] Privacy Policy page
- [ ] Links in footer
- [ ] Checkbox on signup form

**Quick Win**: Use a template generator (Termly, iubenda) or ChatGPT

---

## 🟡 Important Features (Should Have)

### 5. **User Settings/Profile Page** ❌ NOT IMPLEMENTED
**Status**: No way to update profile
**Priority**: MEDIUM

**What's Needed:**
- [ ] Settings page (`/settings`)
- [ ] Update name/email
- [ ] Change password
- [ ] View subscription details
- [ ] License key management
- [ ] Delete account option

---

### 6. **Better Error Pages** ⚠️ BASIC
**Status**: Generic Flask errors
**Priority**: MEDIUM

**What's Needed:**
- [ ] Custom 404 page
- [ ] Custom 500 page
- [ ] Custom 403 (forbidden) page
- [ ] User-friendly error messages

---

### 7. **Render Sharing/Preview Links** ❌ NOT IMPLEMENTED
**Status**: Can't share renders with others
**Priority**: MEDIUM

**What's Needed:**
- [ ] Generate shareable preview links
- [ ] Public preview page (no download, just view)
- [ ] Share button on completed renders
- [ ] Optional: Password-protected shares

**Use Case**: Show clients previews before they purchase

---

### 8. **Storage Management** ⚠️ BASIC
**Status**: Renders stored indefinitely, no cleanup
**Priority**: MEDIUM

**What's Needed:**
- [ ] Auto-delete old renders (e.g., 30 days for free, 90 days for Pro)
- [ ] Storage usage display in dashboard
- [ ] Manual delete option for users
- [ ] Cleanup job/cron task

**Impact**: Disk space will fill up over time

---

### 9. **Rate Limiting** ❌ NOT IMPLEMENTED
**Status**: No protection against abuse
**Priority**: MEDIUM

**What's Needed:**
- [ ] Rate limiting on upload endpoint
- [ ] Rate limiting on auth endpoints
- [ ] IP-based throttling
- [ ] User-based limits (already have concurrent renders)

**Quick Win**: Use Flask-Limiter

---

### 10. **Analytics & Tracking** ❌ NOT IMPLEMENTED
**Status**: No user behavior tracking
**Priority**: LOW (but useful)

**What's Needed:**
- [ ] Google Analytics or Plausible
- [ ] Track render completions
- [ ] Track upgrade conversions
- [ ] Track feature usage

---

## 🟢 Nice-to-Have Features (Can Add Later)

### 11. **Batch Rendering** ❌ NOT IMPLEMENTED
**Status**: One file at a time
**Priority**: LOW

**What's Needed:**
- [ ] Upload multiple STL files
- [ ] Queue system for batch processing
- [ ] Batch download option
- [ ] Progress for each file

**Use Case**: Render multiple product variations at once

---

### 12. **Custom Background Colors** ❌ NOT IMPLEMENTED
**Status**: Only transparent background
**Priority**: LOW

**What's Needed:**
- [ ] Background color picker
- [ ] Preset backgrounds (white, black, gray)
- [ ] Gradient backgrounds (optional)

---

### 13. **Video Preview Before Download** ❌ NOT IMPLEMENTED
**Status**: Must download to preview
**Priority**: LOW

**What's Needed:**
- [ ] HTML5 video player in dashboard
- [ ] Preview modal on render cards
- [ ] Play button on completed renders

**Quick Win**: Use HTML5 `<video>` tag

---

### 14. **Render Presets/Saved Settings** ❌ NOT IMPLEMENTED
**Status**: Must configure each time
**Priority**: LOW

**What's Needed:**
- [ ] Save render settings as presets
- [ ] Quick-select presets
- [ ] Name presets (e.g., "Product Shot", "Social Media")
- [ ] Share presets (optional)

---

### 15. **Export Settings** ❌ NOT IMPLEMENTED
**Status**: Can't export/import settings
**Priority**: LOW

**What's Needed:**
- [ ] Export render settings as JSON
- [ ] Import settings from JSON
- [ ] Share settings files

---

### 16. **Render Queue Management** ⚠️ BASIC
**Status**: Basic queue, no management UI
**Priority**: LOW

**What's Needed:**
- [ ] Queue view showing all pending renders
- [ ] Reorder queue
- [ ] Pause/resume queue
- [ ] Priority rendering

---

### 17. **Video Length Customization UI** ⚠️ HARDCODED
**Status**: 10 seconds hardcoded
**Priority**: LOW

**What's Needed:**
- [ ] Duration slider (5-30 seconds)
- [ ] Preview duration in UI
- [ ] Save preferred duration

---

### 18. **Keyboard Shortcuts** ❌ NOT IMPLEMENTED
**Status**: Mouse-only navigation
**Priority**: LOW

**What's Needed:**
- [ ] Keyboard shortcuts for common actions
- [ ] Shortcut help modal
- [ ] Accessibility improvements

---

### 19. **Dark Mode** ❌ NOT IMPLEMENTED
**Status**: Light theme only
**Priority**: LOW

**What's Needed:**
- [ ] Dark mode toggle
- [ ] System preference detection
- [ ] Persist preference

---

### 20. **Multi-language Support** ❌ NOT IMPLEMENTED
**Status**: English only
**Priority**: LOW

**What's Needed:**
- [ ] i18n framework (Flask-Babel)
- [ ] Language switcher
- [ ] Translate UI strings

---

## 🚀 Quick Wins (Easy to Add)

### 1. **Add "Upgrade" Buttons**
- Add buttons linking to Lemon Squeezy checkout
- 15 minutes

### 2. **Video Preview in Dashboard**
- Add HTML5 video player to render cards
- 30 minutes

### 3. **Custom 404/500 Pages**
- Create error templates
- 20 minutes

### 4. **Settings Page**
- Basic profile update form
- 1 hour

### 5. **Render Sharing Links**
- Generate unique share tokens
- 1-2 hours

### 6. **Storage Usage Display**
- Show disk usage in dashboard
- 30 minutes

---

## 📊 Priority Matrix

### Do First (Week 1)
1. ✅ Payment checkout buttons
2. ✅ Password reset
3. ✅ Email service setup
4. ✅ Terms & Privacy pages

### Do Next (Week 2)
5. ✅ Settings page
6. ✅ Error pages
7. ✅ Storage cleanup
8. ✅ Rate limiting

### Do Later (Month 2+)
9. ✅ Batch rendering
10. ✅ Custom backgrounds
11. ✅ Render presets
12. ✅ Dark mode

---

## 💡 Feature Ideas from User Feedback

### Potential Additions:
- **3MF Support**: Currently only STL, add 3MF format
- **OBJ Support**: Add OBJ file format
- **Animation Presets**: Pre-made animation styles (slow spin, fast spin, bounce)
- **Camera Angles**: Multiple camera positions
- **Lighting Presets**: Different lighting setups
- **Material Preview**: Show materials on model
- **Cloud Rendering**: Optional cloud rendering for faster processing
- **API Access**: REST API for developers
- **Webhooks**: Notify external services when renders complete
- **Team Accounts**: Share renders with team members

---

## 🎯 Recommended Next Steps

### Immediate (This Week)
1. **Add Lemon Squeezy checkout buttons** - Link to your store
2. **Set up email service** - SendGrid free tier
3. **Create Terms & Privacy** - Use template
4. **Add password reset** - Critical for user retention

### Short Term (This Month)
5. **Settings page** - User profile management
6. **Error pages** - Better UX
7. **Storage cleanup** - Prevent disk issues
8. **Video preview** - Better dashboard UX

### Long Term (Next Quarter)
9. **Batch rendering** - Power user feature
10. **Render sharing** - Collaboration feature
11. **Custom backgrounds** - More customization
12. **Analytics** - Track usage and conversions

---

## 📝 Implementation Notes

### Easy to Implement (< 2 hours)
- Upgrade buttons
- Video preview
- Error pages
- Storage usage display
- Settings page (basic)

### Medium Complexity (2-8 hours)
- Password reset
- Email service
- Render sharing
- Storage cleanup
- Rate limiting

### Complex (1+ days)
- Batch rendering
- Render presets
- Multi-language
- API access

---

## 🎨 UI/UX Improvements

### Quick UI Wins:
- [ ] Loading skeletons instead of spinners
- [ ] Better empty states (no renders yet)
- [ ] Toast notifications for actions
- [ ] Confirmation modals for destructive actions
- [ ] Better mobile navigation
- [ ] Tooltips for settings
- [ ] Progress indicators for multi-step flows

---

## 🔧 Technical Improvements

### Code Quality:
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Set up CI/CD
- [ ] Database migrations (Alembic)
- [ ] API documentation
- [ ] Logging improvements
- [ ] Performance monitoring

---

## Summary

**Critical Missing:**
1. Payment checkout flow
2. Password reset
3. Email service
4. Legal pages

**Should Add Soon:**
5. Settings page
6. Error pages
7. Storage management
8. Rate limiting

**Nice to Have:**
9. Batch rendering
10. Custom backgrounds
11. Render sharing
12. Video preview

**Estimated Time:**
- Critical features: 2-3 days
- Important features: 1-2 weeks
- Nice-to-have: 1-2 months



