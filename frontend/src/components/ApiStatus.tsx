import { useTranslation } from 'react-i18next'
import { useHealth } from '../api/health'

/** Indicador del estado de la API en el pie del menú (texto + punto, nunca solo color). */
export function ApiStatus() {
  const { t } = useTranslation()
  const { isError, isSuccess } = useHealth()
  const state = isSuccess ? 'online' : isError ? 'offline' : 'checking'
  const dot = isSuccess ? 'bg-st-resolved' : isError ? 'bg-prio-urgent' : 'bg-chart-low'
  return (
    <p className="flex items-center gap-2 text-xs text-slate-300" aria-live="polite">
      <span className={`size-2 rounded-full ${dot}`} aria-hidden="true" />
      {t('server.api')}: {t(`server.${state}`)}
    </p>
  )
}
