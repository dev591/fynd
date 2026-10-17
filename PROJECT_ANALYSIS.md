# FYND Project - Complete Code Analysis

**Repository**: https://github.com/dev591/fynd  
**Analysis Date**: October 17, 2026  
**Project Type**: Hackathon project for FyndHacks competition

## 🎯 Project Overview

FYND is a sophisticated procurement optimization platform built for **FyndHacks hackathon**. It solves the problem of **B2B quote comparison and order allocation** in commerce. The platform helps buyers find the optimal supplier quotes by considering landed cost (pack price + freight), lead times, and handling minimum order quantities (MOQs).

### Problem Statement
- Buyers receive messy, informal quotes from multiple suppliers (email, chat, spreadsheet)
- Current systems don't account for **packing inefficiency**: if a supplier ships in 10-unit packs but you need 23 units, you pay for 30
- Most procurement teams pick by cheapest per-unit price (naive sort), ignoring freight
- No structured way to handle late quotes with written exceptions

### Solution
A **layered intelligence pipeline** that:
1. Normalizes messy quotes into structured data
2. Evaluates true landed cost (with packing math)
3. Ranks suppliers considering lead time and MOQ
4. Handles exceptions and approvals
5. Provides live cost transparency with an interactive landing page story

---

## 📁 Project Structure

```
fynd-repo/
├── app/                          # Frontend (React + TypeScript + Vite)
│   ├── src/
│   │   ├── App.tsx              # Router setup
│   │   ├── index.css            # Tailwind + design tokens
│   │   ├── main.tsx             # React entry
│   │   ├── landing/
│   │   │   ├── Landing.tsx      # Landing page container
│   │   │   ├── chapters/        # 6 story chapters
│   │   │   ├── engine.ts        # In-browser order evaluation logic
│   │   │   ├── fixture.ts       # Sample quotes & needs (test data)
│   │   │   ├── CostChart.tsx    # Cost visualization
│   │   │   ├── QuoteCard.tsx    # Individual quote display
│   │   │   ├── QtyControl.tsx   # Quantity slider + spreadsheet
│   │   │   └── scrub.ts         # Scroll scrubbing logic
│   │   ├── components/
│   │   │   ├── CursorTrail.tsx  # Animated cursor trail with goo filter
│   │   │   ├── DiveStage.tsx    # Chapter container
│   │   │   ├── Magnetic.tsx     # Magnetic CTA buttons
│   │   │   ├── Nav.tsx          # Top navigation
│   │   │   ├── PinnedChapter.tsx # Scroll-pinned section controller
│   │   │   ├── ScrollProgress.tsx # Progress bar
│   │   │   └── SkipToApp.tsx    # Skip button for judges
│   │   └── lib/
│   │       ├── LenisProvider.tsx # Smooth scroll provider
│   │       └── [scroll utilities]
│   ├── docs/
│   │   ├── BRIEF.md             # Design & motion spec (7 pages)
│   │   ├── ENGINEERING_PLAYBOOK.md # System design philosophy
│   │   └── ORGANIZER.md         # Fynd platform alignment
│   ├── package.json             # React + build tooling
│   └── vite.config.ts           # Build config
│
├── api/                          # Backend (Python + FastAPI)
│   ├── app/
│   │   ├── main.py              # FastAPI app, layer registry, endpoints
│   │   ├── core.py              # Pipeline, context, result models
│   │   ├── trace.py             # SSE trace events & bus
│   │   └── layers/
│   │       ├── exact_cache.py   # Hash map cache (normalized key)
│   │       ├── rules.py         # Deterministic rules engine
│   │       ├── semantic_cache.py # Embedding + ANN similarity
│   │       └── llm.py           # Model cascade with fallback
│   ├── tests/
│   └── requirements.txt          # FastAPI, Pydantic, pytest, httpx
│
└── README.md
```

---

## 🏗️ Architecture

### Backend Pipeline (Layer-Based, Config-Driven)

The backend implements the **cheapest-first request pipeline** principle:

