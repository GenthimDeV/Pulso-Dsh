import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { keepPreviousData, useQueries, useQuery } from '@tanstack/react-query'
import { ApiError } from '../api/errors'
import {
  PAGE_SIZE,
  PRIORITIES,
  STATUSES,
  displayName,
  fetchAgents,
  fetchTickets,
  type Priority,
  type Status,
  type TicketFilters,
  type TicketListItem,
} from '../api/tickets'
import { useAuth } from '../auth/AuthContext'
import {
  PriorityBadge,
  STATUS_DOT_CLASSES,
  StatusBadge,
  UserAvatar,
} from '../components/TicketBadges'
import { useFormatters } from '../i18n/format'

const SEARCH_DEBOUNCE_MS = 300
const FIELD_CLASSES =
  'h-10 rounded-md border border-line bg-surface px-3 text-sm text-text placeholder:text-text-3'
const PAGE_BUTTON_CLASSES =
  'grid size-9 place-items-center rounded-md border border-line bg-surface text-sm hover:bg-bg disabled:cursor-not-allowed disabled:opacity-40'

function parseOption<T extends string>(value: string | null, options: readonly T[]): T | undefined {
  return options.find((option) => option === value)
}

/** `me`, `none` o un id numérico; cualquier otra cosa se ignora (la API la rechazaría con 400). */
function parseAssignee(value: string | null): string | undefined {
  if (value === 'me' || value === 'none') return value
  return value && /^\d{1,9}$/.test(value) ? value : undefined
}

function parsePage(value: string | null): number {
  const page = Number(value)
  return Number.isInteger(page) && page > 0 ? page : 1
}

/** Hasta 5 números de página alrededor de la actual. */
function pageWindow(current: number, total: number): number[] {
  const size = Math.min(5, total)
  const start = Math.max(1, Math.min(current - Math.floor(size / 2), total - size + 1))
  return Array.from({ length: size }, (_, index) => start + index)
}

