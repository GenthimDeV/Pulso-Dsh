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

// Generación de sesión: sube con cada login y cada limpieza. Una renovación que empezó en una
// generación anterior no puede escribir sus tokens (evita que reviva o pise una sesión posterior).
let generation = 0

export function getSessionGeneration(): number {
  return generation
}

function writeTokens(access: string, refresh?: string) {
  accessToken = access
  if (refresh === undefined) return
  try {
    localStorage.setItem(REFRESH_KEY, refresh)
  } catch {
    // Sin localStorage la sesión dura hasta recargar la página.
  }
}

/** Login nuevo: abre una generación nueva e invalida las renovaciones en vuelo. */
export function startSession(access: string, refresh: string) {
  generation++
  writeTokens(access, refresh)
}

/**
 * Guarda los tokens de una renovación (el refresh rota en cada uso). Si la sesión cambió desde que
 * empezó (`startedAt`), los descarta y devuelve `false`.
 */
export function setRefreshedTokens(access: string, refresh: string, startedAt: number): boolean {
  if (startedAt !== generation) return false
  writeTokens(access, refresh)
  return true
}

export function clearTokens() {
  generation++
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
