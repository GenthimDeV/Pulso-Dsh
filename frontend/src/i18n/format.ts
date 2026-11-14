import { useTranslation } from 'react-i18next'

// Fechas y números con Intl según el idioma activo (brief §8).
export function useFormatters() {
  const { i18n } = useTranslation()
  const locale = i18n.language
  return {
    number: (value: number, options?: Intl.NumberFormatOptions) =>
      new Intl.NumberFormat(locale, options).format(value),
    date: (value: string | Date, options?: Intl.DateTimeFormatOptions) =>
      new Intl.DateTimeFormat(
        locale,
        options ?? { dateStyle: 'medium', timeStyle: 'short' },
      ).format(typeof value === 'string' ? new Date(value) : value),
  }
}
