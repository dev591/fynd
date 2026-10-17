import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Landing } from './landing/Landing'
import { CursorTrail } from './components/CursorTrail'
import { LoginWizard } from './wizard/LoginWizard'
import { BuyerRequests } from './dashboard/BuyerRequests'
import { NewRequestForm } from './dashboard/NewRequestForm'
import { DashboardDesk } from './dashboard/DashboardDesk'
import { DecisionOnePager } from './dashboard/DecisionOnePager'
import { SupplierDashboard } from './supplier/SupplierDashboard'
import { SupplierQuotePage } from './supplier/SupplierQuotePage'
import { SignIn } from './auth/SignIn'
import { RequireAuth } from './components/RequireAuth'

export default function App() {
  return (
    <BrowserRouter>
      <CursorTrail />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<LoginWizard />} />
        <Route path="/signin" element={<SignIn />} />

        {/* Buyer dashboard: signed in only */}
        <Route path="/app" element={<RequireAuth role="buyer"><BuyerRequests /></RequireAuth>} />
        <Route path="/app/new" element={<RequireAuth role="buyer"><NewRequestForm /></RequireAuth>} />
        <Route path="/app/compare/:rfqId" element={<RequireAuth role="buyer"><DashboardDesk /></RequireAuth>} />
        <Route path="/app/decision/:rfqId" element={<RequireAuth role="buyer"><DecisionOnePager /></RequireAuth>} />

        {/* Seller dashboard: signed in only. The quote pages below open from an invite link, no login. */}
        <Route path="/supplier" element={<RequireAuth role="seller"><SupplierDashboard /></RequireAuth>} />
        <Route path="/supplier/quote" element={<SupplierQuotePage />} />
        <Route path="/quote" element={<SupplierQuotePage />} />

        {/* Read-only shared one-pager: anyone with the link */}
        <Route path="/share/:token" element={<DecisionOnePager shared />} />
      </Routes>
    </BrowserRouter>
  )
}
