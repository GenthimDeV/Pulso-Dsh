import { apiFetch, refreshAccessToken } from './client'
import { clearTokens, getRefreshToken, setTokens } from './tokens'

export type Role = 'agent' | 'requester'

/** Respuesta de `GET /me/`. `role` es `null` para usuarios sin perfil (p. ej. superusuario). */
export interface Me {
  id: number
  username: string
  first_name: string
  last_name: string
  role: Role | null
  team: string
}

interface TokenPair {
  access: string
  refresh: string
}

export function fetchMe(): Promise<Me> {
  return apiFetch<Me>('/me/')
}

export async function login(username: string, password: string): Promise<Me> {
  const tokens = await apiFetch<TokenPair>('/auth/token/', {
    method: 'POST',
    body: { username, password },
    auth: false,
  })
  setTokens(tokens.access, tokens.refresh)
  try {
    return await fetchMe()
  } catch (error) {
    clearTokens()
    throw error
  }
}

/** Recupera la sesión guardada (si la hay). `null` = no hay sesión o ya no es válida. */
export async function restoreSession(): Promise<Me | null> {
  if (!getRefreshToken()) return null
  const access = await refreshAccessToken()
  if (!access) {
    clearTokens()
    return null
  }
  return fetchMe()
}

/** Cierra la sesión. Siempre limpia el estado local; el aviso al servidor es de mejor esfuerzo. */
export async function logout(): Promise<void> {
  const refresh = getRefreshToken()
  clearTokens()
  if (!refresh) return
  try {
    await apiFetch('/auth/logout/', { method: 'POST', body: { refresh }, auth: false })
  } catch {
    // 401 = el refresh ya estaba en la blacklist: la sesión ya estaba cerrada. Cualquier otro
    // fallo (red, 429) tampoco debe impedir salir; el refresh caduca por sí solo.
  }
}
