/** Slow drifting light behind the app, so screens never feel frozen. Pure CSS; off for reduced motion. */
export function Ambient() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="ambient-blob left-[-10%] top-[-15%] h-[42rem] w-[42rem] bg-signal/[0.07]" />
      <div className="ambient-blob ambient-blob-2 right-[-12%] top-[30%] h-[36rem] w-[36rem] bg-live/[0.07]" />
      <div className="ambient-blob ambient-blob-3 bottom-[-20%] left-[30%] h-[30rem] w-[30rem] bg-warn/[0.05]" />
    </div>
  );
}
