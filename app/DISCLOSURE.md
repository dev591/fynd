# Disclosure log

## Pre-hackathon boilerplate (generic plumbing only, no story/protagonist/product logic)
Written 2026-10-16: Vite + React + TS scaffold, Tailwind tokens (`src/index.css`), Lenis↔ScrollTrigger wiring (`src/lib`),
generic `PinnedChapter` (pin, scrub, progress out, reduced-motion fallback), `SkipToApp`, `Nav`, placeholder chapters.

## Built during the hackathon (Sat 17 Oct, after the PS drop)
Crossover story landing: six chapters in `src/landing/chapters`, the quote-card → cost-curve protagonist
(`CostChart`, `QuoteCard`), the quantity slider + spreadsheet mode (`QtyControl`), and an in-browser copy of the
rules (`src/landing/engine.ts`, `fixture.ts`) that runs the three case checks live. No new dependencies.
Written with Claude Code; reviewed by Dev.
Site-wide polish: `CursorTrail` (canvas ink-drop trail with an SVG goo filter), `Magnetic` CTAs, tilting quote cards,
`ScrollProgress`, and a scrubbed `--enter` entrance in `PinnedChapter`. The trail idea was inspired by a pasted
"particle animation" component whose author and license were not stated, so none of its code was copied; this is an
independent rebuild.

## Dependencies installed
| Package | Use | License |
|---|---|---|
| react, react-dom, react-router-dom | UI / routing | MIT |
| vite, typescript | build | MIT / Apache-2.0 |
| tailwindcss, @tailwindcss/vite | styling | MIT |
| gsap (+ScrollTrigger, SplitText) | landing scroll story | GSAP standard license (free) |
| lenis | landing smooth scroll | MIT |
| motion | dashboard micro-interactions | MIT |
| three, @react-three/fiber, @react-three/drei | optional 3D protagonist | MIT |
| lucide-react | icons (1.5px stroke) | ISC |
| @fontsource-variable/{fraunces,geist,geist-mono} | fonts | OFL-1.1 |

## 21st.dev components
None installed yet. Record component, author, license here before adding any.

## Backend skeleton (`/Volumes/dev/fynd/api`, pre-hackathon, generic)
Python 3.13: fastapi, uvicorn, pydantic, httpx, pytest (MIT/BSD/Apache). Layered pipeline, LRU+TTL exact cache, brute-force semantic cache with placeholder embedder, model-cascade stub with offline mock provider, SSE trace stream, stats. No domain logic, no real LLM calls.
