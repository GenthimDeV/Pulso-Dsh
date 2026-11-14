import { useTranslation } from 'react-i18next'
import { useServerWaking } from '../api/serverState'

/** Aviso global de arranque en frío. Se muestra mientras el servidor no responde. */
export function WakingBanner() {
  const { t } = useTranslation()
  const waking = useServerWaking()
  if (!waking) return null
  return (
    <div role="status" className="border-b border-line bg-prio-high-bg px-4 py-2 text-sm">
      <p className="font-semibold text-prio-high">{t('server.waking')}</p>
      <p className="text-text-2">{t('server.wakingHint')}</p>
    </div>
  )
}
