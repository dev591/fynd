# FyndHacks Design & Motion Brief (verbatim text extract of the PDF)

FyndHacks Design & Motion Brief
Oct 16, 2026  ·  @dev
TL;DR
The landing page is a story the judge scrolls through, not a site with effects on it. Every
animation has to answer one question: what just changed in the story?
Look: warm near-black and bone, one loud accent. No AI purple gradients.
Type: a variable display serif for the story, a clean sans for the app, mono for numbers.
Story: six chapters driven by scroll, with one persistent object (the protagonist) that
transforms as the problem turns into the solution.
App: landing tells the story, the dashboard stays calm and fast. Motion there only
shows state changing, mainly a live trace of what the system is doing.
Payoff: the same six chapters become the deck and the demo video. One story, three
deliverables.
Color system
Warm near-black and bone neutrals with one saturated accent. The purple-to-blue
gradient is the default every AI tool spits out, so judges read it as generated. 2026 work
leans on warm clay and bone neutrals with a single saturated accent kept for buttons and
links, alongside Pantone's soft white Cloud Dancer (source).
Token Hex Use
ink #0E0E0C Page background (dark, warm, not pure
black)
surface #171714 Cards, panels
raised #1F1E1A Hover, popovers
line #2C2A25 Borders, dividers
bone #F2EDE4 Main text on dark, light-mode
background
muted #9A958A Secondary text
FyndHacks Design & Motion Brief
Page 1 of 7

---

Rules:
signal  covers under 5% of any screen. Its scarcity is what makes it pop.
Swap signal  once the use case drops if the domain suggests a better one, the rest
stays.
Check text pairs hit WCAG AA (4.5:1). Bone on ink passes easily, muted on surface
needs a check.
Add a subtle film grain over ink  (an SVG noise at 3 to 4% opacity). It kills the flat
"template" look for almost no cost.
Typography
Three fonts, each with one job. Oversized, confident type as the hero is the strongest
2026 pattern, and fluid scales replace breakpoint-by-breakpoint font sizes (source).
All three are free on Google Fonts.
Token Hex Use
signal #FF5A1F The one accent: CTAs, the protagonist's
"fixed" state, active step
live #C6F432 Only for "happening now": live trace,
streaming, online
success  / warn  /
error
#3DDC97 / #FFB020 /
#FF4D4F
Status only, never decoration
Role Font Why
Story headlines Fraunces
(variable)
Has a weight axis, so letters can thicken as the
cursor approaches. Serif reads as editorial, not
SaaS template
App UI and body Geist Clean, neutral, built for interfaces
Numbers, traces,
code
Geist Mono Tabular digits so live numbers don't jitter
FyndHacks Design & Motion Brief
Page 2 of 7

---

Keep body text max 65 characters wide. Use font-variant-numeric: tabular-nums  on
every number in the dashboard.
Imagery and icons
No stock photos. The protagonist object and your real product UI are the only images.
Hero visual: the 3D or SVG protagonist, rendered live, not a video.
Product shots: real screenshots of your dashboard, slightly tilted with a soft shadow,
placed inside the story chapters.
Texture: film grain on dark backgrounds, a faint dot or line grid behind pinned sections.
Icons: Lucide, one stroke width (1.5px) everywhere. Mixing icon sets is an instant
amateur tell.
Illustrations: skip. With 26 hours, they never match the quality of the rest.
Page by page
The landing tells the story, login is the bridge, the dashboard is where the story pays off.
Landing
The six chapters above, full-screen each, dark. One CTA style only, in signal . Nav is a thin
bar with the logo and one button, it fades out while a chapter is pinned so nothing
competes with the story.
Level Size Weight / tracking
Hook number clamp(5rem, 14vw, 12rem) 300 to 800 animated, -0.04em
Chapter headline clamp(2.5rem, 6vw, 5.5rem) 400, -0.03em
Section title clamp(1.5rem, 3vw,
2.25rem)
500, -0.02em
Body (landing) 18px, line-height 1.6 400
Body (app) 14px, line-height 1.5 400
Dashboard dense /
labels
12 to 13px 500, +0.02em, uppercase for
labels
FyndHacks Design & Motion Brief
Page 3 of 7

---