```
Request → Exact Cache → Rules → Semantic Cache → LLM
           (hash map)  (logic)  (vectors)     (fallback)
```

Each layer:
- **Returns a Result** if it can answer (short-circuits the pipeline)
- **Returns None** to fall through to the next layer
- **Emits trace events** (start, hit, miss, done, error) for live dashboard visualization

#### Key Layers

1. **ExactCache** (`layers/exact_cache.py`)
   - Hash map with LRU eviction + TTL
   - Normalized key: lowercase, stripped, sorted params, FNV-1a hash of prompt+model+version
   - Cost: ~0 tokens
   - Use: Identical repeat queries

2. **Rules** (`layers/rules.py`)
   - Deterministic rule evaluation (domain-specific logic goes here)
   - For FYND: quote normalization, MOQ handling, lead-time checks
   - Cost: ~0 tokens
   - Use: Structured queries that match known patterns

3. **SemanticCache** (`layers/semantic_cache.py`)
   - Embedding-based similarity search (hashed BoW placeholder now, real embeddings later)
   - Configurable similarity threshold (0.88 currently, untuned)
   - Cost: Only embedding cost (no LLM)
   - Use: Paraphrased or similar queries

4. **LLMCascade** (`layers/llm.py`)
   - Model cascade: try cheap model first, escalate on low confidence
   - Fallback mock provider (offline, for demo)
   - Real LLM integrated here when needed
   - Cost: Full LLM pricing

#### Pipeline Configuration

```python
# Set layer order via environment variable
PIPELINE="exact,rules,semantic,llm"  # default

# Each layer is in REGISTRY; add new layers there
REGISTRY = {
    "exact": ExactCache,
    "rules": Rules,
    "semantic": SemanticCache,
    "llm": LLMCascade
}
```

### API Endpoints

```python
POST /run
├─ Input: { query, tenant, meta }
└─ Output: { request_id, answer, layer, tokens_in, tokens_out, cost_usd, detail }

GET /stats
├─ % answered before LLM
├─ Cost per 1k requests
├─ p50/p95 latency
└─ Per-layer hit counts

GET /trace/stream (SSE)
├─ Events: start | hit | miss | done | error
├─ Includes: ms, tokens, $, layer, request_id
└─ Live dashboard feed (right rail)

GET /health
└─ { ok: true, layers: [...] }
```

### Trace & Observability

**TraceEvent** emitted per layer hop:
```python
@dataclass
class TraceEvent:
    request_id: str      # Same ID through all hops
    layer: str           # Which layer
    status: str          # start|hit|miss|done|error
    ms: float            # Latency
    tokens_in: int       # Input tokens
    tokens_out: int      # Output tokens
    cost_usd: float      # Cost for this hop
    detail: dict         # Layer-specific data
    ts: float            # Timestamp
```

**TraceBus**: 
- In-memory deque (500 history, configurable)
- Multiple subscribers (dashboards, monitoring)
- Never blocks (drops messages if consumer is slow)

---

## 🎨 Frontend

### Tech Stack
- **React 19.2** + TypeScript 6.0
- **Vite 8.3** (build, HMR)
- **Tailwind CSS 4.3** with custom tokens
- **GSAP 3.15** + ScrollTrigger (landing scroll story)
- **Lenis 1.3** (smooth scroll)
- **Motion 14.3** (dashboard animations, formerly Framer Motion)
- **Three.js + React Three Fiber** (optional 3D protagonist)
- **Lucide React** (icons, 1.5px stroke)

### Design System (Tokens)

**Color Palette** (warm + bone + one accent):
```css
--ink:     #0E0E0C    /* Page background */
--surface: #171714    /* Cards, panels */
--raised:  #1F1E1A    /* Hover, popovers */
--line:    #2C2A25    /* Borders */
--bone:    #F2EDE4    /* Main text (light on dark) */
--muted:   #9A958A    /* Secondary text */
--signal:  #FF5A1F    /* The one accent (CTAs, highlights) */
--live:    #C6F432    /* Only for "happening now" */
```