export function TicketList() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const isAgent = user?.role === 'agent'
  const [params, setParams] = useSearchParams()

  const status = parseOption(params.get('status'), STATUSES)
  const priority = parseOption(params.get('priority'), PRIORITIES)
  const assignee = isAgent ? parseAssignee(params.get('assignee')) : undefined
  const search = params.get('search')?.trim() ?? ''
  const page = parsePage(params.get('page'))

  /** Cambia filtros en la URL; cualquier cambio vuelve a la página 1 salvo que se indique `page`. */
  const update = useCallback(
    (patch: Record<string, string | undefined>, replace = false) => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous)
          if (!('page' in patch)) next.delete('page')
          for (const [key, value] of Object.entries(patch)) {
            if (value) next.set(key, value)
            else next.delete(key)
          }
          return next
        },
        { replace },
      )
    },
    [setParams],
  )

  // Búsqueda: el campo es local y se vuelca a la URL tras una pausa. Si la URL cambia desde fuera
  // (p. ej. la búsqueda de la cabecera) el campo la sigue; se ajusta durante el render, sin efecto.
  const [query, setQuery] = useState(search)
  const [seenSearch, setSeenSearch] = useState(search)
  if (search !== seenSearch) {
    setSeenSearch(search)
    if (query.trim() !== search) setQuery(search)
  }
  useEffect(() => {
    if (query.trim() === search) return
    const timer = setTimeout(() => update({ search: query.trim() }, true), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [query, search, update])

  const filters: TicketFilters = { priority, assignee, search: search || undefined }

  const list = useQuery({
    queryKey: ['tickets', 'list', filters, status, page],
    queryFn: ({ signal }) => fetchTickets({ ...filters, status, page }, signal),
    placeholderData: keepPreviousData,
  })

  // Un contador por estado con los filtros actuales; "Todos" es su suma.
  const counts = useQueries({
    queries: STATUSES.map((s) => ({
      queryKey: ['tickets', 'count', filters, s],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        fetchTickets({ ...filters, status: s, page: 1, pageSize: 1 }, signal),
      placeholderData: keepPreviousData,
    })),
  })
  const countOf = (index: number) => counts[index]?.data?.count
  const totalCount = counts.every((c) => c.data)
    ? counts.reduce((sum, c) => sum + c.data!.count, 0)
    : undefined

  const agents = useQuery({
    queryKey: ['agents'],
    queryFn: ({ signal }) => fetchAgents(signal),
    enabled: isAgent,
    staleTime: 5 * 60_000,
  })

  // Página fuera de rango (p. ej. tras borrar filtros en otra pestaña): vuelve a la primera.
  const outOfRange = list.error instanceof ApiError && list.error.status === 404 && page > 1
  useEffect(() => {
    if (outOfRange) update({})
  }, [outOfRange, update])

  const hasFilters = Boolean(status || priority || assignee || search || query)
  function clearFilters() {
    setQuery('')
    update({ status: undefined, priority: undefined, assignee: undefined, search: undefined })
  }

  const tabs: { key: Status | undefined; label: string; count: number | undefined }[] = [
    { key: undefined, label: t('tickets.tabs.all'), count: totalCount },
    ...STATUSES.map((s, index) => ({
      key: s,
      label: t(`tickets.status.${s}`),
      count: countOf(index),
    })),
  ]

  const rows = list.data?.results ?? []
  const total = list.data?.count ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const from = (currentPage - 1) * PAGE_SIZE + 1
  const to = from + rows.length - 1
  const fetchingNewData = list.isPlaceholderData

  return (
    <section className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="font-display text-3xl font-bold tracking-tight">{t('nav.tickets')}</h1>
        <p className="text-sm text-text-3">
          {isAgent ? t('tickets.subtitleAgent') : t('tickets.subtitleRequester')}
        </p>
      </div>

      <div
        role="tablist"
        aria-label={t('tickets.tabs.label')}
        className="flex flex-wrap gap-1.5 border-b border-line"
      >
        {tabs.map((tab) => {
          const selected = tab.key === status
          return (
            <button
              key={tab.key ?? 'all'}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => update({ status: tab.key })}
              className={`-mb-px inline-flex min-h-11 items-center gap-2 border-b-2 px-3.5 text-sm font-semibold ${
                selected
                  ? 'border-accent text-text'
                  : 'border-transparent text-text-3 hover:text-text'
              }`}
            >
              {tab.key && (
                <span
                  aria-hidden="true"
                  className={`size-2 rounded-full ${STATUS_DOT_CLASSES[tab.key]}`}
                />
              )}
              {tab.label}
              <span
                className={`min-w-6 rounded-full px-2 py-0.5 text-center text-xs ${
                  selected ? 'bg-prio-medium-bg text-accent-text' : 'bg-prio-low-bg text-text-2'
                }`}
              >
                {tab.count ?? '–'}
              </span>
            </button>
          )
        })}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex basis-72 flex-[2_1_18rem] flex-col gap-1.5">
          <label htmlFor="ticket-search" className="text-xs font-semibold text-text-2">
            {t('tickets.filters.search')}
          </label>
          <input
            id="ticket-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('tickets.filters.searchPlaceholder')}
            className={FIELD_CLASSES}
          />
        </div>
        <div className="flex basis-40 flex-[1_1_10rem] flex-col gap-1.5">
          <label htmlFor="ticket-priority" className="text-xs font-semibold text-text-2">
            {t('tickets.filters.priority')}
          </label>
          <select
            id="ticket-priority"
            value={priority ?? ''}
            onChange={(event) => update({ priority: event.target.value })}
            className={FIELD_CLASSES}
          >
            <option value="">{t('tickets.filters.allFeminine')}</option>
            {PRIORITIES.map((p: Priority) => (
              <option key={p} value={p}>
                {t(`tickets.priority.${p}`)}
              </option>
            ))}
          </select>
        </div>
        {isAgent && (
          <div className="flex basis-44 flex-[1_1_11rem] flex-col gap-1.5">
            <label htmlFor="ticket-assignee" className="text-xs font-semibold text-text-2">
              {t('tickets.filters.agent')}
            </label>
            <select
              id="ticket-assignee"
              value={assignee ?? ''}
              onChange={(event) => update({ assignee: event.target.value })}
              className={FIELD_CLASSES}
            >
              <option value="">{t('tickets.filters.allMasculine')}</option>
              <option value="none">{t('tickets.unassigned')}</option>
              <option value="me">{t('tickets.filters.mine')}</option>
              {agents.data?.map((agent) => (
                <option key={agent.id} value={String(agent.id)}>
                  {displayName(agent)}
                </option>
              ))}
            </select>
          </div>
        )}
        <button
          type="button"
          onClick={clearFilters}
          disabled={!hasFilters}
          className="h-10 rounded-md px-3 text-sm font-semibold text-accent-text hover:underline disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:no-underline"
        >
          {t('tickets.filters.clear')}
        </button>
      </div>

      <section
        role="tabpanel"
        aria-label={t('tickets.results')}
        aria-busy={list.isFetching}
        className="overflow-hidden rounded-2xl border border-line bg-surface"
      >
        <div className={`overflow-x-auto ${fetchingNewData ? 'opacity-60' : ''}`}>
          <table className="w-full min-w-[56rem] border-collapse text-sm">
            <thead>
              <tr className="bg-bg/60 text-left text-xs uppercase tracking-wide text-text-3">
                <th scope="col" className="px-5 py-3 font-semibold">
                  {t('tickets.columns.ticket')}
                </th>
                {isAgent && (
                  <th scope="col" className="px-3 py-3 font-semibold">
                    {t('tickets.columns.requester')}
                  </th>
                )}
                <th scope="col" className="px-3 py-3 font-semibold">
                  {t('tickets.columns.priority')}
                </th>
                <th scope="col" className="px-3 py-3 font-semibold">
                  {t('tickets.columns.status')}
                </th>
                <th scope="col" className="px-3 py-3 font-semibold">
                  {t('tickets.columns.agent')}
                </th>
                <th scope="col" className="px-3 py-3 font-semibold">
                  {t('tickets.columns.updated')}
                </th>
                <th scope="col" className="px-5 py-3 text-right font-semibold">
                  {t('tickets.columns.waiting')}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((ticket) => (
                <TicketRow
                  key={ticket.code}
                  ticket={ticket}
                  showRequester={isAgent}
                  now={list.dataUpdatedAt}
                />
              ))}
            </tbody>
          </table>
        </div>

        {list.isPending && (
          <p role="status" className="px-6 py-14 text-center text-sm text-text-3">
            {t('tickets.loading')}
          </p>
        )}

        {list.isError && !outOfRange && (
          <div role="alert" className="flex flex-col items-center gap-3 px-6 py-14 text-center">
            <p className="text-sm text-text-2">
              {list.error instanceof ApiError ? t('errors.unknown') : t('errors.network')}
            </p>
            <button
              type="button"
              onClick={() => void list.refetch()}
              className="rounded-md border border-line px-3 py-2 text-sm font-semibold hover:bg-bg"
            >
              {t('tickets.retry')}
            </button>
          </div>
        )}

        {list.isSuccess && rows.length === 0 && (
          <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
            <svg
              viewBox="0 0 40 40"
              className="size-10 text-text-3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <circle cx="18" cy="18" r="11" />
              <path d="M26 26l8 8M14 18h8" />
            </svg>
            <p className="font-display text-lg font-semibold">{t('tickets.empty.title')}</p>
            <p className="text-sm text-text-3">{t('tickets.empty.hint')}</p>
          </div>
        )}

        {rows.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3.5 text-sm text-text-3">
            <span>{t('tickets.showing', { from, to, total })}</span>
            {totalPages > 1 && (
              <nav aria-label={t('tickets.pagination.label')} className="flex gap-1.5">
                <button
                  type="button"
                  aria-label={t('tickets.pagination.previous')}
                  disabled={currentPage <= 1}
                  onClick={() => update({ page: String(currentPage - 1) })}
                  className={PAGE_BUTTON_CLASSES}
                >
                  ‹
                </button>
                {pageWindow(currentPage, totalPages).map((number) => (
                  <button
                    key={number}
                    type="button"
                    aria-current={number === currentPage ? 'page' : undefined}
                    onClick={() => update({ page: String(number) })}
                    className={`${PAGE_BUTTON_CLASSES} ${
                      number === currentPage
                        ? '!border-sidebar !bg-sidebar font-semibold text-white'
                        : ''
                    }`}
                  >
                    {number}
                  </button>
                ))}
                <button
                  type="button"
                  aria-label={t('tickets.pagination.next')}
                  disabled={currentPage >= totalPages}
                  onClick={() => update({ page: String(currentPage + 1) })}
                  className={PAGE_BUTTON_CLASSES}
                >
                  ›
                </button>
              </nav>
            )}
          </div>
        )}
      </section>
    </section>
  )
}

