import { useSyncExternalStore } from 'react'

/**
 * Estado "¿está despertando el servidor?". Pequeño almacén externo (sin librería):
 * - una petición que tarda más de SLOW_MS sin respuesta,
 * - o un fallo de arranque en frío (red, 502/503/504),
 * marcan el servidor como dormido hasta que una petición se complete bien.
 */
const SLOW_MS = 4000

let waking = false
const listeners = new Set<() => void>()

function setWaking(value: boolean) {
  if (waking === value) return
  waking = value
  listeners.forEach((l) => l())
}

export function markWaking() {
  setWaking(true)
}

export function markAwake() {
  setWaking(false)
}

/** Arranca el temporizador de "petición lenta"; devuelve la función que lo cancela. */
export function watchSlowRequest(): () => void {
  const id = setTimeout(markWaking, SLOW_MS)
  return () => clearTimeout(id)
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useServerWaking(): boolean {
  return useSyncExternalStore(subscribe, () => waking)
}
