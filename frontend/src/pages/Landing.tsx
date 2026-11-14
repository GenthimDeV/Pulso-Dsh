import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { WakingBanner } from '../components/WakingBanner'
import { LANGUAGES, setLanguage, type Language } from '../i18n'

const PORTFOLIO_URL = 'https://gdv-portfolio.pages.dev'
const GITHUB_URL = 'https://github.com/GenthimDeV'
const FEATURES = ['dashboard', 'lifecycle', 'sla', 'conversation'] as const

const enterClass =
  'rounded-md bg-accent-text px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-text/90'

/** Página pública de `/` para visitantes sin sesión. */
export function Landing() {
  const { t, i18n } = useTranslation()
  return (
    <div className="flex min-h-screen flex-col">
      <WakingBanner />
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
          <span className="font-display text-xl font-bold">{t('app.name')}</span>
          <div className="flex items-center gap-3">
            <label htmlFor="landing-lang" className="sr-only">
              {t('header.language')}
            </label>
            <select
              id="landing-lang"
              value={i18n.language}
              onChange={(e) => setLanguage(e.target.value as Language)}
              className="rounded-md border border-line bg-surface px-2 py-1 text-sm"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {lang.toUpperCase()}
                </option>
              ))}
            </select>
            <Link to="/login" className={enterClass}>
              {t('landing.enter')}
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-5xl px-4 py-12 md:py-20">
          <h1 className="max-w-2xl font-display text-3xl font-bold md:text-5xl">
            {t('landing.title')}
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-text-2">{t('landing.lead')}</p>
          <div className="mt-6">
            <Link to="/login" className={`${enterClass} inline-block px-6 py-3 text-base`}>
              {t('landing.enter')}
            </Link>
          </div>
          <p
            role="note"
            className="mt-8 max-w-2xl rounded-md bg-prio-high-bg px-4 py-3 text-sm text-prio-high"
          >
            <strong className="font-semibold">{t('landing.demoTitle')}</strong>{' '}
            {t('landing.demoBody')}
          </p>
        </section>

        <section aria-labelledby="landing-features" className="border-t border-line bg-surface">
          <div className="mx-auto max-w-5xl px-4 py-10">
            <h2 id="landing-features" className="font-display text-2xl font-bold">
              {t('landing.featuresTitle')}
            </h2>
            <ul className="mt-6 grid gap-4 sm:grid-cols-2">
              {FEATURES.map((key) => (
                <li key={key} className="rounded-lg border border-line bg-bg p-4">
                  <h3 className="font-semibold">{t(`landing.features.${key}.title`)}</h3>
                  <p className="mt-1 text-sm text-text-2">{t(`landing.features.${key}.body`)}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-4 text-sm text-text-3">
          <p>{t('landing.footer')}</p>
          <nav aria-label={t('landing.links')} className="flex gap-4">
            <a
              href={PORTFOLIO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-text underline"
            >
              {t('landing.portfolio')}
            </a>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-text underline"
            >
              GitHub
            </a>
          </nav>
        </div>
      </footer>
    </div>
  )
}