**Typography** (fluid scales, no breakpoints):
```
Fraunces (variable)     → Story headlines (editorial serif)
Geist (variable)        → App UI, body text (clean sans)
Geist Mono (variable)   → Numbers, code (tabular digits)
```

### Landing Page Story (Six Chapters)

The landing is **not a site with effects**; it's a **story the judge scrolls through**. One persistent object (the protagonist) transforms from broken → fixed as the problem → solution unfolds.

#### Chapter 1: Hook
- **Huge number** about the pain, alone on screen
- Protagonist in "broken" state
- Headline weight shifts as cursor approaches (Variable Font Proximity Hero idea)

#### Chapter 2: Cost
- **Pinned section** (scroll scrubs through timeline)
- Real figures showing what the pain costs
- Protagonist gets worse

#### Chapter 3: The Turn
- **Big moment**: product appears and acts on protagonist
- Chaos-to-order animation (inspired by Dipole Field concept)
- Heaviest animation investment here

#### Chapter 4: How It Works
- **Pinned, 4 steps**: each scroll step lights one stage of the real pipeline
- Not abstract boxes—actual system architecture
- Rules → Semantic Cache → LLM flow visible

#### Chapter 5: Proof
- **Live numbers** from the backend (not hardcoded)
- Protagonist in finished state
- Stats: % answered before LLM, cost/1k, latency percentiles

#### Chapter 6: Enter
- **CTA**: protagonist shrinks and becomes the login card
- Story never cuts; entering the app is part of it

### Key Components

#### `PinnedChapter`
- Pins a section to viewport while scrolling
- Scrubbed timeline (GSAP ScrollTrigger)
- Emits progress value (0..1) for animation feedback
- Respects `prefers-reduced-motion`

#### `CursorTrail`
- Canvas-based ink-drop trail following cursor
- SVG goo filter effect
- Cleaned-up rebuild (inspiration acknowledged, no code reused from unstated-license version)

#### `DiveStage`
- Container for chapters
- Manages scroll context

#### `QuoteCard` / `CostChart` / `QtyControl`
- Interactive components for quote data
- Spreadsheet mode (select rows, multi-edit)
- Quantity slider with packing visualization
- Live cost calculation using in-browser engine

### In-Browser Engine

`landing/engine.ts`: mirror of backend rules for client-side demo.

```typescript
// Calculate packed order
order(quote, qty) → { packs, units, overbuy, landed }

// Evaluate all quotes against a need
evaluate(quotes, need, exceptions) → {
  rows,              // All quotes evaluated
  pool,              // Eligible + approved quotes
  winner,            // Best by cost, then lead time, then overbuy
  tie,               // Multiple quotes tied
  cheaperExcluded    // Cheaper quotes that were blocked
}

// Show a losing quote how to win
negotiation(loser, winner) → { cut, freight, perUnit }

// Sort by naive per-unit price (what most buyers do)
naivePick(quotes, need) → Quote | null
```

**Test Data** in `fixture.ts`: sample quotes + needs.

---

## 🔧 Key Technical Decisions

### 1. **Layered Pipeline (Cheap First)**
- Every request type has a cost model: miss exact → semantic → LLM
- Config-driven layer order (no hardcoding)
- Trace events prove cost reduction live

### 2. **No External LLM Dependency**
- Backend runs offline with mock LLM
- Real LLM can be swapped in later
- Current mock confidence is fake (for demo only)

### 3. **In-Browser Engine Mirror**
- Same logic runs on client + backend
- Landing story runs offline (no network)
- Enables judges to interact with the system without backend

### 4. **SSE Trace Stream**
- Live, one-way pipeline visualization
- Feeds the dashboard right rail
- Never blocks if consumer is slow (drops messages)

### 5. **Design-as-Code**
- Tokens in `src/index.css` (not hardcoded)
- Typeface scales fluid (clamp, not breakpoints)
- Grip = one story told three ways: landing → deck → video

---

