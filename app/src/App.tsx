import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Landing } from './landing/Landing'
import { CursorTrail } from './components/CursorTrail'
import { LoginWizard } from './wizard/LoginWizard'
import { DashboardDesk } from './dashboard/DashboardDesk'

export default function App() {
  return (
    <BrowserRouter>
      <CursorTrail />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<LoginWizard />} />
        <Route path="/app" element={<DashboardDesk />} />
      </Routes>
    </BrowserRouter>
  )
}
