import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { isWakingError } from '../api/errors'
import { login as apiLogin, logout as apiLogout, restoreSession, type Me } from '../api/session'
import { onSessionExpired } from '../api/tokens'

type Status = 'loading' | 'authenticated' | 'anonymous'

interface AuthValue {
  status: Status
  user: Me | null
  login: (username: string, password: string) => Promise<Me>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

const MAX_RESTORE_RETRIES = 8
const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/** Restaura la sesión; con el servidor dormido reintenta en lugar de expulsar al usuario. */
async function restoreWithRetry(signal: { cancelled: boolean }): Promise<Me | null> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await restoreSession()
    } catch (error) {
      if (signal.cancelled || !isWakingError(error) || attempt >= MAX_RESTORE_RETRIES) throw error
      await wait(Math.min(1000 * 2 ** attempt, 10_000))
    }
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<Status>('loading')
  const [user, setUser] = useState<Me | null>(null)

  const clearSession = useCallback(() => {
    setUser(null)
    setStatus('anonymous')
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    const signal = { cancelled: false }
    restoreWithRetry(signal)
      .then((me) => {
        if (signal.cancelled) return
        if (me) {
          setUser(me)
          setStatus('authenticated')
        } else {
          setStatus('anonymous')
        }
      })
      .catch(() => {
        if (!signal.cancelled) setStatus('anonymous')
      })
    return () => {
      signal.cancelled = true
    }
  }, [])

  // Refresh rechazado en mitad de una petición: se vuelve al login.
  useEffect(() => onSessionExpired(clearSession), [clearSession])

  const login = useCallback(
    async (username: string, password: string) => {
      const me = await apiLogin(username, password)
      queryClient.clear()
      setUser(me)
      setStatus('authenticated')
      return me
    },
    [queryClient],
  )

  const logout = useCallback(async () => {
    await apiLogout()
    clearSession()
  }, [clearSession])

  const value = useMemo(() => ({ status, user, login, logout }), [status, user, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return value
}
