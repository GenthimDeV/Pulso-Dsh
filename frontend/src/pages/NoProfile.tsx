import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { homeFor } from '../auth/roles'

/** Usuario autenticado sin perfil de agente ni solicitante (p. ej. un superusuario). */
export function NoProfile() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  // Esta pantalla es solo para usuarios sin rol: el resto vuelve a su inicio.
  if (user?.role) return <Navigate to={homeFor(user.role)} replace />
  return (
    <main className="grid min-h-screen place-items-center p-4">
      <section className="max-w-md rounded-lg border border-line bg-surface p-6">
        <h1 className="font-display text-xl font-semibold">{t('auth.noProfile.title')}</h1>
        <p className="mt-2 text-text-2">{t('auth.noProfile.body')}</p>
        <button
          type="button"
          onClick={() => void logout()}
          className="mt-4 rounded-md bg-accent-text px-4 py-2 text-sm font-semibold text-white"
        >
          {t('auth.logout')}
        </button>
      </section>
    </main>
  )
}
