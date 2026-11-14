import { apiFetch } from './client'
import type { Priority, Status } from './tickets'

export const RANGES = ['today', '7d', '30d'] as const
export type Range = (typeof RANGES)[number]
export const DEFAULT_RANGE: Range = '7d'

export interface DailyPoint {
  date: string
  count: number
}

export interface WeeklyResolution {
  week_start: string
  avg_hours: number | null
  resolved: number
}

export interface MetricsSummary {
  range: Range
  generated_at: string
  open: { count: number; week_ago: number }
  unassigned: { count: number; urgent: number; oldest_created_at: string | null }
  by_priority: Record<Priority, number>
  by_status: Record<Status, number>
  resolved: { count: number; previous: number }
  sla: { breached: number; at_risk: number }
  resolution: { target_hours: number; weekly: WeeklyResolution[] }
  rejected: { count: number; latest: { from: Status; to: Status } | null }
  series: { open: DailyPoint[]; resolved: DailyPoint[] }
}

export function fetchMetrics(range: Range, signal?: AbortSignal): Promise<MetricsSummary> {
  return apiFetch<MetricsSummary>('/metrics/summary/', { signal, params: { range } })
}
