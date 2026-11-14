import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ApiStatus } from './ApiStatus'

const ITEMS = [
  { to: '/', key: 'dashboard', end: true },
  { to: '/tickets', key: 'tickets', end: false },
  { to: '/asignados', key: 'assigned', end: false },
  { to: '/agentes', key: 'agents', end: false },
  { to: '/informes', key: 'reports', end: false },
] as const

/** Menú lateral oscuro; en móvil pasa arriba y sus enlaces hacen scroll horizontal. */
export function Sidebar() {
  const { t } = useTranslation()
  return (
    <aside className="flex shrink-0 flex-col gap-2 bg-sidebar p-3 text-slate-200 md:w-60 md:gap-6 md:p-4">
      <div className="flex items-center justify-between">
        <span className="font-display text-xl font-bold text-white">{t('app.name')}</span>
        <div className="md:hidden">
          <ApiStatus />
        </div>
      </div>
      <nav aria-label={t('nav.main')} className="-mx-1 overflow-x-auto px-1">
        <ul className="flex gap-1 md:flex-col">
          {ITEMS.map(({ to, key, end }) => (
            <li key={key}>
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  `block whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium hover:bg-sidebar-2 ${
                    isActive ? 'bg-sidebar-active text-white' : ''
                  }`
                }
              >
                {t(`nav.${key}`)}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="mt-auto hidden md:block">
        <ApiStatus />
      </div>
    </aside>
  )
}
