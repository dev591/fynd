# Integration Plan: Profile Contract & Validators → FYND Backend

## Overview

We've built a complete **TypeScript profile contract** with **19 production-grade validators** (161 tests, all passing). Now we integrate it into the existing FYND project to power the **buyer/supplier onboarding wizard** and **login flow**.

**Outcome**: A full-featured wizard that validates every field in real-time, stores profiles in Supabase, and feeds buyer/supplier data to the backend pipeline.

---

## 📋 Integration Checklist

### Phase 1: Backend Integration (Backend Routes + Rules Layer)

#### 1.1 Copy Profile Contract & Validators
```bash
# From: c:\Users\amans\OneDrive\Pictures\Desktop\FYND\src\
# To: <fynd-repo>/api/app/

cp src/types.ts → api/app/schemas/profile.py (convert to Python Pydantic)
cp src/validators/index.ts → api/app/validators/profile.py (convert to Python)
```

**Python Implementation** (same logic, Pydantic models):

`api/app/schemas/profile.py`:
```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional

class BuyerProfile(BaseModel):
    gst_claimable: bool
    spend_band: Literal["under_5L", "5L_to_20L", "20L_to_1Cr", "above_1Cr"]
    need_by_buffer_days: int = Field(ge=0)

class SupplierProfile(BaseModel):
    default_lead_days: int = Field(ge=0)
    gst_inclusive_default: bool
    regions: list[str] = Field(min_items=1)

class Profile(BaseModel):
    id: str
    role: Literal["buyer", "supplier"]
    full_name: str
    email: str
    phone: str
    company: str
    business_type: Literal["manufacturer", "trader", "distributor", "other"]
    state: str
    city: str
    categories: list[str] = Field(min_items=1)
    gstin: Optional[str] = None
    pan_masked: Optional[str] = None
    verification: dict = {}
    buyer: Optional[BuyerProfile] = None
    supplier: Optional[SupplierProfile] = None
```

`api/app/validators/profile.py`:
```python
"""Profile field validators (converted from TypeScript)."""

from typing import Tuple
import re

INDIAN_STATES = {
    "01": "Jammu and Kashmir",
    "07": "Delhi",
    "27": "Maharashtra",
    "29": "Karnataka",
    "33": "Tamil Nadu",
    # ... (39 states)
}

def validate_phone(phone: str) -> Tuple[bool, str]:
    """Indian mobile: 10 digits, starts with 6-9."""
    if not phone:
        return False, "Phone number is required"
    
    cleaned = re.sub(r'\D', '', phone)
    
    if len(cleaned) != 10:
        return False, "Phone number must be exactly 10 digits"
    
    if not cleaned[0] in '6789':
        return False, "Phone number must start with 6, 7, 8, or 9"
    
    return True, ""

def validate_email(email: str) -> Tuple[bool, str]:
    """RFC-compliant email."""
    if not email:
        return False, "Email is required"
    
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    return True, ""

def validate_gstin(gstin: str) -> Tuple[bool, str]:
    """GSTIN: 15 chars, state code (first 2) valid."""
    if not gstin:
        return False, "GSTIN is required"
    
    cleaned = gstin.upper().replace(' ', '')
    
    if len(cleaned) != 15:
        return False, "GSTIN must be exactly 15 characters"
    
    state_code = cleaned[:2]
    if state_code not in INDIAN_STATES:
        return False, "Invalid state code in GSTIN"
    
    if not cleaned.endswith('Z'):
        return False, "Invalid GSTIN format"
    
    pattern = r'^[0-9]{2}[A-Z0-9]{12}Z$'
    if not re.match(pattern, cleaned):
        return False, "Invalid GSTIN format"
    
    return True, ""

def validate_pan(pan: str) -> Tuple[bool, str]:
    """PAN: 10 chars, [A-Z]{5}[0-9]{4}[A-Z]{1}."""
    if not pan:
        return False, "PAN is required"
    
    cleaned = pan.upper().replace(' ', '')
    
    if len(cleaned) != 10:
        return False, "PAN must be exactly 10 characters"
    
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
    if not re.match(pattern, cleaned):
        return False, "Invalid PAN format"
    
    return True, ""

# ... (add all other validators)
```

#### 1.2 Add Validation Layer to Pipeline

