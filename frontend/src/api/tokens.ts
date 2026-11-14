// Almacén de tokens. El access vive solo en memoria; el refresh se guarda en localStorage para
// sobrevivir a una recarga (la demo usa JWT entre dominios distintos, sin cookies).
const REFRESH_KEY = 'pulso.refresh'

let accessToken: string | null = null
const expiredListeners = new Set<() => void>()

export function getAccessToken(): string | null {
  return accessToken
}

export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY)
  } catch {
    return null
  }
}

/** Guarda el access y, si llega uno nuevo (el refresh rota en cada uso), también el refresh. */
export function setTokens(access: string, refresh?: string) {
  accessToken = access
  if (refresh === undefined) return
  try {
    localStorage.setItem(REFRESH_KEY, refresh)
  } catch {
    // Sin localStorage la sesión dura hasta recargar la página.
  }
}

export function clearTokens() {
  accessToken = null
  try {
    localStorage.removeItem(REFRESH_KEY)
  } catch {
    // Nada que limpiar.
  }
}

/** Avisa a la interfaz de que la sesión ya no es válida (refresh rechazado). */
export function onSessionExpired(listener: () => void): () => void {
  expiredListeners.add(listener)
  return () => expiredListeners.delete(listener)
}

export function expireSession() {
  clearTokens()
  expiredListeners.forEach((listener) => listener())
}
