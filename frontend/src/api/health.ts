import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'

interface Health {
  status: string
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => apiFetch<Health>('/health/', { signal }),
    refetchInterval: 60_000,
  })
}
