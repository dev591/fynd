import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Landing } from './landing/Landing'
import { CursorTrail } from './components/CursorTrail'
import { LoginWizard } from './wizard/LoginWizard'
import { DashboardDesk } from './dashboard/DashboardDesk'
import { SupplierDashboard } from './supplier/SupplierDashboard'
import { SupplierQuotePage } from './supplier/SupplierQuotePage'

export default function App() {
  return (
    <BrowserRouter>
      <CursorTrail />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<LoginWizard />} />
        <Route path="/app" element={<DashboardDesk />} />
        <Route path="/supplier" element={<SupplierDashboard />} />
        <Route path="/supplier/quote" element={<SupplierQuotePage />} />
        <Route path="/quote" element={<SupplierQuotePage />} />
      </Routes>
    </BrowserRouter>
  )
}
