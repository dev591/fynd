/** Helpers for mapping one chapter's scroll progress (0..1) onto story beats. */
export const clamp01 = (v: number) => Math.min(1, Math.max(0, v))
/** Progress through the window [a, b] of p, clamped. */
export const seg = (p: number, a: number, b: number) => clamp01((p - a) / (b - a))
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t
export const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2)
