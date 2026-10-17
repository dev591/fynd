import { Link } from 'react-router-dom'

export function SkipToApp() {
  return (
    <Link
      to="/app"
      className="label fixed right-4 bottom-4 z-50 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-muted backdrop-blur transition-colors hover:text-bone"
    >
      Skip to app →
    </Link>
  )
}
