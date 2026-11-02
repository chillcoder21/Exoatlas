import type {
  ClusterProfile,
  PlanetRecord,
  UniverseData,
  UniverseOverview,
} from './types'

const PAGE_SIZE = 100
const PAGE_CONCURRENCY = 8

type PlanetPage = {
  pagination: {
    page: number
    page_size: number
    total_records: number
    total_pages: number
  }
  records: PlanetRecord[]
}

type OverviewResponse = {
  dataset: UniverseOverview
}

type ClustersResponse = {
  cohort_size: number
  clusters: ClusterProfile[]
}

async function readJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal, headers: { Accept: 'application/json' } })
  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    const message =
      typeof payload === 'object' && payload !== null && 'error' in payload
        ? String((payload as { error?: { message?: unknown } }).error?.message ?? response.statusText)
        : response.statusText
    throw new Error(`${url}: ${message || `HTTP ${response.status}`}`)
  }

  return payload as T
}

function validatePage(page: PlanetPage, expectedPage: number, expectedTotal?: number) {
  if (
    !page ||
    !page.pagination ||
    !Array.isArray(page.records) ||
    page.pagination.page !== expectedPage ||
    page.pagination.page_size !== PAGE_SIZE ||
    !Number.isInteger(page.pagination.total_records) ||
    !Number.isInteger(page.pagination.total_pages)
  ) {
    throw new Error(`The planets API returned an invalid response for page ${expectedPage}.`)
  }

  if (
    (expectedTotal !== undefined && page.pagination.total_records !== expectedTotal) ||
    page.pagination.total_pages !== Math.ceil(page.pagination.total_records / PAGE_SIZE)
  ) {
    throw new Error('The planets API returned inconsistent pagination totals.')
  }

  const expectedPageRecords = Math.max(
    0,
    Math.min(PAGE_SIZE, page.pagination.total_records - (expectedPage - 1) * PAGE_SIZE),
  )
  if (page.records.length !== expectedPageRecords) {
    throw new Error(`The planets API returned an incomplete page ${expectedPage}.`)
  }
}

function validatePlanet(record: PlanetRecord) {
  if (!record || typeof record.pl_name !== 'string' || !record.pl_name.trim()) {
    throw new Error('The planets API returned a record without a stable planet identifier.')
  }
  if (record.assignment_status !== 'assigned' && record.assignment_status !== 'unassigned') {
    throw new Error(`The assignment status for ${record.pl_name} is invalid.`)
  }
  if (
    (record.assignment_status === 'assigned' && !Number.isInteger(record.cluster_id)) ||
    (record.assignment_status === 'unassigned' && record.cluster_id !== null)
  ) {
    throw new Error(`The cluster assignment for ${record.pl_name} is inconsistent.`)
  }
}

async function getPage(page: number, signal?: AbortSignal, expectedTotal?: number) {
  const result = await readJson<PlanetPage>(
    `/api/planets?page=${page}&page_size=${PAGE_SIZE}`,
    signal,
  )
  validatePage(result, page, expectedTotal)
  result.records.forEach(validatePlanet)
  return result
}

export async function loadUniverseData(signal?: AbortSignal): Promise<UniverseData> {
  const [overviewResponse, clustersResponse, firstPage] = await Promise.all([
    readJson<OverviewResponse>('/api/overview', signal),
    readJson<ClustersResponse>('/api/clusters', signal),
    getPage(1, signal),
  ])

  const overview = overviewResponse.dataset
  const { pagination } = firstPage
  if (
    !overview ||
    overview.total_confirmed_planets !== pagination.total_records ||
    overview.number_of_clusters !== clustersResponse.clusters.length ||
    clustersResponse.cohort_size !== overview.with_primary_cluster_assignment ||
    overview.with_primary_cluster_assignment + overview.without_cluster_assignment !==
      overview.total_confirmed_planets
  ) {
    throw new Error('The overview, cluster profiles, and planet pages disagree about dataset totals.')
  }

  const pages: PlanetRecord[][] = [firstPage.records]
  const remainingPages = Array.from({ length: pagination.total_pages - 1 }, (_, index) => index + 2)
  for (let offset = 0; offset < remainingPages.length; offset += PAGE_CONCURRENCY) {
    const pageBatch = remainingPages.slice(offset, offset + PAGE_CONCURRENCY)
    const responses = await Promise.all(
      pageBatch.map((page) => getPage(page, signal, pagination.total_records)),
    )
    pages.push(...responses.map((response) => response.records))
  }

  const planets = pages.flat()
  if (planets.length !== overview.total_confirmed_planets) {
    throw new Error(`Loaded ${planets.length} planets; expected ${overview.total_confirmed_planets}.`)
  }

  const identifiers = new Set<string>()
  const assignmentCounts = new Map<number, number>()
  let unassignedCount = 0
  for (const planet of planets) {
    if (identifiers.has(planet.pl_name)) {
      throw new Error(`Duplicate planet identifier returned by the API: ${planet.pl_name}.`)
    }
    identifiers.add(planet.pl_name)
    if (planet.cluster_id === null) unassignedCount += 1
    else assignmentCounts.set(planet.cluster_id, (assignmentCounts.get(planet.cluster_id) ?? 0) + 1)
  }

  const profiles = new Map(clustersResponse.clusters.map((profile) => [profile.cluster_id, profile]))
  if (
    unassignedCount !== overview.without_cluster_assignment ||
    assignmentCounts.size !== clustersResponse.clusters.length ||
    clustersResponse.clusters.some(
      (profile) => assignmentCounts.get(profile.cluster_id) !== profile.planet_count,
    ) ||
    Array.from(assignmentCounts.keys()).some((clusterId) => !profiles.has(clusterId))
  ) {
    throw new Error('Loaded planet assignments do not match the published cluster profiles.')
  }

  return { planets, overview, clusters: clustersResponse.clusters }
}
