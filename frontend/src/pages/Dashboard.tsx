import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQueries, useQuery } from '@tanstack/react-query'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  DEFAULT_RANGE,
  RANGES,
  fetchMetrics,
  type MetricsSummary,
  type Range,
  type WeeklyResolution,
} from '../api/metrics'
import {
  PRIORITIES,
  STATUSES,
  displayName,
  fetchAgents,
  fetchTickets,
  type Agent,
  type Priority,
  type Status,
  type TicketListItem,
} from '../api/tickets'
import { useAuth } from '../auth/AuthContext'
import { PriorityBadge, STATUS_DOT_CLASSES, UserAvatar } from '../components/TicketBadges'
import { useFormatters } from '../i18n/format'

const ACCENT = '#4c6fff'
const TARGET_COLOR = '#0e7c66'
const GRID_COLOR = '#eef0f3'
const SPARK_ON_DARK = '#8fe3cf'
/** Horas de SLA por prioridad (brief §4); el backend guarda solo `sla_due_at`. */
const SLA_HOURS: Record<Priority, number> = { urgent: 2, high: 8, medium: 24, low: 72 }
const PRIORITY_COLORS: Record<Priority, string> = {
  urgent: 'bg-chart-urgent',
  high: 'bg-chart-high',
  medium: 'bg-chart-medium',
  low: 'bg-chart-low',
}
/** Estados en los que un ticket sigue vivo: los candidatos a "necesitan atención". */
const LIVE_STATUSES: readonly Status[] = ['open', 'assigned', 'in_progress']
const ATTENTION_ROWS = 5
const AT_RISK_MS = 60 * 60_000
/** Escala de la barra de carga: capacidad + 20 % para que se vea el exceso. */
const LOAD_SCALE_FACTOR = 1.2

const CARD = 'rounded-2xl border border-line bg-surface'

function parseRange(value: string | null): Range {
  return RANGES.find((range) => range === value) ?? DEFAULT_RANGE
}

/** Número de semana ISO de una fecha (para las etiquetas "S46"). */
function isoWeek(value: string): number {
  const date = new Date(value)
  const day = (date.getUTCDay() + 6) % 7
  date.setUTCDate(date.getUTCDate() - day + 3)
  const firstThursday = new Date(Date.UTC(date.getUTCFullYear(), 0, 4))
  const week = 1 + Math.round(((date.getTime() - firstThursday.getTime()) / 86_400_000 - 3) / 7)
  return week
}

function greetingKey(hour: number): 'morning' | 'afternoon' | 'evening' {
  if (hour < 12) return 'morning'
  if (hour < 20) return 'afternoon'
  return 'evening'
}

type Tone = 'bad' | 'good' | 'neutral'
const CHIP_TONES: Record<Tone, string> = {
  bad: 'bg-prio-urgent-bg text-prio-urgent',
  good: 'bg-[#e0f4ee] text-[#0b6553]',
  neutral: 'bg-prio-low-bg text-text-2',
}

