import { useTranslation } from 'react-i18next'
import type { Priority, Status } from '../api/tickets'

// Clases completas (no construidas por interpolación) para que Tailwind las detecte.
const PRIORITY_CLASSES: Record<Priority, string> = {
  urgent: 'bg-prio-urgent-bg text-prio-urgent',
  high: 'bg-prio-high-bg text-prio-high',
  medium: 'bg-prio-medium-bg text-prio-medium',
  low: 'bg-prio-low-bg text-prio-low',
}

export const STATUS_DOT_CLASSES: Record<Status, string> = {
  open: 'bg-st-open',
  assigned: 'bg-st-assigned',
  in_progress: 'bg-st-in-progress',
  resolved: 'bg-st-resolved',
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  const { t } = useTranslation()
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${PRIORITY_CLASSES[priority]}`}
    >
      {t(`tickets.priority.${priority}`)}
    </span>
  )
}

export function StatusBadge({ status }: { status: Status }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex items-center gap-2 font-medium">
      <span aria-hidden="true" className={`size-2 rounded-full ${STATUS_DOT_CLASSES[status]}`} />
      {t(`tickets.status.${status}`)}
    </span>
  )
}
