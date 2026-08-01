import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import { PrivacyPolicy, TermsOfService } from './pages/Legal'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import LeadSearch from './pages/LeadSearch'
import LeadDetail from './pages/LeadDetail'
import SavedLeads from './pages/SavedLeads'
import Pipeline from './pages/Pipeline'
import Assistant from './pages/Assistant'
import Outreach from './pages/Outreach'
import Billing from './pages/Billing'
import Settings from './pages/Settings'
import { Spinner } from './components/ui'

function Protected({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex h-full items-center justify-center"><Spinner className="h-8 w-8" /></div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

function Public({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex h-full items-center justify-center"><Spinner className="h-8 w-8" /></div>
  if (user) return <Navigate to="/dashboard" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/privacy" element={<PrivacyPolicy />} />
          <Route path="/terms" element={<TermsOfService />} />
          <Route path="/login" element={<Public><Login /></Public>} />
          <Route path="/register" element={<Public><Register /></Public>} />

          <Route element={<Protected><Layout /></Protected>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/leads" element={<LeadSearch />} />
            <Route path="/leads/:id" element={<LeadDetail />} />
            <Route path="/saved" element={<SavedLeads />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/assistant" element={<Assistant />} />
            <Route path="/outreach" element={<Outreach />} />
            <Route path="/billing" element={<Billing />} />
            <Route path="/settings" element={<Settings />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
