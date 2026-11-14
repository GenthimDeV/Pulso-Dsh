import { apiFetch } from './client'

export const STATUSES = ['open', 'assigned', 'in_progress', 'resolved'] as const
export type Status = (typeof STATUSES)[number]

export const PRIORITIES = ['urgent', 'high', 'medium', 'low'] as const
export type Priority = (typeof PRIORITIES)[number]

/** Referencia mínima a un usuario (solicitante, asignado). */
export interface UserRef {
  id: number
  username: string
  first_name: string
  last_name: string
}

export interface TicketListItem {
  code: string
  subject: string
  priority: Priority
  status: Status
  category: { id: number; name: string }
  requester: UserRef
  assignee: UserRef | null
  created_at: string
  updated_at: string
  resolved_at: string | null
  sla_due_at: string
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface TicketFilters {
  status?: Status
  priority?: Priority
  /** Id de agente, `me` o `none`. */
  assignee?: string
  search?: string
  page?: number
  pageSize?: number
}

export const PAGE_SIZE = 20

export function fetchTickets(
  filters: TicketFilters,
  signal?: AbortSignal,
): Promise<Page<TicketListItem>> {
  return apiFetch<Page<TicketListItem>>('/tickets/', {
    signal,
    params: {
      status: filters.status,
      priority: filters.priority,
      assignee: filters.assignee,
      search: filters.search,
      page: filters.page,
      page_size: filters.pageSize ?? PAGE_SIZE,
      ordering: '-updated_at',
    },
  })
}

export interface Agent {
  id: number
  username: string
  first_name: string
  last_name: string
  team: string
  assigned: number
  in_progress: number
  capacity: number
}

export function fetchAgents(signal?: AbortSignal): Promise<Agent[]> {
  return apiFetch<Agent[]>('/agents/', { signal })
}

/** Nombre para mostrar: "Nombre Apellido", o el usuario si no los tiene. */
export function displayName(user: Pick<UserRef, 'username' | 'first_name' | 'last_name'>): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username
}
