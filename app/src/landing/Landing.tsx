import { LenisProvider } from '../lib/LenisProvider'
import { SkipToApp } from '../components/SkipToApp'
import { Nav } from '../components/Nav'
import { DiveStage } from '../components/DiveStage'
import { ScrollProgress } from '../components/ScrollProgress'
import { Hook } from './chapters/Hook'
import { Cost } from './chapters/Cost'
import { Turn } from './chapters/Turn'
import { How } from './chapters/How'
import { Proof } from './chapters/Proof'
import { Enter } from './chapters/Enter'

/** Crossover story: messy quotes → cost curves → the right order, explained. */
export function Landing() {
  return (
    <LenisProvider>
      <div className="landing grain">
        <ScrollProgress />
        <Nav />
        <SkipToApp />
        <DiveStage>
          <Hook />
          <Cost />
          <Turn />
          <How />
          <Proof />
          <Enter />
        </DiveStage>
      </div>
    </LenisProvider>
  )
}