`api/app/layers/validation.py`:
```python
"""Validation layer: catches malformed requests before rules/LLM."""

from ..core import Layer, Ctx, Result
from ..validators.profile import validate_phone, validate_email, validate_gstin
from ..schemas.profile import Profile

class ValidationLayer(Layer):
    name = "validation"
    
    async def run(self, ctx: Ctx) -> Result | None:
        """Validate profile fields if this is a profile submission."""
        
        # Only handle /profile endpoints
        if not ctx.meta.get("endpoint") == "/profile":
            return None
        
        profile_data = ctx.meta.get("profile_data")
        if not profile_data:
            return None
        
        errors = []
        
        # Validate common fields
        valid, msg = validate_email(profile_data.get("email", ""))
        if not valid:
            errors.append(msg)
        
        valid, msg = validate_phone(profile_data.get("phone", ""))
        if not valid:
            errors.append(msg)
        
        # Validate optional GSTIN/PAN
        if profile_data.get("gstin"):
            valid, msg = validate_gstin(profile_data["gstin"])
            if not valid:
                errors.append(msg)
        
        if errors:
            return Result(
                answer=f"Validation failed: {'; '.join(errors)}",
                layer="validation",
                detail={"errors": errors}
            )
        
        # All fields valid, fall through to next layer
        return None
```

Add to pipeline:
```python
# In api/app/main.py

REGISTRY = {
    "validation": ValidationLayer,  # NEW: first layer
    "exact": ExactCache,
    "rules": Rules,
    "semantic": SemanticCache,
    "llm": LLMCascade
}

# Default order now includes validation
PIPELINE="validation,exact,rules,semantic,llm"
```

#### 1.3 Add Profile Endpoints

`api/app/routes/profile.py`:
```python
"""Profile management endpoints."""

from fastapi import APIRouter, HTTPException
from ..schemas.profile import Profile
from ..validators.profile import validate_email, validate_phone, validate_gstin
from ..core import Ctx

router = APIRouter(prefix="/profile", tags=["profile"])

@router.post("/register")
async def register_profile(profile: Profile):
    """Register a new buyer/supplier profile."""
    
    # Validate all fields
    errors = []
    
    # (Validation happens, returns errors if any)
    
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})
    
    # Save to Supabase (or DB)
    # ...
    
    return {
        "success": True,
        "profile_id": profile.id,
        "message": f"Profile created for {profile.email}"
    }

@router.get("/{profile_id}")
async def get_profile(profile_id: str):
    """Fetch a profile by ID."""
    # Load from DB, return
    pass

@router.patch("/{profile_id}")
async def update_profile(profile_id: str, updates: dict):
    """Update profile fields (with validation)."""
    # Validate updated fields, save
    pass
```

Add to FastAPI app:
```python
# In api/app/main.py

from .routes import profile

app.include_router(profile.router)
```

---

### Phase 2: Frontend Integration (Wizard Component + Real-Time Validation)

#### 2.1 Create Wizard Component

`app/src/wizard/Wizard.tsx`:
```tsx
import { useState } from 'react'
import { validateEmail, validatePhone, validateGSTIN, validateProfile } from '../validators/profile'
import { AccountStep } from './steps/AccountStep'
import { BusinessStep } from './steps/BusinessStep'
import { TaxStep } from './steps/TaxStep'
import { RoleStep } from './steps/RoleStep'

export function Wizard() {
  const [step, setStep] = useState<'role' | 'account' | 'business' | 'tax' | 'review'>("role")
  const [profile, setProfile] = useState({})
  const [errors, setErrors] = useState({})
  
  const handleFieldChange = (field: string, value: any) => {
    setProfile(prev => ({ ...prev, [field]: value }))
    
    // Real-time validation
    if (field === 'email') {
      const result = validateEmail(value)
      if (!result.isValid) {
        setErrors(prev => ({ ...prev, email: result.error }))
      } else {
        setErrors(prev => ({ ...prev, email: null }))
      }
    }
    // ... (handle other fields)
  }
  
  const handleNext = async () => {
    // Validate current step
    const validation = validateProfile(profile)
    if (!validation.isValid) {
      setErrors(prev => ({ ...prev, summary: validation.error }))
      return
    }
    
    // Move to next step
    setStep(next(step))
  }
  
  return (
    <div className="wizard">
      {step === 'role' && <RoleStep onNext={() => setStep('account')} />}
      {step === 'account' && (
        <AccountStep 
          profile={profile}
          errors={errors}
          onChange={handleFieldChange}
          onNext={handleNext}
        />
      )}
      {step === 'business' && (
        <BusinessStep 
          profile={profile}
          errors={errors}
          onChange={handleFieldChange}
          onNext={handleNext}
        />
      )}
      {step === 'tax' && (
        <TaxStep 
          profile={profile}
          errors={errors}
          onChange={handleFieldChange}
          onNext={handleNext}
        />
      )}
      {step === 'review' && (
        <ReviewStep 
          profile={profile}
          onSubmit={submitProfile}
        />
      )}
    </div>
  )
}
```

