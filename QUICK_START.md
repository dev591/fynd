# FYND Project - Quick Start Guide

## 📂 What You Have

### 1. **Profile Contract & Validators** (`c:\Users\amans\OneDrive\Pictures\Desktop\FYND\`)
- Complete TypeScript type definitions (`src/types.ts`)
- 19 production-grade validator functions (`src/validators/index.ts`)
- 161 passing tests (`src/validators/validators.test.ts`)
- Documentation & analysis files

**Status**: ✅ Ready to integrate into backend

### 2. **FYND Hackathon Project** (`c:\Users\amans\OneDrive\Pictures\Desktop\fynd-repo\`)
- React frontend with landing page story
- Python FastAPI backend with layered pipeline
- Generic boilerplate (no domain logic yet)
- Live trace + SSE dashboard

**Status**: Ready for onboarding wizard integration

---

## 🎯 What to Do Next

### Quick Wins (30 min)

1. **Copy Profile Contract to Backend**
   ```bash
   # Read TypeScript files
   cat FYND/src/types.ts
   cat FYND/src/validators/index.ts
   
   # Manually convert to Python Pydantic models
   # Save to: fynd-repo/api/app/schemas/profile.py
   # Save validators to: fynd-repo/api/app/validators/profile.py
   ```

2. **Test Python Validators**
   ```bash
   cd fynd-repo/api
   python -m pytest tests/test_validators.py -v
   ```

3. **Add Validation Layer to Pipeline**
   ```python
   # In fynd-repo/api/app/layers/validation.py
   # Copy the layer implementation from INTEGRATION_PLAN.md
   ```

### Medium Term (2-4 hours)

4. **Build Wizard Component** (React)
   - 6 screens: role, account, business, tax, review, summary
   - Real-time validation on every field
   - Error messages inline

5. **Wire Wizard to Backend**
   - Form submission → POST /onboard/buyer or /onboard/supplier
   - Backend validation layer catches errors
   - Rules layer classifies user

6. **Add Supabase**
   - Create profiles table
   - Wire wizard to save profiles
   - Setup auth

---

## 📖 Documentation Files

| File | Purpose | Read Time |
|------|---------|-----------|
| **PROJECT_ANALYSIS.md** | Complete FYND codebase breakdown | 20 min |
| **INTEGRATION_PLAN.md** | Step-by-step integration guide | 30 min |
| **COMPLETION_SUMMARY.md** | Validators built + test results | 10 min |
| **fynd-repo/app/docs/BRIEF.md** | Design & motion spec | 15 min |
| **fynd-repo/app/CLAUDE.md** | Project overview & workflow | 5 min |

**Start with**: INTEGRATION_PLAN.md (has code samples you can copy-paste)

---

## 🔑 Key Files to Understand

### Frontend
```
fynd-repo/app/src/
├── landing/engine.ts          ← Quote evaluation logic (in-browser)
├── components/PinnedChapter   ← Scroll-pinned sections
└── App.tsx                    ← Router (add /wizard route here)
```

### Backend
```
fynd-repo/api/app/
├── core.py                    ← Pipeline, Result, Ctx models
├── main.py                    ← FastAPI app + endpoints
└── layers/                    ← Add validation.py here
```

---

## 🚀 The Plan in 5 Steps

### Step 1: Profile Contract (TypeScript → Python)
```
Input:  FYND/src/types.ts + validators/index.ts
Output: fynd-repo/api/app/schemas/profile.py
        fynd-repo/api/app/validators/profile.py
Time:   45 min
```

**What to do:**
- Read TypeScript interfaces
- Write Pydantic models (same structure)
- Write Python validator functions (same logic)
- Test with 10 sample inputs

### Step 2: Validation Layer
```
Input:  INTEGRATION_PLAN.md (Phase 1.2)
Output: fynd-repo/api/app/layers/validation.py
Time:   30 min
```

**What to do:**
- Copy ValidationLayer class from plan
- Integrate into pipeline
- Test: POST /onboard/buyer with invalid email → should fail

### Step 3: Onboarding Endpoints
```
Input:  INTEGRATION_PLAN.md (Phase 4.2)
Output: fynd-repo/api/app/routes/onboarding.py
Time:   30 min
```

**What to do:**
- Create /onboard/buyer and /onboard/supplier endpoints
- Wire to rules layer
- Test: valid profile → returns classification

### Step 4: Wizard Component (React)
```
Input:  INTEGRATION_PLAN.md (Phase 2)
Output: fynd-repo/app/src/wizard/Wizard.tsx + step components
Time:   2 hours
```

**What to do:**
- Create Wizard component with state
- Build 4 step components (role, account, business, tax)
- Wire validators to form fields (real-time validation)
- Add submit button

### Step 5: Wire Frontend → Backend
```
Input:  Phase 2.4 + Phase 3
Output: Wizard submits to /onboard/buyer, saves to Supabase
Time:   1 hour
```

