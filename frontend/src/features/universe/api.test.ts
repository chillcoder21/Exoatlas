import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadUniverseData } from './api'
import {
  createUniverseApiPayload,
  createUniverseTestPlanets,
  jsonResponse,
  universeFixtureFetch,
} from './universeTestFixtures'

afterEach(() => vi.unstubAllGlobals())

describe('loadUniverseData', () => {
  it('loads every page in source order and rejects no valid records as duplicates', async () => {
    const fixturePlanets = createUniverseTestPlanets(205)
    const fetchMock = vi.fn(universeFixtureFetch(fixturePlanets))
    vi.stubGlobal('fetch', fetchMock)

    const result = await loadUniverseData()

    expect(result.planets).toHaveLength(205)
    expect(result.planets.map((planet) => planet.pl_name)).toEqual(
      fixturePlanets.map((planet) => planet.pl_name),
    )
    expect(new Set(result.planets.map((planet) => planet.pl_name)).size).toBe(205)
    expect(fetchMock.mock.calls.filter(([input]) => String(input).startsWith('/api/planets'))).toHaveLength(3)
    expect(result.overview.total_confirmed_planets).toBe(205)
    expect(result.overview.with_primary_cluster_assignment).toBe(204)
  })

  it('rejects a duplicate planet identifier across pages', async () => {
    const fixturePlanets = createUniverseTestPlanets(101)
    const fetchFixture = universeFixtureFetch(fixturePlanets)
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/planets' && url.searchParams.get('page') === '2') {
        const payload = createUniverseApiPayload(url.pathname, fixturePlanets, url.search)
        payload.records = [fixturePlanets[0]]
        return jsonResponse(payload)
      }
      return fetchFixture(input)
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(loadUniverseData()).rejects.toThrow(/Duplicate planet identifier/)
  })

  it('rejects a partial page instead of silently displaying incomplete data', async () => {
    const fixturePlanets = createUniverseTestPlanets(101)
    const fetchFixture = universeFixtureFetch(fixturePlanets)
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/planets' && url.searchParams.get('page') === '2') {
        return jsonResponse({
          pagination: { page: 2, page_size: 100, total_records: 101, total_pages: 2 },
          records: [],
        })
      }
      return fetchFixture(input)
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(loadUniverseData()).rejects.toThrow(/incomplete page 2/)
  })

  it('surfaces an API error response to the page', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ error: { message: 'API unavailable' } }, 503)),
    )

    await expect(loadUniverseData()).rejects.toThrow(/API unavailable/)
  })
})
