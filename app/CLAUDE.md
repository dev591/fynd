# FyndHacks project

Full design/motion brief: `docs/BRIEF.md` (read it first). Boilerplate disclosure: `DISCLOSURE.md`. Protagonist ideas: `PROTAGONISTS.md`.
Organizer research (Fynd, what it does, how to align): `docs/ORGANIZER.md`.
Engineering approach (cost-cutting with DSA, system design, library choices): `docs/ENGINEERING_PLAYBOOK.md`. Principle: LLM is the last resort; measure everything.

## Workflow when the problem statements (about 20 PS) are dropped
1. Run the `anthropic-skills:hackathon-deep-research` skill on the PS list to choose one idea and build a differentiated, defensible solution.
2. Then run the `anthropic-skills:hackathon-story-ui` skill to design the frontend (scroll-story landing, bridge login, calm live-trace dashboard) using this repo's boilerplate.
3. Pick a protagonist from `PROTAGONISTS.md`, then build chapters 1-6 (story content only after 1 pm on hackathon day).
4. Re-theme by editing the palette block in `src/index.css` (colors are role-based CSS variables; any palette works, not only dark). Re-check WCAG AA contrast.

## Rules to keep
- GSAP + Lenis own the landing; Motion owns the app. Never animate one element with both.
- Accent (`signal`) under 5% of any screen. `live` only for "happening now".
- Respect prefers-reduced-motion; cap canvas DPR at 1.5; pause 3D off-screen.
- Log every installed package / 21st.dev component (author + license) in `DISCLOSURE.md`.

Backend skeleton: `/Volumes/dev/fynd/api` (see its README.md). Layers are config-driven and meant to be swapped once the PS is known.