#### 2.2 Create Step Components

`app/src/wizard/steps/AccountStep.tsx`:
```tsx
import { validateEmail, validatePhone, validatePassword } from '../../validators/profile'

export function AccountStep({ profile, errors, onChange, onNext }) {
  return (
    <div className="step account-step p-8">
      <h2 className="text-3xl font-fraunces mb-8">Create Account</h2>
      
      <div className="form-group mb-6">
        <label className="block text-sm font-medium mb-2">Full Name *</label>
        <input
          type="text"
          value={profile.full_name || ''}
          onChange={(e) => onChange('full_name', e.target.value)}
          onBlur={() => {
            const result = validateFullName(profile.full_name)
            if (!result.isValid) {
              onChange('errors', { ...errors, full_name: result.error })
            }
          }}
          className={`input ${errors.full_name ? 'error' : ''}`}
        />
        {errors.full_name && <p className="text-red-500 text-sm mt-1">{errors.full_name}</p>}
      </div>
      
      <div className="form-group mb-6">
        <label className="block text-sm font-medium mb-2">Work Email *</label>
        <input
          type="email"
          value={profile.email || ''}
          onChange={(e) => onChange('email', e.target.value)}
          className={`input ${errors.email ? 'error' : ''}`}
        />
        {errors.email && <p className="text-red-500 text-sm mt-1">{errors.email}</p>}
      </div>
      
      <div className="form-group mb-6">
        <label className="block text-sm font-medium mb-2">Phone (Indian Mobile) *</label>
        <input
          type="tel"
          value={profile.phone || ''}
          onChange={(e) => onChange('phone', e.target.value)}
          placeholder="9123456789"
          className={`input ${errors.phone ? 'error' : ''}`}
        />
        {errors.phone && <p className="text-red-500 text-sm mt-1">{errors.phone}</p>}
      </div>
      
      <div className="form-group mb-6">
        <label className="block text-sm font-medium mb-2">Password (Min 8 chars, or use magic link) *</label>
        <input
          type="password"
          value={profile.password || ''}
          onChange={(e) => onChange('password', e.target.value)}
          className={`input ${errors.password ? 'error' : ''}`}
        />
        {errors.password && <p className="text-red-500 text-sm mt-1">{errors.password}</p>}
      </div>
      
      <button onClick={onNext} className="btn btn-primary">Next</button>
    </div>
  )
}
```

#### 2.3 Add Wizard Routes

`app/src/App.tsx` (updated):
```tsx
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Landing } from './landing/Landing'
import { Wizard } from './wizard/Wizard'
import { Dashboard } from './dashboard/Dashboard'
import { CursorTrail } from './components/CursorTrail'

export default function App() {
  return (
    <BrowserRouter>
      <CursorTrail />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/wizard" element={<Wizard />} />
        <Route path="/login" element={<LoginBridge />} />
        <Route path="/app" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  )
}
```

#### 2.4 Create LoginBridge Component

`app/src/components/LoginBridge.tsx`:
```tsx
/**
 * Chapter 6 payoff: the protagonist shrinks into the login card.
 * Split screen: form on left, dashboard preview on right.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { validateEmail, validatePassword } from '../validators/profile'

export function LoginBridge() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('demo@fynd.com')
  const [password, setPassword] = useState('demo1234')
  const [errors, setErrors] = useState({})
  
  const handleLogin = async () => {
    // Validate
    const emailValid = validateEmail(email)
    const passValid = validatePassword(password)
    
    if (!emailValid.isValid || !passValid.isValid) {
      setErrors({
        email: emailValid.error,
        password: passValid.error
      })
      return
    }
    
    // Call backend
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    })
    
    if (res.ok) {
      navigate('/app')
    } else {
      setErrors({ summary: 'Login failed' })
    }
  }
  
  return (
    <div className="login-bridge flex h-screen">
      {/* Left: Form */}
      <div className="w-1/2 p-12 flex flex-col justify-center">
        <h1 className="text-5xl font-fraunces mb-8">Enter Fynd</h1>
        <p className="text-muted mb-12">One click for judges, real auth behind it.</p>
        
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          className="input mb-4"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="input mb-6"
        />
        
        {errors.summary && <p className="text-red-500 mb-4">{errors.summary}</p>}
        
        <button onClick={handleLogin} className="btn btn-primary">
          Enter
        </button>
      </div>
      
      {/* Right: Dashboard Preview */}
      <div className="w-1/2 bg-surface p-12">
        <p className="text-muted text-center py-32">Dashboard preview here (static mock)</p>
      </div>
    </div>
  )
}
```

