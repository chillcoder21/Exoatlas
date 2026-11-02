import type { ClusterProfile, PlanetRecord } from './types'

/** Test-only API fixtures. These identifiers and measurements are never used by the app. */
export function createUniverseTestPlanets(total: number): PlanetRecord[] {
  const assignedCount = Math.max(0, total - 1)
  return Array.from({ length: total }, (_, index): PlanetRecord => {
    const isUnassigned = index >= assignedCount
    const clusterId = isUnassigned ? null : index % 4
    return {
      pl_name: `Fixture Planet ${String(index + 1).padStart(3, '0')}`,
      hostname: `Fixture Star ${String(index + 1).padStart(3, '0')}`,
      pl_rade: index === 41 ? null : 0.5 + (index % 30) * 0.12,
      pl_orbper: index + 1,
      pl_eqt: index === 100 ? null : 240 + index * 3,
      pl_orbeccen: index === 0 ? 0 : (index % 10) / 20,
      cluster_id: clusterId,
      assignment_status: isUnassigned ? 'unassigned' : 'assigned',
      discoverymethod: index % 2 === 0 ? 'Transit' : 'Radial Velocity',
      disc_year: 2000 + (index % 25),
    }
  })
}

export function createUniverseTestProfiles(planets: PlanetRecord[]): ClusterProfile[] {
  return [0, 1, 2, 3].map((clusterId) => ({
    cluster_id: clusterId,
    planet_count: planets.filter((planet) => planet.cluster_id === clusterId).length,
  }))
}

export function createUniverseApiPayload(path: string, planets: PlanetRecord[], search = '') {
  const assignedCount = planets.filter((planet) => planet.cluster_id !== null).length
  const profiles = createUniverseTestProfiles(planets)
  if (path === '/api/overview') {
    return {
      dataset: {
        total_confirmed_planets: planets.length,
        with_primary_cluster_assignment: assignedCount,
        without_cluster_assignment: planets.length - assignedCount,
        number_of_clusters: profiles.length,
        version: 'PSCompPars-test-fixture',
      },
    }
  }
  if (path === '/api/clusters') {
    return { cohort_size: assignedCount, clusters: profiles }
  }
  if (path === '/api/planets') {
    const url = new URL(`http://localhost${path}${search}`)
    const page = Number(url.searchParams.get('page') ?? 1)
    const pageSize = Number(url.searchParams.get('page_size') ?? 50)
    const start = (page - 1) * pageSize
    return {
      pagination: {
        page,
        page_size: pageSize,
        total_records: planets.length,
        total_pages: Math.ceil(planets.length / pageSize),
      },
      records: planets.slice(start, start + pageSize),
    }
  }
  throw new Error(`Unexpected fixture API path: ${path}`)
}

export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Service Unavailable',
    json: async () => body,
  } as Response
}

export function universeFixtureFetch(planets: PlanetRecord[]) {
  return async (input: RequestInfo | URL): Promise<Response> => {
    const url = new URL(String(input), 'http://localhost')
    return jsonResponse(createUniverseApiPayload(url.pathname, planets, url.search))
  }
}