**What to do:**
- Add Supabase client
- Wire wizard submit to POST /onboard/buyer
- Handle response + redirect to dashboard
- Test full flow

---

## 💻 Command Reference

### Backend Setup
```bash
# Install deps
cd fynd-repo/api
pip install -r requirements.txt

# Run server
python -m uvicorn app.main:app --port 8000 --reload

# Run tests
python -m pytest -v

# Check API
curl http://localhost:8000/health
```

### Frontend Setup
```bash
# Install deps
cd fynd-repo/app
npm install

# Run dev server
npm run dev

# Build
npm run build

# Lint
npm run lint
```

### Profile Validators (Local Test)
```bash
# Import and test in Python
python3

from app.validators.profile import (
    validate_email,
    validate_phone,
    validate_gstin,
    validate_pan
)

# Test phone
print(validate_phone("9123456789"))  # (True, "")
print(validate_phone("5123456789"))  # (False, "must start with 6-9")

# Test email
print(validate_email("user@company.com"))  # (True, "")
print(validate_email("not-an-email"))      # (False, "Invalid format")

# Test GSTIN
print(validate_gstin("27AABCR5055K11Z"))   # (True, "")
print(validate_gstin("99AABCR5055K11Z"))   # (False, "Invalid state code")
```

---

## 📊 Validator Quick Reference

### Phone
- 10 digits starting with 6-9
- Accepts: `9123456789`, `91 2345 6789`, `(91) 234-56789`
- Rejects: `5123456789`, `912345678` (9 digits), `012345678` (starts with 0)

### Email
- Standard RFC format
- Accepts: `user@company.com`, `user+tag@gmail.com`, `user_name@example.co.in`
- Rejects: `user@`, `@company.com`, `user company.com`

### GSTIN
- 15 characters: state code (2) + PAN (10) + checksum (1) + entity (1) + Z (1)
- Format: `27AABCR5055K11Z` (valid Maharashtra)
- Rejects: `99AABCR5055K11Z` (invalid state), `27AABCR5055K11Y` (no Z)
- Accepts: lowercase, spaces

### PAN
- 10 characters: letters (5) + digits (4) + letter (1)
- Format: `AABCR5055K`
- Rejects: `1ABCR5055K` (starts with digit), `AABCR505K` (only 9 chars)

### State
- By code: `01`, `07`, `27`, `29`, `33`, etc.
- By name: `Maharashtra`, `Delhi`, `Karnataka` (case-insensitive)
- Rejects: `99` (invalid code), `InvalidState`

---

## 🎬 Demo Flow

**Chapter 1-6**: Judge scrolls landing, sees the problem → solution story  
**Chapter 6 payoff**: Clicks "Enter", protagonist shrinks into login  
**Login**: Pre-filled demo account, one click  
**Dashboard**: Trace shows validation layer at 0 cost, <5ms latency  
**Success**: Live stats: 100% answered before LLM, $0 overhead

---

## ❓ Troubleshooting

### "Validators not working"
- Check: Python syntax (Pydantic models vs. TypeScript interfaces)
- Test: Run individual validator functions in Python shell
- Fix: Print intermediate values, debug regex patterns

### "Backend not responding"
- Check: `curl http://localhost:8000/health` returns `{"ok": true}`
- Check: CORS middleware in main.py allows localhost:5173
- Fix: Restart server, check for syntax errors in logs

### "Wizard not submitting"
- Check: Form fields have correct names (`full_name`, `email`, `phone`, etc.)
- Check: Validators pass before POST
- Check: Network tab in DevTools shows request + response
- Fix: Add console.log to see POST payload

### "Trace events not showing"
- Check: Backend emits TraceEvent for each layer
- Check: `/trace/stream` returns SSE
- Check: Frontend subscribes to EventSource
- Fix: Test with `curl --no-buffer http://localhost:8000/trace/stream`

---

## 📈 Success Checklist

- [ ] Python validators pass 161 test cases (or equivalent)
- [ ] Validation layer integrates into pipeline
- [ ] /onboard/buyer endpoint returns classification
- [ ] Wizard renders all 4 steps
- [ ] Form validation works (real-time error messages)
- [ ] Wizard submit POSTs to backend
- [ ] Profile saves to database (Supabase)
- [ ] Dashboard trace shows validation layer at 0 cost, <10ms latency
- [ ] LoginBridge works (pre-filled demo, one click)
- [ ] Full flow: landing → wizard → login → dashboard

---

## 🤝 Questions?

Refer to:
1. **INTEGRATION_PLAN.md** - Code examples & step-by-step
2. **PROJECT_ANALYSIS.md** - Architecture deep-dive
3. **COMPLETION_SUMMARY.md** - Validators reference

---

**Total time to full integration: 4-5 hours**

Start with Step 1 now. Happy coding! 🚀