import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { queryClient } from './api/queryClient'
import { AuthProvider } from './auth/AuthContext'
import { RequireAuth, RequireRole } from './auth/guards'
import { AGENT_ONLY, ALL_ROLES } from './auth/roles'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Login } from './pages/Login'
import { NoProfile } from './pages/NoProfile'
import { NewTicket } from './pages/NewTicket'
import { NotFound } from './pages/NotFound'
import { Placeholder } from './pages/Placeholder'
import { TicketDetail } from './pages/TicketDetail'
import { TicketList } from './pages/TicketList'

export function App() {
  const { t } = useTranslation()
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="login" element={<Login />} />
            <Route element={<RequireAuth />}>
              <Route path="sin-perfil" element={<NoProfile />} />
              <Route element={<Layout />}>
                <Route element={<RequireRole roles={ALL_ROLES} />}>
                  <Route path="tickets" element={<TicketList />} />
                  <Route path="tickets/nuevo" element={<NewTicket />} />
                  <Route path="tickets/:code" element={<TicketDetail />} />
                  <Route path="*" element={<NotFound />} />
                </Route>
                <Route element={<RequireRole roles={AGENT_ONLY} />}>
                  <Route index element={<Dashboard />} />
                  <Route path="asignados" element={<Placeholder title={t('nav.assigned')} />} />
                  <Route path="agentes" element={<Placeholder title={t('nav.agents')} />} />
                  <Route path="informes" element={<Placeholder title={t('nav.reports')} />} />
                </Route>
              </Route>
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
