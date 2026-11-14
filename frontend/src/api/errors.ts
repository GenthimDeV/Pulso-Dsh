/** Error devuelto por la API (HTTP no 2xx). El backend responde con códigos, no con textos. */
export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown) {
    super(`API ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

/** No hubo respuesta HTTP: red caída, CORS o servidor dormido que aún no contesta. */
export class NetworkError extends Error {
  constructor(options?: ErrorOptions) {
    super('Network error', options)
    this.name = 'NetworkError'
  }
}

const WAKING_STATUSES = [502, 503, 504]

/** Fallos típicos del arranque en frío de Render: merecen reintento automático. */
export function isWakingError(error: unknown): boolean {
  if (error instanceof NetworkError) return true
  return error instanceof ApiError && WAKING_STATUSES.includes(error.status)
}
