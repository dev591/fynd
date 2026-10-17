import { useLocation } from "react-router-dom";

/** Always visible inside the app: every seller, price and history here is synthetic. */
export function DemoMarker() {
  const { pathname } = useLocation();
  if (pathname === "/") return null;        // the story page has its own framing
  return (
    <div className="pointer-events-none fixed bottom-3 left-3 z-40 print:hidden">
      <span className="rounded-full border border-line bg-surface/90 px-3 py-1 text-[11px] text-muted shadow-sm backdrop-blur">
        Demo data is synthetic. No customers, no revenue.
      </span>
    </div>
  );
}
