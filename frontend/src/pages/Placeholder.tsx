import { useTranslation } from 'react-i18next'

/** Pantalla marcador: la real llega en su tarea (4.2–4.6). */
export function Placeholder({ title }: { title: string }) {
  const { t } = useTranslation()
  return (
    <section>
      <h1 className="font-display text-2xl font-semibold">{title}</h1>
      <p className="mt-2 text-text-3">{t('pages.comingSoon')}</p>
    </section>
  )
}
