import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Landing } from './landing/Landing'
import { CursorTrail } from './components/CursorTrail'

const Stub = ({ name }: { name: string }) => <div className="p-8">{name} (todo)</div>

export default function App() {
  return (
    <BrowserRouter>
      <CursorTrail />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Stub name="Login" />} />
        <Route path="/app" element={<Stub name="Dashboard" />} />
      </Routes>
    </BrowserRouter>
  )
}
