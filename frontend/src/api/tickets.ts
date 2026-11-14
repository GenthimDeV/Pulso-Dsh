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
  /** Campo de orden de la API (`-updated_at` por defecto). */
  ordering?: string
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
      ordering: filters.ordering ?? '-updated_at',
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

export interface TicketComment {
  id: number
  author: UserRef
  body: string
  is_internal: boolean
  created_at: string
}

export type TicketEventType =
  'created' | 'assigned' | 'status_changed' | 'commented' | 'internal_note'

export interface TicketEvent {
  id: number
  type: TicketEventType
  actor: UserRef | null
  from_status: Status | ''
  to_status: Status | ''
  created_at: string
}

export interface TicketDetail extends TicketListItem {
  description: string
  comments: TicketComment[]
  events: TicketEvent[]
  allowed_transitions: Status[]
}

export function fetchTicket(code: string, signal?: AbortSignal): Promise<TicketDetail> {
  return apiFetch<TicketDetail>(`/tickets/${encodeURIComponent(code)}/`, { signal })
}

export function transitionTicket(
  code: string,
  to: Status,
  assignee?: number,
): Promise<TicketDetail> {
  return apiFetch<TicketDetail>(`/tickets/${encodeURIComponent(code)}/transition/`, {
    method: 'POST',
    body: assignee === undefined ? { to } : { to, assignee },
  })
}

export function assignTicket(code: string, assignee: number): Promise<TicketDetail> {
  return apiFetch<TicketDetail>(`/tickets/${encodeURIComponent(code)}/assign/`, {
    method: 'POST',
    body: { assignee },
  })
}

export function addComment(
  code: string,
  body: string,
  isInternal: boolean,
): Promise<TicketComment> {
  return apiFetch<TicketComment>(`/tickets/${encodeURIComponent(code)}/comments/`, {
    method: 'POST',
    body: { body, is_internal: isInternal },
  })
}

/** Nombre para mostrar: "Nombre Apellido", o el usuario si no los tiene. */
export function displayName(user: Pick<UserRef, 'username' | 'first_name' | 'last_name'>): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username
}

export interface Category {
  id: number
  name: string
}

export function fetchCategories(signal?: AbortSignal): Promise<Category[]> {
  return apiFetch<Category[]>('/categories/', { signal })
}

export type NewTicketInput = {
  subject: string
  description: string
  category: number
  priority: Priority
}

export function createTicket(input: NewTicketInput): Promise<TicketDetail> {
  return apiFetch<TicketDetail>('/tickets/', { method: 'POST', body: input })
}

/** Longitud máxima del asunto (coincide con el backend). */
export const SUBJECT_MAX = 200
