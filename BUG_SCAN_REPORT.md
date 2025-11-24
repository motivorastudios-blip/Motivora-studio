# Bug Scan Report - Motivora Studio

**Scan Date:** Current  
**Status:** 🔴 Found **10 bugs/issues** that need fixing

---

## 🔴 CRITICAL BUGS (Must Fix Before Beta)

### 1. **Google OAuth Route Returns Wrong Type** ⚠️ **BLOCKER**
**File:** `server.py:944`  
**Issue:** If Google OAuth is disabled, returns `jsonify()` but route expects redirect or template

```python
@app.route("/auth/google", methods=["GET"])
def auth_google():
    if not GOOGLE_OAUTH_ENABLED:
        return jsonify({"message": "Google login is not configured."}), 503  # ❌ Should redirect
```

**Fix:**
```python
if not GOOGLE_OAUTH_ENABLED:
    return redirect(url_for("auth_login", error="google_disabled"))
```

**Impact:** Will show JSON error instead of redirecting user

---

### 2. **Missing Authorization Check for Anonymous Render Downloads**
**File:** `server.py:799`  
**Issue:** Authorization check only happens if user is authenticated, but doesn't handle unauthenticated users accessing authenticated user's renders

```python
if current_user.is_authenticated and render_record.user_id != current_user.id:
    return jsonify({"message": "Unauthorized"}), 403
```

**Problem:** Anonymous users can access any render by guessing job_id if they know it

**Fix:**
```python
# Check authorization - only owner can access
if render_record.user_id:  # If render belongs to a user
    if not current_user.is_authenticated or render_record.user_id != current_user.id:
        return jsonify({"message": "Unauthorized"}), 403
```

**Impact:** Security vulnerability - users can access other users' renders

---

### 3. **Race Condition in Download Route**
**File:** `server.py:809-817`  
**Issue:** File existence check and file serving aren't atomic - file could be deleted between check and send

```python
file_path = Path(render_record.file_path)
if file_path.exists():  # ❌ File could be deleted here
    return send_file(...)  # Then this fails
```

**Fix:** Wrap in try-except:
```python
file_path = Path(render_record.file_path)
try:
    if file_path.exists():
        return send_file(...)
except FileNotFoundError:
    return render_form(message="Rendered file could not be found.")
```

**Impact:** Could cause 500 errors

---

### 4. **Session State Not Cleared on OAuth Error**
**File:** `server.py:995`  
**Issue:** If OAuth state is invalid, session state is not cleared

```python
if not state or state != session.get("oauth_state"):
    return redirect(url_for("auth_login", error="invalid_state"))
    # ❌ session["oauth_state"] still exists
```

**Fix:** Clear session state:
```python
if not state or state != session.get("oauth_state"):
    session.pop("oauth_state", None)  # Clear invalid state
    return redirect(url_for("auth_login", error="invalid_state"))
```

**Impact:** Could cause OAuth issues on retry

---

### 5. **Database Commit Not in Transaction**
**File:** `server.py:347-351`  
**Issue:** Database update happens inside app context but outside explicit transaction

```python
if job.get("user_id"):
    with app.app_context():
        render_record = Render.query.filter_by(job_id=job_id).first()
        if render_record:
            render_record.progress = progress
            render_record.message = job["message"]
            db.session.commit()  # ❌ Could fail if another thread modified
```

**Impact:** Could cause database inconsistencies

**Fix:** Add error handling:
```python
try:
    db.session.commit()
except Exception as e:
    db.session.rollback()
    print(f"Database update failed: {e}")
```

---

## 🟡 MEDIUM PRIORITY BUGS

### 6. **File Path Injection Risk**
**File:** `server.py:810`  
**Issue:** `render_record.file_path` comes from database - if compromised, could access arbitrary files

**Problem:** No validation that file_path is within allowed directory

**Fix:**
```python
file_path = Path(render_record.file_path)
# Ensure path is within storage directory
if not str(file_path.resolve()).startswith(str(STORAGE_ROOT.resolve())):
    return jsonify({"message": "Invalid file path"}), 403
```

**Impact:** Security risk if database is compromised

---

### 7. **Email Validation Missing**
**File:** `server.py:878-879`  
**Issue:** Email is only checked for empty string, not valid email format