interface TicketRowProps {
  ticket: TicketListItem
  showRequester: boolean
  /** Instante de la última carga de la lista: referencia estable para "esperando" y el SLA. */
  now: number
}

function TicketRow({ ticket, showRequester, now }: TicketRowProps) {
  const { t } = useTranslation()
  const format = useFormatters()
  const resolved = ticket.status === 'resolved'
  const elapsed = now - new Date(ticket.created_at).getTime()
  const late = !resolved && now > new Date(ticket.sla_due_at).getTime()

  return (
    <tr className="border-t border-line">
      <td className="px-5 py-3.5">
        <Link
          to={`/tickets/${ticket.code}`}
          className="flex flex-col gap-0.5 text-text no-underline hover:text-accent-text"
        >
          <span className="font-mono text-xs text-text-3">
            {ticket.code} · {ticket.category.name}
          </span>
          <span className="font-semibold">{ticket.subject}</span>
        </Link>
      </td>
      {showRequester && (
        <td className="px-3 py-3.5 text-text-2">{displayName(ticket.requester)}</td>
      )}
      <td className="px-3 py-3.5">
        <PriorityBadge priority={ticket.priority} />
      </td>
      <td className="px-3 py-3.5">
        <StatusBadge status={ticket.status} />
      </td>
      <td className="px-3 py-3.5">
        {ticket.assignee ? (
          <span className="inline-flex items-center gap-2 text-text-2">
            <UserAvatar user={ticket.assignee} className="size-6.5 text-[0.6875rem]" />
            {displayName(ticket.assignee)}
          </span>
        ) : (
          <span className="text-text-3">{t('tickets.unassigned')}</span>
        )}
      </td>
      <td className="px-3 py-3.5 text-text-3">
        <time dateTime={ticket.updated_at} title={format.date(ticket.updated_at)}>
          {format.relative(ticket.updated_at)}
        </time>
      </td>
      <td className="px-5 py-3.5 text-right">
        {resolved ? (
          <span className="text-text-3">—</span>
        ) : (
          <span
            title={late ? t('tickets.slaBreached') : undefined}
            className={`inline-block rounded-md px-2 py-1 font-mono text-xs font-medium ${
              late ? 'bg-prio-urgent-bg text-prio-urgent' : 'text-text-2'
            }`}
          >
            {format.duration(elapsed)}
          </span>
        )}
      </td>
    </tr>
  )
}
