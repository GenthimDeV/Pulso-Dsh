import { useTranslation } from 'react-i18next'
import type { Priority, Status, UserRef } from '../api/tickets'

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

const AVATAR_CLASSES = [
  'bg-[#9ec5ff]',
  'bg-[#f2c66d]',
  'bg-[#8fe3cf]',
  'bg-[#c7b6ff]',
  'bg-[#ffb59a]',
] as const

export function initials(user: UserRef): string {
  const first = user.first_name.charAt(0)
  const last = user.last_name.charAt(0)
  return (first + last || user.username.slice(0, 2)).toUpperCase()
}

/** Círculo con las iniciales; el color sale del id para que sea estable. `className` fija el tamaño. */
export function UserAvatar({ user, className }: { user: UserRef; className: string }) {
  return (
    <span
      aria-hidden="true"
      className={`grid shrink-0 place-items-center rounded-full font-bold text-text ${className} ${
        AVATAR_CLASSES[user.id % AVATAR_CLASSES.length]
      }`}
    >
      {initials(user)}
    </span>
  )
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