```python
email = request.form.get("email", "").strip().lower()
# ❌ No validation if email is actually valid
```

**Fix:**
```python
import re
email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
if not email_pattern.match(email):
    return jsonify({"message": "Invalid email format."}), 400
```

**Impact:** Could store invalid emails in database

---

### 8. **Concurrent Render Limit Missing**
**File:** `server.py:520+`  
**Issue:** No limit on concurrent renders - one user could start 100 renders and crash server

**Impact:** Denial of service risk

**Fix:** Add concurrent render limit:
```python
MAX_CONCURRENT_RENDERS = 5  # Per user
current_renders = Render.query.filter_by(
    user_id=user_id,
    state="running"
).count()
if current_renders >= MAX_CONCURRENT_RENDERS:
    return jsonify({"message": f"Maximum {MAX_CONCURRENT_RENDERS} concurrent renders allowed."}), 429
```

---

### 9. **Job Cleanup Race Condition**
**File:** `server.py:841-843`  
**Issue:** Job is removed from ACTIVE_JOBS before cleanup completes

```python
output_path = Path(job["output_path"])
if not output_path.exists():
    ACTIVE_JOBS.pop(job_id, None)  # ❌ Removed here
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)  # Cleanup happens after
```

**Impact:** Another request could start new job with same ID before cleanup

---

### 10. **Missing Input Validation for File Size**
**File:** `server.py:491`  
**Issue:** File size is checked by Flask config, but actual STL file size validation missing

**Current:** Only checks upload size limit (512MB), not actual STL complexity

**Impact:** Very large STL files could cause Blender to crash

**Fix:** Add pre-check:
```python
# Quick validation before processing
if input_path.stat().st_size > 100 * 1024 * 1024:  # 100MB
    return jsonify({"message": "STL file too large for processing. Maximum 100MB."}), 400
```

---

## 🟢 LOW PRIORITY / EDGE CASES

### 11. **No Rate Limiting**
**Issue:** No protection against spam/abuse

**Impact:** Users could spam signups or renders

**Fix:** Add Flask-Limiter

---

### 12. **Missing CSRF Protection**
**Issue:** Forms don't have CSRF tokens

**Impact:** CSRF attack risk (though Flask-Login helps)

**Fix:** Add Flask-WTF with CSRF protection

---

### 13. **Error Messages Too Technical**
**File:** Multiple locations  
**Issue:** Some error messages show technical details

**Example:** "Blender output error: ..." shows full stack trace

**Fix:** Show user-friendly messages, log technical details

---

### 14. **Storage Directory Could Fill Up**
**File:** `server.py:397`  
**Issue:** No cleanup of old renders, storage will grow indefinitely

**Impact:** Server will run out of disk space

**Fix:** Add cleanup job for renders older than X days

---

### 15. **Missing Password Reset**
**Issue:** Users can't reset forgotten passwords

**Impact:** User can't recover account

---

## 🔧 QUICK FIXES NEEDED

### Immediate Actions:

1. **Fix Google OAuth route** (5 min)
2. **Fix authorization check** (10 min)
3. **Add file path validation** (15 min)
4. **Add email validation** (5 min)
5. **Add error handling for file operations** (10 min)

**Total Time: ~45 minutes for critical fixes**

---

## ✅ WHAT'S WORKING WELL

- ✅ Database models are solid
- ✅ Authentication flow is mostly correct
- ✅ File upload validation exists
- ✅ Watermark system works
- ✅ Download restrictions work
- ✅ Error handling in most places
- ✅ Thread safety for monitoring (mostly)

---

## 📋 PRIORITY FIX ORDER

1. **Before Beta:**
   - Fix Google OAuth route (#1)
   - Fix authorization check (#2)
   - Add file path validation (#6)
   - Add email validation (#7)
   - Add error handling (#3, #5)

2. **Before Launch:**
   - Add rate limiting (#11)
   - Add concurrent render limit (#8)
   - Add storage cleanup (#14)
   - Add password reset (#15)

3. **Post-Launch:**
   - Add CSRF protection (#12)
   - Improve error messages (#13)

---

## 🎯 RECOMMENDATION

**Fix the 5 critical bugs (#1-5) before sending to beta testers.**  
These will cause errors and security issues that will frustrate testers.

The rest can be fixed iteratively based on feedback.

Want me to fix these bugs now?


