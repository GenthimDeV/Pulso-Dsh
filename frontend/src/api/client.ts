import { ApiError, isWakingError, NetworkError } from './errors'
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

/** Cliente único de la API. Lanza `ApiError` (HTTP no 2xx) o `NetworkError` (sin respuesta). */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
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
