import { Link } from 'react-router-dom'
import { Magnetic } from './Magnetic'

/** Thin bar that stays on screen. */
export function Nav() {
  return (
    <nav className="fixed inset-x-0 top-0 z-40 flex items-center justify-between border-b border-line/60 bg-ink/85 px-6 py-3 backdrop-blur-md">
      <span className="display text-xl">Crossover</span>
      <div className="flex items-center gap-4">
        <Link to="/signin" className="text-sm text-muted transition-colors hover:text-bone">Sign in</Link>
        <Magnetic>
          <Link to="/login" className="block rounded-full bg-signal px-4 py-2 text-sm font-medium text-ink">
            Get started
          </Link>
        </Magnetic>
      </div>
    </nav>
  )
}