Login
The protagonist from chapter 6 shrinks into the login card, so the story never cuts. Split
screen: form on the left, on the right a small live preview of the dashboard in its finished
state. Pre-fill a demo account so judges click once, no typing. Keep a real form behind it so
auth still counts.
Dashboard
Calm, dense, fast. The best 2026 dashboards (Linear, Stripe) pair quiet chrome with high
information density and put status first (source).
Top-left: the one number or status the user came for.
Center: the main work area.
Right rail: the live trace. Your agents, steps or pipeline running in real time, with live
color pulses on the active step. This is your flashiest element and it's honest flash, it
shows the real system working.
Empty states get a sentence and a button, never a blank chart.
Loading states use skeletons matching the real layout, never spinners.
Motion here only for state changes: a row arriving, a step finishing, a number updating.
Under 200ms, no scroll effects.
The story: scroll as narrative
Random scroll animations feel like a template. A story feels like a product someone
thought hard about. The difference is three rules.
Rule 1: one protagonist. A single persistent object lives on screen through every chapter
and changes state as the judge scrolls. It starts broken or chaotic (the problem), gets
fixed (the turn), and ends as the working product. This is what turns sections into a story.
Pick it after the use case drops: tangled parcels that sort themselves, a scattered catalog
that snaps into a grid, a noisy signal that resolves.
Rule 2: scrub, don't trigger. Animations follow scroll position (GSAP ScrollTrigger with
scrub ), so the judge controls the pace and can scroll back. Triggered one-shot fades are
what make sites feel random.
Rule 3: every motion is a plot point. Before adding any animation, say what changed in the
story. If the answer is nothing, cut it.
FyndHacks Design & Motion Brief
Page 4 of 7

---

The six chapters
1. Hook. One number about the pain, huge, alone on screen. The protagonist is in its
broken state. Headline weight shifts as the cursor moves near it.
2. The cost. Pinned section. Scroll scrubs through what the pain costs, real figures from
your research. The protagonist gets worse.
3. The turn. Your product appears and acts on the protagonist. This is the one big
moment, spend most animation effort here.
4. How it works. Pinned, 3 to 4 steps. Each scroll step lights up one stage of your actual
pipeline, the real architecture, not abstract boxes.
5. Proof. Live numbers pulled from your backend, not hardcoded. The protagonist is now
in its finished state.
6. Enter. CTA. The protagonist shrinks and becomes the login card (see Login below), so
leaving the story is part of it.
Why this wins judges
Problem Understanding (20) is shown, not told: chapters 1 and 2 are the problem.
The deck uses the same six beats, and the demo video is a screen recording of
scrolling through it. One asset, three deliverables.
Give a judge the trackpad on chapter 3. Watching it respond to their own scroll is what
they remember.
Add a quiet "skip to app" button in the corner so a judge in a hurry is never trapped.
FyndHacks Design & Motion Brief
Page 5 of 7

---

Stack and guardrails
Never animate the same element with GSAP and Motion together. GSAP owns the landing,
Motion owns the app.
21st.dev references
Living Fluid Hero: a 3D fluid that reacts to the cursor, built on R3F. MIT. Good base for a
protagonist.
Variable Font Proximity Hero: letters gain weight as the cursor nears. Use the idea for
the chapter 1 hook number.
Hero Dipole Field: particle field that forms headline letters as the cursor approaches.
Great "chaos becomes order" metaphor for chapter 3.
Installs need a 21st API key and free accounts get limited installs a day, so set it up tonight.
Check each license: several components are marked no-license, which is risky in a public
repo you're judged on. Prefer MIT, or rebuild the idea yourself.
Guardrails
Performance: cap canvas pixel ratio at 1.5, pause the 3D render when it's off screen,
and test on a mid laptop plus a projector. A stuttering hero looks worse than no hero.
Reduced motion: honor prefers-reduced-motion  with a static version of each
chapter.
Tool Job Note
Lenis Smooth scroll for the landing Landing only, never the
dashboard
GSAP + ScrollTrigger +
SplitText
Pinned chapters, scrubbed
timelines, headline reveals
Every plugin is now free,
including SplitText (source)
React Three Fiber +
drei
The 3D protagonist Only if the protagonist is 3D;
SVG is fine and cheaper
Motion (formerly
Framer Motion)
Dashboard micro-interactions Import from motion/react
(source)
FyndHacks Design & Motion Brief
Page 6 of 7

---

Rules: the story content and protagonist are part of the solution, build them after 1 pm
tomorrow. Tonight only generic plumbing (Lenis and ScrollTrigger wiring, a reusable
pinned-chapter component, tokens), and disclose it as boilerplate.
Disclosure: list every 21st.dev component, its author and license in the README.
Tonight's prep checklist
Sources
8 Web Design Trends to Try in 2026, Barn Images
Web Design Trends 2026, Line25
10 Best SaaS Dashboard Design Examples, AdminLTE
GSAP README
Motion for React
21st.dev: Living Fluid Hero, Variable Font Proximity Hero, Hero Dipole Field
Frontend teammate reads this doc end to end
Install Lenis, GSAP, Motion, R3F and drei in the boilerplate repo
Put the color and type tokens into the Tailwind config
Build one generic pinned-chapter component (pin, scrub, progress value out) and test
it with placeholder boxes
Add the reduced-motion fallback and the skip-to-app button to that component
Get a 21st.dev API key and preview the three references, checking licenses
List 3 or 4 protagonist ideas that could fit commerce problems, so picking one
tomorrow takes minutes
Note everything installed tonight in the disclosure log
FyndHacks Design & Motion Brief
Page 7 of 7