## 🎬 User Flows

### Landing Page Flow
1. Judge lands on `/`
2. **Chapter 1**: Sees the pain (huge number)
3. **Chapters 2-3**: Problem gets worse, then product appears
4. **Chapters 4-5**: How it works, proof of cost reduction
5. **Chapter 6**: Clicks to enter app
6. Protagonist shrinks into login card (story never breaks)

### Dashboard Flow (Placeholder)
1. Pre-filled demo account (one click to enter)
2. Right rail: live trace of backend requests (SSE stream)
3. Center: work area (not yet built)
4. States: empty → loading → populated
5. Animations on state changes only (no scroll effects)

---

## 📊 Data Models

### Frontend
```typescript
// Quote from a supplier (messy incoming data)
type Quote = {
  id: string
  supplier: string
  item: string
  packPrice: number
  packSize: number | null       // null = unknown
  freight: number
  leadDays: number
  moq?: number
  raw: string                   // Original, for messy card display
  channel: string
}

// What the buyer needs
type Need = {
  item: string
  qty: number
  needInDays: number
}

// Evaluated result
type Row = {
  quote: Quote
  status: 'eligible' | 'exception' | 'blocked'
  reason: string | null
  approved: boolean
  packs: number
  units: number
  overbuy: number
  landed: number | null
}
```

### Backend
```python
@dataclass
class Ctx:
    query: str
    tenant: str = "default"      # Multi-tenant cache namespace
    meta: dict = {}
    request_id: str              # Trace ID

@dataclass
class Result:
    answer: str
    layer: str                   # Which layer answered
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    detail: dict = {}
```

---

## 🔒 Security & Multi-Tenancy

- **Tenant namespace**: Each org gets its own cache/knowledge
- Never mix tenants
- Secrets in env (not hardcoded)
- Input validation: Pydantic models on every endpoint
- PII never in cache keys or logs

---

## 📈 Performance & Cost Metrics

**Proof Chapter Numbers** (live from backend):

```json
{
  "requests": 42,
  "by_layer": {
    "exact": 18,
    "rules": 12,
    "semantic": 8,
    "llm": 4
  },
  "pct_answered_before_llm": 90.5,
  "cost_usd": 0.064,
  "cost_per_1k_usd": 1.52,
  "p50_ms": 45,
  "p95_ms": 280
}
```

**Cost Model** (from `core.py`):
```python
# Placeholder pricing (edit to real rates)
PRICES = {
    "small": (0.25, 1.25),      # $0.25 / 1M in, $1.25 / 1M out
    "big": (3.0, 15.0),
    "mock": (0.25, 1.25)
}

cost = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
```

---

## 🚀 What's Missing / Placeholders

1. **Real LLM**: Swap in actual Anthropic API in `layers/llm.py`
2. **Embeddings**: Replace hashed BoW with real embedding model (e.g., Voyager)
3. **Vector ANN**: Real DB (pgvector) or Qdrant instead of in-memory
4. **Dashboard Center**: Work area not yet built (routes exist, component is `<Stub>`)
5. **Domain Logic**: Rules layer currently empty; add quote normalization, MOQ math here
6. **Database**: State is in-memory; move cache to Redis, vectors to pgvector at scale
7. **Tests**: Backend has test stubs; no frontend tests yet
8. **Auth**: Login page is placeholder; wire to Supabase or similar

---

## 🎓 Design Philosophy (from CLAUDE.md & BRIEF.md)

### The Story Principle
- Landing is a story, not a site with effects
- One protagonist transforms from problem → solution
- Every animation answers: "What changed in the story?"
- Scroll-scrubbed timelines (judge controls pace, can scroll back)

### Motion Rules
- **Under 200ms** for micro-interactions
- **No scroll effects on the dashboard** (motion only for state changes)
- Honor `prefers-reduced-motion`
- GSAP owns landing, Motion owns app (never animate same element with both)