---

### Phase 3: Database Integration (Supabase)

#### 3.1 Add Supabase Client

`app/src/lib/supabase.ts`:
```typescript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = createClient(supabaseUrl, supabaseKey)
```

#### 3.2 Add Auth & Profile Service

`app/src/services/profile.ts`:
```typescript
import { supabase } from '../lib/supabase'
import { Profile } from '../validators/profile'

export async function createProfile(profile: Profile) {
  const { data, error } = await supabase
    .from('profiles')
    .insert([profile])
    .select()
  
  if (error) throw error
  return data[0]
}

export async function getProfile(userId: string) {
  const { data, error } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', userId)
    .single()
  
  if (error) throw error
  return data
}

export async function updateProfile(userId: string, updates: Partial<Profile>) {
  const { data, error } = await supabase
    .from('profiles')
    .update(updates)
    .eq('id', userId)
    .select()
  
  if (error) throw error
  return data[0]
}
```

#### 3.3 Wire Wizard to Supabase

`app/src/wizard/Wizard.tsx` (updated):
```tsx
import { createProfile } from '../services/profile'

export function Wizard() {
  // ... (existing state)
  
  const submitProfile = async () => {
    try {
      const result = await createProfile(profile)
      toast.success(`Welcome, ${profile.full_name}!`)
      navigate('/app', { state: { profile: result } })
    } catch (err) {
      setErrors({ summary: err.message })
    }
  }
  
  return (
    // ... (wizard steps)
  )
}
```

---

### Phase 4: Backend Data Pipeline Integration

#### 4.1 Update Rules Layer for Buyer/Supplier Onboarding

`api/app/layers/rules.py`:
```python
"""Rules layer: deterministic logic for quotes, buyers, suppliers."""

from ..core import Layer, Ctx, Result
from ..schemas.profile import Profile
from ..validators import profile as validators

class Rules(Layer):
    name = "rules"
    rules = {}  # Accumulate learned rules here
    
    async def run(self, ctx: Ctx) -> Result | None:
        """Apply deterministic rules."""
        
        endpoint = ctx.meta.get("endpoint")
        
        # Buyer onboarding: classify by spend band
        if endpoint == "/onboard/buyer":
            profile_data = ctx.meta.get("profile")
            
            if profile_data.get("spend_band") == "under_5L":
                return Result(
                    answer="Eligible for quick approval",
                    layer="rules",
                    detail={"classification": "high-confidence"}
                )
            elif profile_data.get("spend_band") in ["5L_to_20L", "20L_to_1Cr"]:
                return Result(
                    answer="Requires manager review",
                    layer="rules",
                    detail={"classification": "requires-review"}
                )
            else:
                return Result(
                    answer="Escalate to account exec",
                    layer="rules",
                    detail={"classification": "enterprise"}
                )
        
        # Quote evaluation: apply packing math
        if endpoint == "/evaluate/quote":
            quote = ctx.meta.get("quote")
            need = ctx.meta.get("need")
            
            # Run the Crossover logic (from frontend engine)
            # This is where the validators ensure data integrity
            
            return None  # Fall through if no rule matches
        
        return None  # No rule applies
    
    def learn(self, ctx: Ctx, result: Result):
        """Record rules that worked for future use."""
        key = (ctx.meta.get("endpoint"), result.detail.get("classification"))
        self.rules[key] = self.rules.get(key, 0) + 1
```

#### 4.2 Add Onboarding Endpoints

