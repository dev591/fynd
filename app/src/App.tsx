import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Landing } from './landing/Landing'
import { CursorTrail } from './components/CursorTrail'
import { LoginWizard } from './wizard/LoginWizard'
import { BuyerRequests } from './dashboard/BuyerRequests'
import { NewRequestForm } from './dashboard/NewRequestForm'
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

        {/* Buyer dashboard */}
        <Route path="/app" element={<BuyerRequests />} />
        <Route path="/app/new" element={<NewRequestForm />} />
        <Route path="/app/compare/:rfqId" element={<DashboardDesk />} />

        {/* Supplier dashboard */}
        <Route path="/supplier" element={<SupplierDashboard />} />
        <Route path="/supplier/quote" element={<SupplierQuotePage />} />
        <Route path="/quote" element={<SupplierQuotePage />} />
      </Routes>
    </BrowserRouter>
  )
}
