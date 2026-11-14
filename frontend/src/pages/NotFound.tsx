import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

export function NotFound() {
  const { t } = useTranslation()
  return (
    <section>
      <h1 className="font-display text-2xl font-semibold">{t('pages.notFound')}</h1>
      <Link to="/" className="mt-2 inline-block text-accent-text underline">
        {t('pages.backHome')}
      </Link>
    </section>
  )
}