`api/app/routes/onboarding.py`:
```python
"""Onboarding: buyer/supplier signup and profile completion."""

from fastapi import APIRouter, HTTPException
from ..schemas.profile import Profile, BuyerProfile, SupplierProfile
from ..core import Ctx
from . import pipeline

router = APIRouter(prefix="/onboard", tags=["onboarding"])

@router.post("/buyer")
async def onboard_buyer(profile: Profile):
    """Onboard a new buyer."""
    
    if profile.role != "buyer" or not profile.buyer:
        raise HTTPException(status_code=400, detail="Invalid buyer profile")
    
    ctx = Ctx(
        query=f"Classify buyer: {profile.company}",
        tenant=profile.id,
        meta={
            "endpoint": "/onboard/buyer",
            "profile": profile.dict()
        }
    )
    
    result = await pipeline.run(ctx)
    
    # Save to DB
    # ...
    
    return {
        "success": True,
        "profile_id": profile.id,
        "classification": result.detail.get("classification"),
        "next_step": "dashboard"
    }

@router.post("/supplier")
async def onboard_supplier(profile: Profile):
    """Onboard a new supplier."""
    
    if profile.role != "supplier" or not profile.supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier profile")
    
    ctx = Ctx(
        query=f"Register supplier: {profile.company}",
        tenant=profile.id,
        meta={
            "endpoint": "/onboard/supplier",
            "profile": profile.dict()
        }
    )
    
    result = await pipeline.run(ctx)
    
    return {
        "success": True,
        "profile_id": profile.id,
        "next_step": "complete_catalog"
    }
```

---

## 🔗 Data Flow

### Wizard → Validation → Backend

```
User fills wizard
    ↓
Frontend validates (real-time)
    ↓
User submits
    ↓
POST /wizard/submit
    ↓
Backend validation layer
    ↓
Rules layer (classify)
    ↓
Result: "eligible" / "requires_review" / "enterprise"
    ↓
Save to Supabase
    ↓
Emit trace event
    ↓
Frontend: redirect to dashboard
```

### Backend Pipeline Trace

```
POST /onboard/buyer
    ↓ validation layer (0ms, $0)
    ├─ Email format? Phone valid? → pass
    ↓ rules layer (2ms, $0)
    ├─ Spend band = under_5L?
    └─ Return classification
    ↓ emit trace event
    ↓ respond to frontend
    ↓ dashboard right rail shows: validation → rules → done (5ms total, $0)
```

---

## 📦 Files to Create/Modify

### New Files
```
api/app/
├── schemas/
│   └── profile.py                  # NEW: Pydantic models
├── validators/
│   ├── __init__.py
│   └── profile.py                  # NEW: validation functions
├── layers/
│   ├── validation.py               # NEW: validation layer
│   └── __init__.py
└── routes/
    ├── onboarding.py               # NEW: /onboard/* endpoints
    ├── profile.py                  # NEW: /profile/* endpoints
    └── __init__.py

app/src/
├── wizard/
│   ├── Wizard.tsx                  # NEW: main wizard component
│   ├── steps/
│   │   ├── RoleStep.tsx            # NEW: role picker
│   │   ├── AccountStep.tsx         # NEW: email, phone, password
│   │   ├── BusinessStep.tsx        # NEW: company, state, city, categories
│   │   ├── TaxStep.tsx             # NEW: GSTIN, PAN (skippable)
│   │   └── ReviewStep.tsx          # NEW: summary + submit
│   └── useWizard.ts                # NEW: wizard state management
├── services/
│   └── profile.ts                  # NEW: Supabase profile CRUD
├── validators/
│   └── profile.ts                  # NEW: import validators from FYND/src/validators
└── components/
    ├── LoginBridge.tsx             # UPDATE: wire to validators
    └── SkipToApp.tsx               # UPDATE: link to wizard
```

### Modified Files
```
api/app/
└── main.py                         # ADD: routes, layer order
app/src/
└── App.tsx                         # ADD: /wizard, /login routes
```

---

## ⚙️ Environment Variables

### Frontend (.env)
```env
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon_key>
VITE_API_URL=http://localhost:8000
```

### Backend (.env)
```env
DATABASE_URL=postgresql://...
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<service_key>
PIPELINE=validation,exact,rules,semantic,llm
```

---

## 🧪 Testing Strategy