function Chip({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${CHIP_TONES[tone]}`}>
      {children}
    </span>
  )
}

/** Mini gráfica decorativa (el dato real está en el texto de la tarjeta). */
function Sparkline({ values, color }: { values: number[]; color: string }) {
  const data = values.map((value, index) => ({ index, value }))
  return (
    <div aria-hidden="true" className="h-9 w-24 shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            fill={color}
            fillOpacity={0.12}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function KpiCard({
  title,
  chip,
  value,
  note,
  spark,
  dark = false,
}: {
  title: string
  chip?: React.ReactNode
  value: string
  note: React.ReactNode
  spark?: React.ReactNode
  dark?: boolean
}) {
  return (
    <div
      className={`flex flex-col gap-3 rounded-2xl p-5 ${
        dark ? 'bg-sidebar text-white' : 'border border-line bg-surface'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className={`text-sm font-medium ${dark ? 'text-[#c3c8d4]' : 'text-text-2'}`}>
          {title}
        </span>
        {chip}
      </div>
      <div className="flex items-end justify-between gap-3">
        <span className="font-display text-4xl leading-none font-bold tracking-tight">{value}</span>
        {spark}
      </div>
      <span className={`text-xs ${dark ? 'text-[#c3c8d4]' : 'text-text-3'}`}>{note}</span>
    </div>
  )
}

function lastTwoWithData(weekly: WeeklyResolution[]) {
  const withData = weekly.filter((week) => week.avg_hours !== null)
  return {
    current: withData.at(-1)?.avg_hours ?? null,
    previous: withData.at(-2)?.avg_hours ?? null,
  }
}

function Kpis({ data, range }: { data: MetricsSummary; range: Range }) {
  const { t } = useTranslation()
  const f = useFormatters()
  const hours = (value: number) =>
    t('dashboard.hours', { value: f.number(value, { maximumFractionDigits: 1 }) })

  const openDelta = data.open.count - data.open.week_ago
  const { current, previous } = lastTwoWithData(data.resolution.weekly)
  const target = data.resolution.target_hours
  const timeDelta = current !== null && previous !== null ? current - previous : null
  const resolvedChange =
    data.resolved.previous > 0
      ? (data.resolved.count - data.resolved.previous) / data.resolved.previous
      : null
  const oldest = data.unassigned.oldest_created_at

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(14rem,1fr))] gap-4">
      <KpiCard
        title={t('dashboard.kpi.open')}
        chip={
          <Chip tone={openDelta > 0 ? 'bad' : openDelta < 0 ? 'good' : 'neutral'}>
            {openDelta > 0 ? '+' : ''}
            {f.number(openDelta)}
          </Chip>
        }
        value={f.number(data.open.count)}
        note={t('dashboard.kpi.openNote', { count: data.open.week_ago })}
        spark={<Sparkline values={data.series.open.map((point) => point.count)} color={ACCENT} />}
      />
      <KpiCard
        title={t('dashboard.kpi.unassigned')}
        chip={
          data.unassigned.urgent > 0 ? (
            <Chip tone="bad">{t('dashboard.kpi.urgent', { count: data.unassigned.urgent })}</Chip>
          ) : undefined
        }
        value={f.number(data.unassigned.count)}
        note={
          oldest
            ? t('dashboard.kpi.oldest', {
                time: f.duration(
                  new Date(data.generated_at).getTime() - new Date(oldest).getTime(),
                ),
              })
            : t('dashboard.kpi.noneWaiting')
        }
      />
      <KpiCard
        title={t('dashboard.kpi.resolution')}
        chip={
          timeDelta !== null ? (
            <Chip tone={timeDelta > 0 ? 'bad' : timeDelta < 0 ? 'good' : 'neutral'}>
              {timeDelta > 0 ? '+' : ''}
              {t('dashboard.hours', { value: f.number(timeDelta, { maximumFractionDigits: 1 }) })}
            </Chip>
          ) : undefined
        }
        value={current !== null ? hours(current) : '–'}
        note={
          current === null
            ? t('dashboard.kpi.noData')
            : t(current <= target ? 'dashboard.kpi.targetMet' : 'dashboard.kpi.targetMissed', {
                target: hours(target),
              })
        }
        spark={
          <Sparkline
            values={data.resolution.weekly.map((week) => week.avg_hours ?? 0)}
            color={ACCENT}
          />
        }
      />
      <KpiCard
        dark
        title={t('dashboard.kpi.resolved', { period: t(`dashboard.range.${range}Short`) })}
        chip={
          resolvedChange !== null ? (
            <span className="rounded-full bg-sidebar-active px-2 py-0.5 text-xs font-semibold text-[#8fe3cf]">
              {resolvedChange > 0 ? '+' : ''}
              {f.number(resolvedChange, { style: 'percent', maximumFractionDigits: 0 })}
            </span>
          ) : undefined
        }
        value={f.number(data.resolved.count)}
        note={t('dashboard.kpi.sla', { breached: data.sla.breached, atRisk: data.sla.at_risk })}
        spark={
          <Sparkline
            values={data.series.resolved.map((point) => point.count)}
            color={SPARK_ON_DARK}
          />
        }
      />
    </div>
  )
}

function SectionTitle({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="font-display text-lg font-semibold">
      {children}
    </h2>
  )
}

