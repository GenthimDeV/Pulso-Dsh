import type { Role } from '../api/session'

export const AGENT_ONLY: readonly Role[] = ['agent']
export const ALL_ROLES: readonly Role[] = ['agent', 'requester']

/** Pantalla de inicio de cada rol: el solicitante no tiene panel. */
export function homeFor(role: Role): string {
  return role === 'agent' ? '/' : '/tickets'
}
