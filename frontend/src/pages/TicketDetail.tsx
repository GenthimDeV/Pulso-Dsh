import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { ApiError, NetworkError } from '../api/errors'
import {
  STATUSES,
  addComment,
  assignTicket,
  displayName,
  fetchAgents,
  fetchTicket,
  transitionTicket,
  type Status,
  type TicketDetail as TicketDetailData,
  type TicketEvent,
} from '../api/tickets'
import { useAuth } from '../auth/AuthContext'
import { PriorityBadge, STATUS_DOT_CLASSES, UserAvatar } from '../components/TicketBadges'
import { useFormatters } from '../i18n/format'

const STEP_BAR_CLASSES: Record<Status, string> = {
  open: 'bg-st-open',
  assigned: 'bg-st-assigned',
  in_progress: 'bg-st-in-progress',
  resolved: 'bg-st-resolved',
}

const CARD_CLASSES = 'rounded-2xl border border-line bg-surface'
const FIELD_CLASSES =
  'rounded-md border border-line bg-bg px-3 text-sm text-text placeholder:text-text-3 disabled:cursor-not-allowed disabled:opacity-60'

/** Código estable de un error de la API: `{"code": ...}` del servicio o `{campo: código}`. */
function apiCode(error: ApiError): string | undefined {
  const body = error.body
  if (typeof body !== 'object' || body === null) return undefined
  const record = body as Record<string, unknown>
  if (typeof record.code === 'string') return record.code
  const first = Object.values(record).find((value) => typeof value === 'string')
  return typeof first === 'string' ? first : undefined
}

function errorMessage(error: unknown, t: TFunction): string {
  if (error instanceof NetworkError) return t('errors.network')
  if (!(error instanceof ApiError)) return t('detail.errors.generic')
  const code = apiCode(error)
  if (error.status === 403) return t('detail.errors.forbidden')
  switch (code) {
    case 'invalid_transition': {
      // `assign` sobre un resuelto responde con `from == to`: hay que reabrirlo antes.
      const body = error.body as { from?: string; to?: string }
      return body.from !== undefined && body.from === body.to
        ? t('detail.errors.reopenFirst')
        : t('detail.errors.invalidTransition')
    }
    case 'assignee_required':
      return t('detail.errors.assigneeRequired')
    case 'invalid_assignee':
    case 'does_not_exist':
    case 'incorrect_type':
      return t('detail.errors.invalidAssignee')
    case 'blank':
    case 'required':
    case 'null':
      return t('detail.errors.blank')
    case 'max_length':
      return t('detail.errors.tooLong')
    default:
      return t('detail.errors.generic')
  }
}

export function TicketDetail() {
  const { t } = useTranslation()
  const { code = '' } = useParams()
  const { user } = useAuth()
  const isAgent = user?.role === 'agent'

  const ticket = useQuery({
    queryKey: ['tickets', 'detail', code],
    queryFn: ({ signal }) => fetchTicket(code, signal),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  })

  const back = (
    <Link to="/tickets" className="text-sm font-semibold text-accent-text hover:underline">
      ← {t('detail.back')}
    </Link>
  )

  if (ticket.isPending) {
    return (
      <section className="flex flex-col gap-4">
        {back}
        <p role="status" className="py-14 text-center text-sm text-text-3">
          {t('detail.loading')}
        </p>
      </section>
    )
  }

  if (ticket.isError) {
    const notFound = ticket.error instanceof ApiError && ticket.error.status === 404
    return (
      <section className="flex flex-col gap-4">
        {back}
        <div role="alert" className="flex flex-col items-center gap-3 py-14 text-center">
          {notFound ? (
            <>
              <p className="font-display text-lg font-semibold">{t('detail.notFound')}</p>
              <p className="text-sm text-text-3">{t('detail.notFoundHint')}</p>
            </>
          ) : (
            <>
              <p className="text-sm text-text-2">
                {ticket.error instanceof ApiError ? t('errors.unknown') : t('errors.network')}
              </p>
              <button
                type="button"
                onClick={() => void ticket.refetch()}
                className="rounded-md border border-line px-3 py-2 text-sm font-semibold hover:bg-bg"
              >
                {t('tickets.retry')}
              </button>
            </>
          )}
        </div>
      </section>
    )
  }

  return (
    <TicketView
      ticket={ticket.data}
      loadedAt={ticket.dataUpdatedAt}
      isAgent={isAgent}
      back={back}
    />
  )
}

