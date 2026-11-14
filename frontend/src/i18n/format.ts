import { useTranslation } from 'react-i18next'

const MINUTE_MS = 60_000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

// Fechas y números con Intl según el idioma activo (brief §8).
export function useFormatters() {
  const { t, i18n } = useTranslation()
  const locale = i18n.language
  const toDate = (value: string | Date) => (typeof value === 'string' ? new Date(value) : value)
  return {
    number: (value: number, options?: Intl.NumberFormatOptions) =>
      new Intl.NumberFormat(locale, options).format(value),
    date: (value: string | Date, options?: Intl.DateTimeFormatOptions) =>
      new Intl.DateTimeFormat(
        locale,
        options ?? { dateStyle: 'medium', timeStyle: 'short' },
      ).format(toDate(value)),
    /** "hace 5 min", "ayer"…: la unidad más grande que quepa. */
    relative: (value: string | Date) => {
      const diff = toDate(value).getTime() - Date.now()
      const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
      const abs = Math.abs(diff)
      if (abs < MINUTE_MS) return rtf.format(0, 'second')
      if (abs < HOUR_MS) return rtf.format(Math.round(diff / MINUTE_MS), 'minute')
      if (abs < DAY_MS) return rtf.format(Math.round(diff / HOUR_MS), 'hour')
      return rtf.format(Math.round(diff / DAY_MS), 'day')
    },
    /** Duración corta: "12 min", "3 h 20 min", "2 d". */
    duration: (ms: number) => {
      const minutes = Math.floor(Math.max(ms, 0) / MINUTE_MS)
      if (minutes < 1) return t('duration.lessThanMinute')
      if (minutes < 60) return t('duration.minutes', { count: minutes })
      const hours = Math.floor(minutes / 60)
      if (hours < 24) {
        const rest = minutes % 60
        const base = t('duration.hours', { count: hours })
        return rest ? `${base} ${t('duration.minutes', { count: rest })}` : base
      }
      return t('duration.days', { count: Math.floor(hours / 24) })
    },
  }
}
