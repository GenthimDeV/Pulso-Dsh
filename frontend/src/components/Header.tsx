import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { LANGUAGES, setLanguage, type Language } from '../i18n'

/** Cabecera: búsqueda, idioma, notificaciones (decorativas en el demo) y "Nuevo ticket". */
export function Header() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  function onSearch(event: FormEvent) {
    event.preventDefault()
    const search = query.trim()
    void navigate(search ? `/tickets?search=${encodeURIComponent(search)}` : '/tickets')
  }

  return (
    <header className="flex flex-wrap items-center gap-3 border-b border-line bg-surface px-4 py-3">
      <form role="search" onSubmit={onSearch} className="min-w-0 flex-1 basis-56">
        <label htmlFor="header-search" className="sr-only">
          {t('header.searchLabel')}
        </label>
        <input
          id="header-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('header.searchPlaceholder')}
          className="w-full rounded-md border border-line bg-bg px-3 py-2 text-sm placeholder:text-text-3"
        />
      </form>

      <label htmlFor="header-lang" className="sr-only">
        {t('header.language')}
      </label>
      <select
        id="header-lang"
        value={i18n.language}
        onChange={(e) => setLanguage(e.target.value as Language)}
        className="rounded-md border border-line bg-surface px-2 py-2 text-sm"
      >
        {LANGUAGES.map((lang) => (
          <option key={lang} value={lang}>
            {lang.toUpperCase()}
          </option>
        ))}
      </select>

      <button
        type="button"
        aria-label={t('header.notifications')}
        className="rounded-md border border-line p-2 text-text-2 hover:bg-bg"
      >
        <svg
          viewBox="0 0 24 24"
          className="size-5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" />
        </svg>
      </button>

      <Link
        to="/tickets/nuevo"
        className="rounded-md bg-accent-text px-3 py-2 text-sm font-semibold text-white hover:bg-accent-text/90"
      >
        {t('header.newTicket')}
      </Link>
    </header>
  )
}
