import { QueryClient } from '@tanstack/react-query'
import { isWakingError } from './errors'

const MAX_WAKING_RETRIES = 8

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Arranque en frío (red / 502-504): reintenta con espera creciente (≈ 1 min en total).
      // Cualquier otro error (400, 401, 403, 404, 409…) es una respuesta real: no se reintenta.
      retry: (failureCount, error) => isWakingError(error) && failureCount < MAX_WAKING_RETRIES,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})
