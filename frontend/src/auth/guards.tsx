import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from './AuthContext'
import { homeFor } from './roles'
import type { Role } from '../api/session'

/** Pantalla de carga mientras se restaura la sesión (puede tardar con el servidor dormido). */
function SessionLoading() {
  const { t } = useTranslation()
  return (
    <div role="status" className="grid min-h-screen place-items-center text-text-3">
      {t('auth.restoring')}
    </div>
  )
}

/** Exige sesión; si no la hay, envía a `/login` recordando la ruta pedida. */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <SessionLoading />
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location }} />
  return <Outlet />
}

/** Exige uno de los roles; el resto va a su pantalla de inicio. Usuarios sin perfil: no entran. */
export function RequireRole({ roles }: { roles: readonly Role[] }) {
  const { user } = useAuth()
  if (!user?.role) return <Navigate to="/sin-perfil" replace />
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
  return <Outlet />
}
