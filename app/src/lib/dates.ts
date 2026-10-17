/** Need-by dates for the buyer; the engine works in whole days from today. */

const pad = (n: number) => String(n).padStart(2, "0");

/** Local calendar date as YYYY-MM-DD, `days` from today. */
export function dateFromDays(days: number): string {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Whole days from today to a YYYY-MM-DD date (0 or less means today or the past). */
export function daysFromToday(isoDate: string): number {
  const [y, m, d] = isoDate.split("-").map(Number);
  if (!y || !m || !d) return 0;
  const target = new Date(y, m - 1, d, 12, 0, 0, 0).getTime();
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  return Math.round((target - today.getTime()) / 86_400_000);
}

export const tomorrow = () => dateFromDays(1);
