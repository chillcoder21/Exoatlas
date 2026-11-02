import type {
  DiscoveryDistributions,
  DiscoveryFacilities,
  DiscoveryOverview,
  DiscoveryProperty,
  DiscoveryTimeline,
} from './types'

async function readJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal, headers: { Accept: 'application/json' } })
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const message =
      typeof payload === 'object' && payload !== null && 'error' in payload
        ? String((payload as { error?: { message?: unknown } }).error?.message ?? response.statusText)
        : response.statusText
    throw new Error(message || `The scientific data service returned ${response.status}.`)
  }
  return payload as T
}

function queryFor(property: DiscoveryProperty | null, methods: string[]) {
  const params = new URLSearchParams()
  if (property) params.set('property', property)
  methods.forEach((method) => params.append('method', method))
  return params.toString()
}

export function loadDiscoveryOverview(signal?: AbortSignal) {
  return readJson<DiscoveryOverview>('/api/discovery/overview', signal)
}

export function loadDiscoveryTimeline(methods: string[], signal?: AbortSignal) {
  const query = queryFor(null, methods)
  return readJson<DiscoveryTimeline>(`/api/discovery/timeline${query ? `?${query}` : ''}`, signal)
}

export function loadDiscoveryDistributions(
  property: DiscoveryProperty,
  methods: string[],
  signal?: AbortSignal,
) {
  return readJson<DiscoveryDistributions>(
    `/api/discovery/distributions?${queryFor(property, methods)}`,
    signal,
  )
}

export function loadDiscoveryFacilities(methods: string[], signal?: AbortSignal) {
  const query = queryFor(null, methods)
  return readJson<DiscoveryFacilities>(`/api/discovery/facilities${query ? `?${query}` : ''}`, signal)
}