interface TicketViewProps {
  ticket: TicketDetailData
  /** Instante de la última carga: referencia estable para el SLA (como en la lista). */
  loadedAt: number
  isAgent: boolean
  back: React.ReactNode
}

function TicketView({ ticket, loadedAt, isAgent, back }: TicketViewProps) {
  const { t } = useTranslation()
  const format = useFormatters()
  const queryClient = useQueryClient()
  const detailKey = ['tickets', 'detail', ticket.code]

  const [message, setMessage] = useState<string | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [internal, setInternal] = useState(false)

  const agents = useQuery({
    queryKey: ['agents'],
    queryFn: ({ signal }) => fetchAgents(signal),
    enabled: isAgent,
    staleTime: 5 * 60_000,
  })

  const refreshLists = () => {
    void queryClient.invalidateQueries({ queryKey: ['tickets', 'list'] })
    void queryClient.invalidateQueries({ queryKey: ['tickets', 'count'] })
  }

  function handleSuccess(data: TicketDetailData, success: string) {
    queryClient.setQueryData(detailKey, data)
    refreshLists()
    setFailure(null)
    setMessage(success)
  }

  function handleError(error: unknown) {
    setMessage(null)
    setFailure(errorMessage(error, t))
    // Un 409 suele indicar datos obsoletos: se vuelve a cargar el ticket.
    if (error instanceof ApiError && error.status === 409) {
      void queryClient.invalidateQueries({ queryKey: detailKey })
    }
  }

  const move = useMutation({
    mutationFn: (to: Status) => transitionTicket(ticket.code, to),
    onSuccess: (data, to) =>
      handleSuccess(data, t('detail.moved', { status: t(`tickets.status.${to}`) })),
    onError: handleError,
  })

  const assign = useMutation({
    mutationFn: (agentId: number) => assignTicket(ticket.code, agentId),
    onSuccess: (data) =>
      handleSuccess(
        data,
        t('detail.assigned', { name: data.assignee ? displayName(data.assignee) : '' }),
      ),
    onError: handleError,
  })

  const comment = useMutation({
    mutationFn: (input: { body: string; internal: boolean }) =>
      addComment(ticket.code, input.body, input.internal),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: detailKey })
      refreshLists()
      setFailure(null)
      setMessage(null)
      setDraft('')
      setInternal(false)
    },
    onError: handleError,
  })

  function submitComment(event: FormEvent) {
    event.preventDefault()
    const body = draft.trim()
    if (!body) {
      setMessage(null)
      setFailure(t('detail.errors.blank'))
      return
    }
    comment.mutate({ body, internal: isAgent && internal })
  }

  const resolved = ticket.status === 'resolved'
  const busy = move.isPending || assign.isPending
  const created = new Date(ticket.created_at).getTime()
  const due = new Date(ticket.sla_due_at).getTime()
  const target = due - created
  const end = ticket.resolved_at ? new Date(ticket.resolved_at).getTime() : loadedAt
  const elapsed = end - created
  const late = resolved ? elapsed > target : loadedAt > due
  const slaPercent = target > 0 ? Math.min(100, Math.round((elapsed / target) * 100)) : 100

  const slaLabel = resolved
    ? t('detail.slaMet', { time: format.duration(elapsed) })
    : late
      ? t('detail.slaOverdue', { time: format.duration(loadedAt - due) })
      : t('detail.slaRemaining', { time: format.duration(due - loadedAt) })

  const stepIndex = STATUSES.indexOf(ticket.status)
  const knownAssignee = agents.data?.some((agent) => agent.id === ticket.assignee?.id) ?? false

  return (
    <article className="flex flex-col gap-6">
      {back}

      <section className={`${CARD_CLASSES} flex flex-col gap-6 p-6 sm:p-7`}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 flex-[1_1_26rem] flex-col gap-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm text-text-3">{ticket.code}</span>
              <PriorityBadge priority={ticket.priority} />
              <span className="rounded-full bg-prio-low-bg px-2.5 py-1 text-xs font-semibold text-prio-low">
                {ticket.category.name}
              </span>
            </div>
            <h1 className="font-display text-3xl font-bold leading-tight tracking-tight">
              {ticket.subject}
            </h1>
            <p className="text-sm text-text-3">
              {t('detail.openedBy')}{' '}
              <strong className="font-semibold text-text">{displayName(ticket.requester)}</strong> ·{' '}
              <time dateTime={ticket.created_at}>{format.date(ticket.created_at)}</time>
            </p>
          </div>
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <span
              className={`rounded-lg px-2.5 py-1.5 font-mono text-xs font-medium ${
                late ? 'bg-prio-urgent-bg text-prio-urgent' : 'bg-prio-low-bg text-text-2'
              }`}
            >
              {slaLabel}
            </span>
            <span className="text-xs text-text-3">
              {t('detail.slaTarget', { time: format.duration(target) })}
            </span>
          </div>
        </div>

        <ol aria-label={t('detail.stepper')} className="m-0 grid list-none grid-cols-4 gap-2 p-0">
          {STATUSES.map((status, index) => {
            const reached = index <= stepIndex
            return (
              <li
                key={status}
                aria-current={index === stepIndex ? 'step' : undefined}
                className="flex flex-col gap-2"
              >
                <div
                  className={`h-1.5 rounded-full ${reached ? STEP_BAR_CLASSES[ticket.status] : 'bg-line'}`}
                />
                <span
                  className={`text-[0.8125rem] ${
                    index === stepIndex ? 'font-bold text-text' : 'font-medium'
                  } ${reached ? 'text-text' : 'text-text-3'}`}
                >
                  {t(`tickets.status.${status}`)}
                </span>
              </li>
            )
          })}
        </ol>

        {isAgent && (
          <div className="flex flex-col gap-2 border-t border-line pt-4">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="mr-1.5 text-[0.8125rem] font-semibold text-text-2">
                {t('detail.moveTo')}
              </span>
              {STATUSES.filter((status) => status !== ticket.status).map((status) => {
                const reopen = ticket.status === 'resolved' && status === 'in_progress'
                const label = reopen ? t('detail.reopen') : t(`tickets.status.${status}`)
                const valid = ticket.allowed_transitions.includes(status)
                // Desde `open` no hay agente al que pasar: se asigna con el selector de Detalles.
                const needsAgent = valid && ticket.status === 'open' && status === 'assigned'
                const enabled = valid && !needsAgent && !busy
                const title = needsAgent
                  ? t('detail.needsAgentTitle')
                  : valid
                    ? t('detail.moveTitle', { status: t(`tickets.status.${status}`) })
                    : t('detail.invalidTitle', { status: t(`tickets.status.${ticket.status}`) })
                return (
                  <button
                    key={status}
                    type="button"
                    disabled={!enabled}
                    title={title}
                    onClick={() => {
                      setMessage(null)
                      setFailure(null)
                      move.mutate(status)
                    }}
                    className={`inline-flex h-10 items-center rounded-md px-4 text-sm font-semibold ${
                      !valid || needsAgent
                        ? 'border border-dashed border-[#c5cbd5] bg-bg text-[#6b7385] line-through'
                        : status === 'resolved'
                          ? 'border-0 bg-st-resolved text-white hover:opacity-90'
                          : 'border border-sidebar bg-surface text-text hover:bg-bg'
                    } ${enabled || !valid || needsAgent ? '' : 'opacity-60'}`}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
            <p className="text-xs text-text-3">{t('detail.moveHint')}</p>
          </div>
        )}

        <div aria-live="polite" className="empty:hidden">
          {message && (
            <p role="status" className="text-[0.8125rem] text-st-resolved">
              {message}
            </p>
          )}
          {failure && (
            <p role="alert" className="text-[0.8125rem] font-medium text-prio-urgent">
              {failure}
            </p>
          )}
        </div>
      </section>

      <div className="flex flex-wrap items-start gap-6">
        <section
          aria-labelledby="detail-conversation"
          className="flex min-w-0 flex-[999_1_32rem] flex-col gap-4"
        >
          <h2 id="detail-conversation" className="font-display text-lg font-semibold">
            {t('detail.conversation')}
          </h2>

          <MessageCard
            author={ticket.requester}
            role="requester"
            time={ticket.created_at}
            label={t('detail.description')}
            body={ticket.description}
          />
          {ticket.comments.map((item) => (
            <MessageCard
              key={item.id}
              author={item.author}
              role={item.author.id === ticket.requester.id ? 'requester' : 'agent'}
              time={item.created_at}
              body={item.body}
              internal={item.is_internal}
            />
          ))}

          <form
            onSubmit={submitComment}
            className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4.5"
          >
            <label htmlFor="comment-body" className="text-[0.8125rem] font-semibold text-text-2">
              {t('detail.addComment')}
            </label>
            <textarea
              id="comment-body"
              rows={3}
              value={draft}
              maxLength={5000}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={
                isAgent
                  ? t('detail.commentPlaceholderAgent')
                  : t('detail.commentPlaceholderRequester')
              }
              className={`${FIELD_CLASSES} resize-y py-3 leading-normal`}
            />
            <div className="flex flex-wrap items-center justify-between gap-3">
              {isAgent ? (
                <label className="inline-flex min-h-11 cursor-pointer items-center gap-2.5 text-sm text-text-2">
                  <input
                    type="checkbox"
                    checked={internal}
                    onChange={(event) => setInternal(event.target.checked)}
                    className="size-4.5 accent-accent"
                  />
                  {t('detail.internalNote')}
                </label>
              ) : (
                <span />
              )}
              <button
                type="submit"
                disabled={comment.isPending}
                className="inline-flex h-10.5 items-center rounded-md bg-accent px-4.5 text-sm font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {comment.isPending ? t('detail.sending') : t('detail.send')}
              </button>
            </div>
          </form>
        </section>

        <aside
          aria-label={t('detail.detailsLabel')}
          className="flex min-w-0 flex-[1_1_18rem] flex-col gap-4"
        >
          <section
            aria-labelledby="detail-details"
            className={`${CARD_CLASSES} flex flex-col gap-4 p-5.5`}
          >
            <h2 id="detail-details" className="font-display text-base font-semibold">
              {t('detail.details')}
            </h2>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="detail-assignee" className="text-xs font-semibold text-text-2">
                {t('detail.assignee')}
              </label>
              {isAgent ? (
                <>
                  <select
                    id="detail-assignee"
                    value={ticket.assignee?.id ?? ''}
                    disabled={resolved || busy || agents.isPending}
                    onChange={(event) => {
                      const id = Number(event.target.value)
                      if (!id) return
                      setMessage(null)
                      setFailure(null)
                      assign.mutate(id)
                    }}
                    className={`${FIELD_CLASSES} h-10.5`}
                  >
                    {!ticket.assignee && <option value="">{t('detail.chooseAgent')}</option>}
                    {ticket.assignee && !knownAssignee && (
                      <option value={ticket.assignee.id}>{displayName(ticket.assignee)}</option>
                    )}
                    {agents.data?.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {displayName(agent)}
                      </option>
                    ))}
                  </select>
                  {resolved && <p className="text-xs text-text-3">{t('detail.reopenFirst')}</p>}
                </>
              ) : (
                <p id="detail-assignee" className="flex items-center gap-2 text-sm">
                  {ticket.assignee ? (
                    <>
                      <UserAvatar user={ticket.assignee} className="size-6.5 text-[0.6875rem]" />
                      {displayName(ticket.assignee)}
                    </>
                  ) : (
                    <span className="text-text-3">{t('tickets.unassigned')}</span>
                  )}
                </p>
              )}
            </div>

            <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm">
              <dt className="text-text-3">{t('detail.status')}</dt>
              <dd className="m-0 flex items-center gap-2 font-semibold">
                <span
                  aria-hidden="true"
                  className={`size-2 rounded-full ${STATUS_DOT_CLASSES[ticket.status]}`}
                />
                {t(`tickets.status.${ticket.status}`)}
              </dd>
              <dt className="text-text-3">{t('detail.priority')}</dt>
              <dd className="m-0 font-semibold">{t(`tickets.priority.${ticket.priority}`)}</dd>
              <dt className="text-text-3">{t('detail.category')}</dt>
              <dd className="m-0">{ticket.category.name}</dd>
              <dt className="text-text-3">{t('detail.requester')}</dt>
              <dd className="m-0">{displayName(ticket.requester)}</dd>
              <dt className="text-text-3">{t('detail.created')}</dt>
              <dd className="m-0">{format.date(ticket.created_at)}</dd>
              <dt className="text-text-3">{t('detail.comments')}</dt>
              <dd className="m-0">{ticket.comments.length}</dd>
            </dl>

            <div className="flex flex-col gap-2 pt-1">
              <div className="flex justify-between text-xs text-text-2">
                <span>{t('detail.slaTime')}</span>
                <span
                  className={`font-mono ${late ? 'text-prio-urgent' : ''}`}
                >{`${format.duration(elapsed)} / ${format.duration(target)}`}</span>
              </div>
              <div
                role="progressbar"
                aria-label={t('detail.slaTime')}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={slaPercent}
                className={`h-2 overflow-hidden rounded-full ${late ? 'bg-prio-urgent-bg' : 'bg-line'}`}
              >
                <div
                  style={{ width: `${slaPercent}%` }}
                  className={`h-2 rounded-full ${late ? 'bg-chart-urgent' : 'bg-accent'}`}
                />
              </div>
            </div>
          </section>

          <section
            aria-labelledby="detail-history"
            className={`${CARD_CLASSES} flex flex-col gap-4 p-5.5`}
          >
            <h2 id="detail-history" className="font-display text-base font-semibold">
              {t('detail.history')}
            </h2>
            <ol className="m-0 flex list-none flex-col p-0">
              {[...ticket.events].reverse().map((event, index, all) => (
                <HistoryItem key={event.id} event={event} last={index === all.length - 1} />
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </article>
  )
}

interface MessageCardProps {
  author: TicketDetailData['requester']
  role: 'agent' | 'requester'
  time: string
  body: string
  /** Etiqueta tras la hora (p. ej. "descripción"). */
  label?: string
  internal?: boolean
}

function MessageCard({ author, role, time, body, label, internal = false }: MessageCardProps) {
  const { t } = useTranslation()
  const format = useFormatters()
  return (
    <article
      className={`flex flex-col gap-3 rounded-2xl border p-5.5 ${
        internal ? 'border-[#f2d78a] bg-[#fff8e1]' : 'border-line bg-surface'
      }`}
    >
      <div className="flex flex-wrap items-center gap-3">
        <UserAvatar user={author} className="size-9 text-[0.8125rem]" />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-sm font-semibold">
            {displayName(author)}{' '}
            <span className="font-normal text-text-3">
              · {role === 'agent' ? t('detail.roleAgent') : t('detail.roleRequester')}
            </span>
          </span>
          <span className="text-xs text-text-3">
            <time dateTime={time}>{format.date(time)}</time>
            {label && ` · ${label}`}
          </span>
        </div>
        {internal && (
          <span className="rounded-md bg-[#ffe9a8] px-2 py-1 text-[0.6875rem] font-bold tracking-wide text-[#5e4300]">
            {t('detail.internalBadge')}
          </span>
        )}
      </div>
      <p className="m-0 whitespace-pre-wrap break-words text-[0.9375rem] leading-relaxed text-[#2a303c]">
        {body}
      </p>
    </article>
  )
}

function HistoryItem({ event, last }: { event: TicketEvent; last: boolean }) {
  const { t } = useTranslation()
  const format = useFormatters()
  const to = event.to_status || undefined

  let text: string
  switch (event.type) {
    case 'created':
      text = t('detail.event.created')
      break
    case 'assigned':
      text =
        event.from_status && event.from_status === event.to_status
          ? t('detail.event.reassigned')
          : t('detail.event.assigned')
      break
    case 'status_changed':
      text = to
        ? t(event.from_status === 'resolved' ? 'detail.event.reopened' : 'detail.event.movedTo', {
            status: t(`tickets.status.${to}`),
          })
        : t('detail.event.assigned')
      break
    case 'commented':
      text = t('detail.event.commented')
      break
    case 'internal_note':
      text = t('detail.event.internalNote')
      break
  }

  return (
    <li className="flex gap-3">
      <div className="flex flex-col items-center">
        <span
          aria-hidden="true"
          className={`mt-1 size-3 shrink-0 rounded-full ${to ? STATUS_DOT_CLASSES[to] : 'bg-text-3'}`}
        />
        <span
          aria-hidden="true"
          className={`w-0.5 flex-1 ${last ? 'bg-transparent' : 'bg-line'}`}
        />
      </div>
      <div className="flex flex-col gap-0.5 pb-4">
        <span className="text-sm leading-snug">{text}</span>
        <span className="font-mono text-[0.6875rem] text-text-3">
          {format.date(event.created_at)} ·{' '}
          {event.actor ? displayName(event.actor) : t('detail.system')}
        </span>
      </div>
    </li>
  )
}