### Design Tokens
- **Warm + bone + one accent** (not AI purple gradient)
- **Signal at <5% opacity** (scarcity is what makes it pop)
- **Film grain on dark** (kills the "template" look)
- **No stock photos**, only real product UI or custom 3D/SVG

---

## 🔗 Integration Points

### Fynd Commerce APIs
- (Not yet integrated; noted in ORGANIZER.md)
- Idea: show we plug into their platform, not rip-and-replace

### 21st.dev Components (Optional)
- Living Fluid Hero (3D fluid protagonist)
- Variable Font Proximity Hero (weight shift on cursor)
- Hero Dipole Field (chaos → order particle field)
- All MIT-licensed, optional, disclosed

---

## 📋 Development Checklist

**Pre-hackathon (Done)**
- [ ] Vite + React + TS scaffold
- [ ] Tailwind tokens
- [ ] Lenis + ScrollTrigger wiring
- [ ] PinnedChapter component
- [ ] Reduced-motion fallback
- [ ] SkipToApp button
- [ ] Backend pipeline skeleton + SSE trace

**After Problem Statement (Sat 17 Oct)**
- [ ] Build 6 landing chapters
- [ ] Pick and build protagonist (1, 2, or 3 from PROTAGONISTS.md)
- [ ] Wire backend rules layer to real quote logic
- [ ] Add Cost Chart, Quote Card, Qty Control
- [ ] Hook backend trace to dashboard right rail
- [ ] Live numbers (p50/p95, cost, %) from `/stats`
- [ ] Polish: CursorTrail, Magnetic CTAs, scrubbed timelines
- [ ] Test on mid laptop + projector
- [ ] Disclosure log updated

---

## 🎯 Success Criteria

**Problem Understanding (20 points)**: Chapters 1-2 show the pain with real numbers.  
**Technical Depth (20 points)**: Layered pipeline with live cost proof, not just chatbot.  
**Product Cohesion (20 points)**: Same story → landing, deck, video.  
**Demo Responsiveness (10 points)**: Judge can scrub chapter 3 with their trackpad.  
**Honest Scaling (10 points)**: Show bottleneck found, how we'd shard, not fake 350k/hour claims.  
**Design & Polish (10 points)**: Warm palette, magnetic CTAs, smooth scroll, no AI gradients.  
**Skip Button (10 points)**: Judge never trapped, one click to app.  

---

## 🔮 Post-Hackathon Enhancements

1. **Real embeddings**: Voyager, voyage-large-2-instruct
2. **Postgres + pgvector**: Move state from memory
3. **Redis**: Cache, rate limits, pub/sub
4. **Celery workers**: Async queue for long tasks
5. **LangGraph**: Multi-step agent with state/checkpoints
6. **Evals**: Labeled set, accuracy + cost scoring
7. **OKF integration**: Curated procurement knowledge as navigable graph
8. **Fynd platform**: Real commerce API integration

---

## 📚 Key Files to Understand

**Start here:**
1. `/app/docs/BRIEF.md` – Design & motion spec (read all 7 pages)
2. `/app/CLAUDE.md` – Project overview & workflow
3. `/api/README.md` – Backend pipeline philosophy

**Then:**
4. `/api/app/core.py` – Pipeline, context, result models
5. `/app/src/landing/engine.ts` – Order evaluation logic
6. `/app/src/components/PinnedChapter.tsx` – Scroll pinning

**Finally:**
7. `/api/app/main.py` – FastAPI endpoints & layer registry
8. `/app/src/landing/Landing.tsx` – Chapter orchestration

---

## 🤝 Team & Attribution

- **Dev**: Project lead, design
- **Claude (Anthropic)**: Frontend build, story chapters, polish
- **GSAP**: Landing scroll animation (free, updated SplitText)
- **Lenis, Motion, React, Tailwind**: Core dependencies (MIT/OFL)

**Disclosure**: Full dependency list and licenses in `/app/DISCLOSURE.md`.

---

**Ready to integrate the contract & validators we built earlier!**

Next step: Wire the backend rules layer to call the validator functions from the FYND profile contract.