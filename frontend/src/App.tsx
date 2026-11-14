import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { queryClient } from './api/queryClient'
import { Layout } from './components/Layout'
import { NotFound } from './pages/NotFound'
import { Placeholder } from './pages/Placeholder'

export function App() {
  const { t } = useTranslation()
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Placeholder title={t('nav.dashboard')} />} />
            <Route path="tickets" element={<Placeholder title={t('nav.tickets')} />} />
            <Route path="tickets/nuevo" element={<Placeholder title={t('pages.newTicket')} />} />
            <Route path="tickets/:code" element={<Placeholder title={t('pages.ticketDetail')} />} />
            <Route path="asignados" element={<Placeholder title={t('nav.assigned')} />} />
            <Route path="agentes" element={<Placeholder title={t('nav.agents')} />} />
            <Route path="informes" element={<Placeholder title={t('nav.reports')} />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
