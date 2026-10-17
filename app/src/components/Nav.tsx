import { Link } from 'react-router-dom'
import { Magnetic } from './Magnetic'

/** Thin bar. The whole story is one pinned stage now, so it stays visible throughout. */
export function Nav() {
  return (
    <nav className="fixed inset-x-0 top-0 z-40 flex items-center justify-between px-6 py-4">
      <span className="display text-xl">Crossover</span>
      <Magnetic>
        <Link to="/login" className="block rounded-full bg-signal px-4 py-2 text-sm font-medium text-ink">
          Enter
        </Link>
      </Magnetic>
    </nav>
  )
}
