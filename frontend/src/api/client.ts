import { ApiError, isWakingError, NetworkError } from './errors'
import { getAccessToken, getRefreshToken, expireSession, setTokens } from './tokens'
import { markAwake, markWaking, watchSlowRequest } from './serverState'

// Sin barra final. En desarrollo apunta al backend local.
const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1').replace(
  /\/+$/,
  '',
)

type Json = Record<string, unknown> | unknown[]

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: Json
  params?: Record<string, string | number | undefined>
  signal?: AbortSignal
  /** `false` en las llamadas de login, refresh y logout: sin cabecera ni reintento por 401. */
  auth?: boolean
}

function buildUrl(path: string, params?: RequestOptions['params']): string {
  const url = new URL(`${BASE_URL}${path}`)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== '') url.searchParams.set(key, String(value))
  }
  return url.toString()
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

async function rawFetch<T>(
  path: string,
  options: RequestOptions,
  token: string | null,
): Promise<T> {
  const { method = 'GET', body, params, signal } = options
  const stopWatching = watchSlowRequest()
  try {
    let response: Response
    try {
      response = await fetch(buildUrl(path, params), {
        method,
        signal,
        headers: {
          Accept: 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
          ...(body !== undefined && { 'Content-Type': 'application/json' }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new NetworkError({ cause: error })
    }

    const data = await parseBody(response)
    if (!response.ok) throw new ApiError(response.status, data)
    markAwake()
    return data as T
  } catch (error) {
    if (isWakingError(error)) markWaking()
    throw error
  } finally {
    stopWatching()
  }
}

interface TokenPair {
  access: string
  refresh: string
}

let refreshing: Promise<string | null> | null = null

async function doRefresh(): Promise<string | null> {
  const refresh = getRefreshToken()
  if (!refresh) return null
  try {
    const data = await rawFetch<TokenPair>(
      '/auth/token/refresh/',
      { method: 'POST', body: { refresh } },
      null,
    )
    setTokens(data.access, data.refresh)
    return data.access
  } catch (error) {
    // Refresh rechazado (caducado, en blacklist o malformado): no hay forma de recuperar la sesión.
    if (error instanceof ApiError && (error.status === 401 || error.status === 400)) return null
    // Red caída, servidor dormido o 429: el refresh puede seguir siendo válido; no se descarta.
    throw error
  }
}

/**
 * Renueva el access con el refresh. Una sola petición a la vez: el refresh rota en cada uso, así
 * que dos llamadas simultáneas (p. ej. StrictMode) invalidarían la segunda.
 */
export function refreshAccessToken(): Promise<string | null> {
  refreshing ??= doRefresh().finally(() => {
    refreshing = null
  })
  return refreshing
}

/**
 * Cliente único de la API. Lanza `ApiError` (HTTP no 2xx) o `NetworkError` (sin respuesta).
 * Con `auth` (por defecto) envía el access y, ante un 401, renueva la sesión y reintenta una vez.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (options.auth === false) return rawFetch<T>(path, options, null)
  try {
    return await rawFetch<T>(path, options, getAccessToken())
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error
    let token: string | null
    try {
      token = await refreshAccessToken()
    } catch {
      throw error
    }
    if (!token) {
      expireSession()
      throw error
    }
    return rawFetch<T>(path, options, token)
  }
}
