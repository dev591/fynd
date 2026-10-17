import { useEffect, useRef } from 'react'
import { ScrollTrigger } from '../lib/motion'

/** Thin signal bar tracking the whole story. Scrubbed to scroll, so it moves back too. */
export function ScrollProgress() {
  const bar = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const st = ScrollTrigger.create({
      trigger: document.documentElement,
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (s) => { bar.current!.style.transform = `scaleX(${s.progress})` },
    })
    return () => st.kill()
  }, [])
  return (
    <div className="fixed inset-x-0 top-0 z-50 h-0.5" aria-hidden>
      <div ref={bar} className="h-full origin-left bg-signal" style={{ transform: 'scaleX(0)' }} />
    </div>
  )
}