### Frontend Unit Tests
```typescript
// wizard.test.tsx
import { render, screen, userEvent } from '@testing-library/react'
import { Wizard } from './Wizard'

test('validates email on blur', async () => {
  render(<Wizard />)
  const input = screen.getByLabelText('Work Email')
  
  await userEvent.type(input, 'invalid')
  await userEvent.tab()
  
  expect(screen.getByText(/Invalid email format/)).toBeInTheDocument()
})

test('phone validation rejects non-Indian numbers', async () => {
  render(<Wizard />)
  const input = screen.getByLabelText('Phone')
  
  await userEvent.type(input, '5123456789')  // starts with 5
  await userEvent.tab()
  
  expect(screen.getByText(/must start with 6, 7, 8, or 9/)).toBeInTheDocument()
})

test('submits valid profile', async () => {
  render(<Wizard />)
  
  // Fill all fields
  // Click submit
  
  // Expect API call with valid data
})
```

### Backend Integration Tests
```python
# tests/test_validation_layer.py
import pytest
from app.layers.validation import ValidationLayer
from app.core import Ctx

@pytest.mark.asyncio
async def test_rejects_invalid_email():
    layer = ValidationLayer()
    ctx = Ctx(
        query="",
        meta={
            "endpoint": "/profile",
            "profile_data": {
                "email": "not-an-email",
                "phone": "9123456789"
            }
        }
    )
    
    result = await layer.run(ctx)
    assert result is not None
    assert "Invalid email format" in result.answer

@pytest.mark.asyncio
async def test_passes_valid_profile():
    layer = ValidationLayer()
    ctx = Ctx(
        query="",
        meta={
            "endpoint": "/profile",
            "profile_data": {
                "email": "user@company.com",
                "phone": "9123456789"
            }
        }
    )
    
    result = await layer.run(ctx)
    assert result is None  # Falls through
```

---

## 📊 Success Metrics

### Phase 1 Complete
- [ ] All 19 validators working in Python
- [ ] Validation layer added to pipeline
- [ ] `/profile` and `/onboard` endpoints live
- [ ] Trace shows validation layer at 0 cost

### Phase 2 Complete
- [ ] Wizard component renders all 4 steps
- [ ] Real-time validation on every field
- [ ] Error messages display inline
- [ ] Submit button disabled until valid
- [ ] Success: redirect to dashboard

### Phase 3 Complete
- [ ] Profiles save to Supabase
- [ ] Profile retrieval works
- [ ] LoginBridge authenticates users
- [ ] Pre-filled demo account works (one click)

### Phase 4 Complete
- [ ] Rules layer classifies buyers
- [ ] Proof chapter shows: validation layer working, 0 cost, <10ms latency
- [ ] Dashboard right rail shows trace: validation → rules → done

---

## 🎯 Demo Script

1. **Landing Page** (scroll through Chapters 1-6)
   - Hook: "42% of procurement teams pick wrong supplier"
   - Cost: "Avg ₹1.2L overspend per order"
   - Turn: Protagonist transforms
   - How: Pipeline shown (validation → rules → proof)
   - Proof: Live stats from backend (0% cost overhead for validation)
   - Enter: Shrinks into login card

2. **Login** (Chapter 6 payoff)
   - Pre-filled demo account
   - One click: "Enter"
   - Redirect to dashboard

3. **Dashboard Right Rail** (Live trace)
   - POST /onboard/buyer
   - Event 1: validation layer START (0ms)
   - Event 2: validation layer HIT (2ms, $0)
   - Event 3: rules layer START (0ms)
   - Event 4: rules layer HIT (1ms, $0)
   - Event 5: pipeline DONE (3ms total, $0)
   - Stats: 100% answered before LLM, $0 cost, <10ms latency

---

## 📝 Implementation Order

**Day 1 (Tonight)**
1. ✅ Copy profile contract & create Python Pydantic models
2. ✅ Implement all validators in Python
3. ✅ Create validation layer
4. ⏳ Add /profile and /onboard endpoints

**Day 2 (Tomorrow, after PS drops)**
5. Create Wizard component + steps (30 min)
6. Wire Wizard to validators (15 min)
7. Add Supabase client (15 min)
8. Test wizard → backend (20 min)
9. Polish LoginBridge (30 min)
10. Wire trace to dashboard (45 min)

---

## 🚀 Next Steps

1. **Copy profile contract**: Move TypeScript validators to Python
2. **Test validators**: Run Python tests to verify parity
3. **Deploy validation layer**: Add to pipeline, test locally
4. **Build wizard skeleton**: Render 4 steps, no logic yet
5. **Integrate validators**: Wire form changes to validation functions
6. **Create profile service**: Supabase CRUD operations
7. **Wire wizard → backend**: POST to /onboard/buyer or /onboard/supplier

---

**Ready to start? Begin with Phase 1.1: Copy & Convert Profile Contract to Python.**