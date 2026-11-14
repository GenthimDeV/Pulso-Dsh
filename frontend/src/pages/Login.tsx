import { useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ApiError, isWakingError } from '../api/errors'
import { useAuth } from '../auth/AuthContext'
import { homeFor } from '../auth/roles'
import { WakingBanner } from '../components/WakingBanner'
import { LANGUAGES, setLanguage, type Language } from '../i18n'

// Cuentas públicas del seed (datos ficticios). La contraseña se puede cambiar por entorno.
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? 'pulso-demo'
const DEMO_ACCOUNTS = [
  { key: 'agent', username: 'agente' },
  { key: 'requester', username: 'solicitante' },
] as const

function errorKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'auth.errors.invalid'
    if (error.status === 429) return 'auth.errors.throttled'
  }
  if (isWakingError(error)) return 'auth.errors.unreachable'
  return 'errors.unknown'
}

interface FromState {
  from?: { pathname: string; search: string }
}

export function Login() {
  const { t, i18n } = useTranslation()
  const { status, user, login } = useAuth()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (status === 'authenticated' && user) {
    const from = (location.state as FromState | null)?.from
    const target = from ? `${from.pathname}${from.search}` : user.role ? homeFor(user.role) : '/'
    return <Navigate to={target} replace />
  }

  async function submit(name: string, pass: string) {
    setPending(true)
    setError(null)
    try {
      await login(name.trim(), pass)
    } catch (e) {
      setError(errorKey(e))
      setPending(false)
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void submit(username, password)
  }

  return (
    <div className="flex min-h-screen flex-col">
      <WakingBanner />
      <main className="grid flex-1 place-items-center p-4">
        <div className="w-full max-w-md rounded-lg border border-line bg-surface p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h1 className="font-display text-2xl font-bold">{t('app.name')}</h1>
            <label htmlFor="login-lang" className="sr-only">
              {t('header.language')}
            </label>
            <select
              id="login-lang"
              value={i18n.language}
              onChange={(e) => setLanguage(e.target.value as Language)}
              className="rounded-md border border-line bg-surface px-2 py-1 text-sm"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {lang.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
          <p className="mt-1 text-sm text-text-3">{t('auth.subtitle')}</p>

          <div className="mt-5 grid gap-2">
            {DEMO_ACCOUNTS.map(({ key, username: demoUser }) => (
              <button
                key={key}
                type="button"
                disabled={pending}
                onClick={() => void submit(demoUser, DEMO_PASSWORD)}
                className="rounded-md bg-accent-text px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-text/90 disabled:opacity-60"
              >
                {t(`auth.demo.${key}`)}
              </button>
            ))}
          </div>

          <div className="my-5 flex items-center gap-3 text-xs text-text-3" aria-hidden="true">
            <span className="h-px flex-1 bg-line" />
            {t('auth.or')}
            <span className="h-px flex-1 bg-line" />
          </div>

          <form onSubmit={onSubmit} className="grid gap-3">
            <div>
              <label htmlFor="login-username" className="block text-sm font-medium">
                {t('auth.username')}
              </label>
              <input
                id="login-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                className="mt-1 w-full rounded-md border border-line bg-bg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label htmlFor="login-password" className="block text-sm font-medium">
                {t('auth.password')}
              </label>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                className="mt-1 w-full rounded-md border border-line bg-bg px-3 py-2 text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={pending}
              className="rounded-md border border-line px-4 py-2 text-sm font-semibold hover:bg-bg disabled:opacity-60"
            >
              {pending ? t('auth.signingIn') : t('auth.signIn')}
            </button>
          </form>

          {error && (
            <p
              role="alert"
              className="mt-4 rounded-md bg-prio-urgent-bg px-3 py-2 text-sm text-prio-urgent"
            >
              {t(error)}
            </p>
          )}
        </div>
      </main>
    </div>
  )
}