function PrioritySection({ data }: { data: MetricsSummary }) {
  const { t } = useTranslation()
  const f = useFormatters()
  const total = PRIORITIES.reduce((sum, priority) => sum + data.by_priority[priority], 0)
  const label = t('dashboard.priority.summary', {
    total,
    detail: PRIORITIES.map((p) => `${data.by_priority[p]} ${t(`tickets.priority.${p}`)}`).join(
      ', ',
    ),
  })
  return (
    <section aria-labelledby="h-prio" className={`${CARD} flex h-full flex-col gap-5 p-6`}>
      <div className="flex items-center justify-between">
        <SectionTitle id="h-prio">{t('dashboard.priority.title')}</SectionTitle>
        <Link to="/tickets" className="text-[0.8125rem] font-semibold text-accent-text">
          {t('dashboard.viewAll')}
        </Link>
      </div>
      <div
        role="img"
        aria-label={label}
        className="flex h-3.5 gap-0.75 overflow-hidden rounded-full bg-line"
      >
        {PRIORITIES.map((priority) => (
          <div
            key={priority}
            className={PRIORITY_COLORS[priority]}
            style={{ width: `${total ? (data.by_priority[priority] / total) * 100 : 0}%` }}
          />
        ))}
      </div>
      <ul className="flex flex-col">
        {PRIORITIES.map((priority) => (
          <li
            key={priority}
            className="flex items-center gap-3 border-b border-bg py-2.5 text-sm last:border-0"
          >
            <span
              aria-hidden="true"
              className={`size-2.5 rounded-[3px] ${PRIORITY_COLORS[priority]}`}
            />
            <span className="flex-1">{t(`tickets.priority.${priority}`)}</span>
            <span
              className={`text-xs ${priority === 'urgent' ? 'font-semibold text-prio-urgent' : 'text-text-3'}`}
            >
              {t('dashboard.priority.sla', { hours: SLA_HOURS[priority] })}
            </span>
            <span className="w-8 text-right font-display text-lg font-bold">
              {f.number(data.by_priority[priority])}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function ResolutionChart({ data }: { data: MetricsSummary }) {
  const { t } = useTranslation()
  const f = useFormatters()
  const target = data.resolution.target_hours
  const points = data.resolution.weekly.map((week) => ({
    label: `S${isoWeek(week.week_start)}`,
    hours: week.avg_hours,
    resolved: week.resolved,
  }))
  const known = points.filter((point) => point.hours !== null)
  const max = Math.max(target, ...known.map((point) => point.hours ?? 0))
  const top = Math.max(16, Math.ceil(max / 4) * 4)
  const summary = known.length
    ? t('dashboard.resolution.summary', {
        first: f.number(known.at(0)?.hours ?? 0, { maximumFractionDigits: 1 }),
        last: f.number(known.at(-1)?.hours ?? 0, { maximumFractionDigits: 1 }),
        target,
      })
    : t('dashboard.kpi.noData')

  return (
    <section aria-labelledby="h-tmr" className={`${CARD} flex h-full min-w-0 flex-col gap-4 p-6`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <SectionTitle id="h-tmr">{t('dashboard.resolution.title')}</SectionTitle>
          <span className="text-[0.8125rem] text-text-3">{t('dashboard.resolution.subtitle')}</span>
        </div>
        <div className="flex gap-4 text-xs text-text-2">
          <span className="flex items-center gap-1.5">
            <span aria-hidden="true" className="h-0.75 w-3.5 rounded-sm bg-accent" />
            {t('dashboard.resolution.real')}
          </span>
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="w-3.5 border-t-2 border-dashed border-st-resolved"
            />
            {t('dashboard.resolution.target', { hours: target })}
          </span>
        </div>
      </div>
      <div role="img" aria-label={summary} className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid stroke={GRID_COLOR} vertical={false} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: '#5b6477' }}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[0, top]}
              tickCount={5}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: '#5b6477' }}
              tickFormatter={(value: number) => t('dashboard.hours', { value })}
            />
            <ReferenceLine y={target} stroke={TARGET_COLOR} strokeDasharray="6 6" strokeWidth={2} />
            <Tooltip
              formatter={(value) => [
                typeof value === 'number'
                  ? t('dashboard.hours', { value: f.number(value, { maximumFractionDigits: 1 }) })
                  : '–',
                t('dashboard.resolution.real'),
              ]}
            />
            <Line
              type="monotone"
              dataKey="hours"
              stroke={ACCENT}
              strokeWidth={2.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

function AgentLoad({ agents, failed }: { agents: Agent[] | undefined; failed: boolean }) {
  const { t } = useTranslation()
  const f = useFormatters()
  return (
    <section aria-labelledby="h-carga" className={`${CARD} flex h-full min-w-0 flex-col gap-4 p-6`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle id="h-carga">{t('dashboard.agents.title')}</SectionTitle>
        <div className="flex gap-4 text-xs text-text-2">
          <span className="flex items-center gap-1.5">
            <span aria-hidden="true" className="size-2.5 rounded-[3px] bg-st-assigned" />
            {t('tickets.status.assigned')}
          </span>
          <span className="flex items-center gap-1.5">
            <span aria-hidden="true" className="size-2.5 rounded-[3px] bg-st-in-progress" />
            {t('tickets.status.in_progress')}
          </span>
          <span className="flex items-center gap-1.5">
            <span aria-hidden="true" className="h-3 border-l-2 border-dashed border-text" />
            {t('dashboard.agents.capacity')}
          </span>
        </div>
      </div>
      {failed ? (
        <p role="alert" className="py-6 text-center text-sm text-text-3">
          {t('dashboard.error')}
        </p>
      ) : !agents ? (
        <Skeleton className="h-40" />
      ) : agents.length === 0 ? (
        <p className="py-6 text-center text-sm text-text-3">{t('dashboard.agents.empty')}</p>
      ) : (
        agents.map((agent) => {
          const total = agent.assigned + agent.in_progress
          const scale = agent.capacity * LOAD_SCALE_FACTOR
          const over = total > agent.capacity
          return (
            <div key={agent.id} className="flex items-center gap-3.5">
              <UserAvatar user={agent} className="size-8.5 text-xs" />
              <div className="flex w-36 flex-none flex-col gap-0.5">
                <span className="truncate text-sm font-semibold">{displayName(agent)}</span>
                <span className="truncate text-xs text-text-3">{agent.team}</span>
              </div>
              <div
                role="img"
                aria-label={t('dashboard.agents.load', {
                  assigned: agent.assigned,
                  inProgress: agent.in_progress,
                  capacity: agent.capacity,
                })}
                className="relative h-3 min-w-20 flex-1 rounded-md bg-prio-low-bg"
              >
                <div
                  className="flex h-3 overflow-hidden rounded-md"
                  style={{ width: `${Math.min(total / scale, 1) * 100}%` }}
                >
                  <div
                    className="bg-st-assigned"
                    style={{ width: `${total ? (agent.assigned / total) * 100 : 0}%` }}
                  />
                  <div
                    className="bg-st-in-progress"
                    style={{ width: `${total ? (agent.in_progress / total) * 100 : 0}%` }}
                  />
                </div>
                <div
                  aria-hidden="true"
                  className="absolute -top-1 h-5.5 border-l-2 border-dashed border-text"
                  style={{ left: `${(agent.capacity / scale) * 100}%` }}
                />
              </div>
              <span
                className={`w-10 text-right font-display text-lg font-bold ${over ? 'text-prio-urgent' : ''}`}
              >
                {f.number(total)}
              </span>
            </div>
          )
        })
      )}
    </section>
  )
}

function Lifecycle({ data, range }: { data: MetricsSummary; range: Range }) {
  const { t } = useTranslation()
  const f = useFormatters()
  const { rejected } = data
  return (
    <section
      aria-labelledby="h-flujo"
      className="flex h-full min-w-0 flex-col gap-4 rounded-2xl bg-sidebar p-6 text-white"
    >
      <div className="flex flex-col gap-1">
        <h2 id="h-flujo" className="font-display text-lg font-semibold">
          {t('dashboard.lifecycle.title')}
        </h2>
        <span className="text-[0.8125rem] text-[#a9b0bf]">{t('dashboard.lifecycle.subtitle')}</span>
      </div>
      <ol className="flex flex-col">
        {STATUSES.map((status, index) => (
          <li key={status} className="flex flex-col">
            {index > 0 && (
              <span aria-hidden="true" className="ml-4.5 h-2.5 border-l-2 border-[#3a4155]" />
            )}
            <span className="flex items-center gap-3 rounded-xl bg-sidebar-2 px-3.5 py-3">
              <span
                aria-hidden="true"
                className={`size-2.5 rounded-full ${STATUS_DOT_CLASSES[status]}`}
              />
              <span className="flex-1 text-sm font-medium">{t(`tickets.status.${status}`)}</span>
              <span className="font-display text-xl font-bold">
                {f.number(data.by_status[status])}
              </span>
            </span>
          </li>
        ))}
      </ol>
      <p className="rounded-xl border border-dashed border-[#3a4155] px-3.5 py-3 text-[0.8125rem] leading-normal text-[#c3c8d4]">
        {rejected.count === 0
          ? t('dashboard.lifecycle.noRejected', { period: t(`dashboard.range.${range}Long`) })
          : t('dashboard.lifecycle.rejected', {
              count: rejected.count,
              period: t(`dashboard.range.${range}Long`),
            })}
        {rejected.latest && (
          <>
            {' '}
            {t('dashboard.lifecycle.latest')}{' '}
            <span className="font-mono text-white">
              {t(`tickets.status.${rejected.latest.from}`)} →{' '}
              {t(`tickets.status.${rejected.latest.to}`)}
            </span>
            .
          </>
        )}
      </p>
    </section>
  )
}

function Skeleton({ className }: { className: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-2xl bg-line ${className}`} />
}

function Attention() {
  const { t } = useTranslation()
  const f = useFormatters()
  const queries = useQueries({
    queries: LIVE_STATUSES.map((status) => ({
      queryKey: ['tickets', 'attention', status],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        fetchTickets({ status, ordering: 'sla_due_at', pageSize: ATTENTION_ROWS }, signal),
    })),
  })
  const now = Math.max(0, ...queries.map((query) => query.dataUpdatedAt))
  const loading = queries.some((query) => query.isPending)
  const failed = queries.some((query) => query.isError)
  const rows: TicketListItem[] = queries
    .flatMap((query) => query.data?.results ?? [])
    .sort((a, b) => new Date(a.sla_due_at).getTime() - new Date(b.sla_due_at).getTime())
    .slice(0, ATTENTION_ROWS)

  return (
    <section aria-labelledby="h-atencion" className={`${CARD} flex flex-col`}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-5">
        <div className="flex items-center gap-2.5">
          <SectionTitle id="h-atencion">{t('dashboard.attention.title')}</SectionTitle>
          <Chip tone="bad">{t('dashboard.attention.badge')}</Chip>
        </div>
        <Link to="/tickets" className="text-[0.8125rem] font-semibold text-accent-text">
          {t('dashboard.attention.openList')}
        </Link>
      </div>
      {failed && !rows.length ? (
        <p role="alert" className="px-6 pb-8 text-center text-sm text-text-3">
          {t('dashboard.error')}
        </p>
      ) : loading ? (
        <Skeleton className="mx-6 mb-6 h-40" />
      ) : rows.length === 0 ? (
        <p className="px-6 pb-8 text-center text-sm text-text-3">
          {t('dashboard.attention.empty')}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-205 border-collapse text-sm">
            <thead>
              <tr className="bg-[#f8f9fb] text-left text-xs font-semibold tracking-wide text-text-3 uppercase">
                <th scope="col" className="px-6 py-3">
                  {t('tickets.columns.ticket')}
                </th>
                <th scope="col" className="px-3 py-3">
                  {t('tickets.columns.priority')}
                </th>
                <th scope="col" className="px-3 py-3">
                  {t('tickets.columns.status')}
                </th>
                <th scope="col" className="px-3 py-3">
                  {t('tickets.columns.agent')}
                </th>
                <th scope="col" className="px-6 py-3 text-right">
                  SLA
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((ticket) => {
                const remaining = new Date(ticket.sla_due_at).getTime() - now
                const late = remaining < AT_RISK_MS
                return (
                  <tr key={ticket.code} className="border-t border-bg">
                    <td className="px-6 py-3.5">
                      <Link to={`/tickets/${ticket.code}`} className="flex flex-col gap-0.5">
                        <span className="font-mono text-xs text-text-3">{ticket.code}</span>
                        <span className="font-semibold">{ticket.subject}</span>
                      </Link>
                    </td>
                    <td className="px-3 py-3.5">
                      <PriorityBadge priority={ticket.priority} />
                    </td>
                    <td className="px-3 py-3.5">
                      <span className="inline-flex items-center gap-2 font-medium">
                        <span
                          aria-hidden="true"
                          className={`size-2 rounded-full ${STATUS_DOT_CLASSES[ticket.status]}`}
                        />
                        {t(`tickets.status.${ticket.status}`)}
                      </span>
                    </td>
                    <td className="px-3 py-3.5 text-text-2">
                      {ticket.assignee ? displayName(ticket.assignee) : t('tickets.unassigned')}
                    </td>
                    <td
                      className={`px-6 py-3.5 text-right font-mono text-xs font-medium ${late ? 'text-prio-urgent' : 'text-text-2'}`}
                    >
                      {remaining < 0
                        ? t('dashboard.attention.overdue', { time: f.duration(-remaining) })
                        : t('dashboard.attention.remaining', { time: f.duration(remaining) })}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export function Dashboard() {
  const { t } = useTranslation()
  const f = useFormatters()
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const range = parseRange(params.get('range'))

  const metrics = useQuery({
    queryKey: ['metrics', range],
    queryFn: ({ signal }) => fetchMetrics(range, signal),
  })
  const agents = useQuery({ queryKey: ['agents'], queryFn: ({ signal }) => fetchAgents(signal) })

  const now = new Date()
  const name = user?.first_name || user?.username || ''

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-sm text-text-3 first-letter:uppercase">
            {f.date(now, { weekday: 'long', day: 'numeric', month: 'long' })}
          </span>
          <h1 className="font-display text-3xl font-bold tracking-tight">
            {t(`dashboard.greeting.${greetingKey(now.getHours())}`, { name })}
          </h1>
        </div>
        <div
          role="group"
          aria-label={t('dashboard.range.label')}
          className="flex gap-0.5 rounded-xl border border-line bg-surface p-1 text-[0.8125rem] font-semibold"
        >
          {RANGES.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={option === range}
              onClick={() =>
                setParams(
                  (previous) => {
                    const next = new URLSearchParams(previous)
                    if (option === DEFAULT_RANGE) next.delete('range')
                    else next.set('range', option)
                    return next
                  },
                  { replace: true },
                )
              }
              className={`min-h-9 rounded-lg px-3.5 ${
                option === range ? 'bg-sidebar text-white' : 'text-text-2 hover:bg-bg'
              }`}
            >
              {t(`dashboard.range.${option}`)}
            </button>
          ))}
        </div>
      </div>

      {metrics.isError ? (
        <div role="alert" className="flex flex-col items-center gap-3 py-14 text-center">
          <p className="text-sm text-text-2">{t('dashboard.error')}</p>
          <button
            type="button"
            onClick={() => void metrics.refetch()}
            className="min-h-10 rounded-md border border-line bg-surface px-4 text-sm font-semibold hover:bg-bg"
          >
            {t('tickets.retry')}
          </button>
        </div>
      ) : !metrics.data ? (
        <div aria-busy="true" aria-label={t('dashboard.loading')} className="flex flex-col gap-4">
          <div className="grid grid-cols-[repeat(auto-fit,minmax(14rem,1fr))] gap-4">
            {[0, 1, 2, 3].map((key) => (
              <Skeleton key={key} className="h-36" />
            ))}
          </div>
          <Skeleton className="h-72" />
        </div>
      ) : (
        <>
          <Kpis data={metrics.data} range={range} />
          <div className="flex flex-wrap gap-4">
            <div className="min-w-0 flex-[1_1_21rem]">
              <PrioritySection data={metrics.data} />
            </div>
            <div className="min-w-0 flex-[2_1_32rem]">
              <ResolutionChart data={metrics.data} />
            </div>
          </div>
          <div className="flex flex-wrap gap-4">
            <div className="min-w-0 flex-[3_1_32rem]">
              <AgentLoad agents={agents.data} failed={agents.isError} />
            </div>
            <div className="min-w-0 flex-[2_1_21rem]">
              <Lifecycle data={metrics.data} range={range} />
            </div>
          </div>
          <Attention />
        </>
      )}
    </section>
  )
}
