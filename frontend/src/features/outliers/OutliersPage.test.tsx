import { useEffect } from 'react'
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { OutliersPage } from './OutliersPage'
import type { OutlierDetail, OutlierObservation, OutlierOverview } from './types'

const planets: OutlierObservation[] = [
  {
    pl_name: 'Kepler-11 b', hostname: 'Kepler-11', assignment_status: 'assigned', cluster_id: 2,
    centroid_distance: 1.84, cluster_distance_percentile: 99.6, silhouette_score: -0.08,
    pl_rade: 1.8, pl_orbper: 10.3, pl_eqt: 900, pl_orbeccen: 0,
    pl_rade_relation: 'below_q1', pl_orbper_relation: 'within_q1_q3', pl_eqt_relation: 'above_q3', pl_orbeccen_relation: 'within_q1_q3',
  },
  {
    pl_name: 'Kepler-11 c', hostname: 'Kepler-11', assignment_status: 'assigned', cluster_id: 1,
    centroid_distance: 1.22, cluster_distance_percentile: 94.0, silhouette_score: 0.14,
    pl_rade: 2.9, pl_orbper: 13.0, pl_eqt: 700, pl_orbeccen: 0.02,
    pl_rade_relation: 'within_q1_q3', pl_orbper_relation: 'above_q3', pl_eqt_relation: 'within_q1_q3', pl_orbeccen_relation: 'above_q3',
  },
]

const featureRelations = {
  pl_rade: { below_q1: 1, within_q1_q3: 0, above_q3: 1 },
  pl_orbper: { below_q1: 1, within_q1_q3: 0, above_q3: 1 },
  pl_eqt: { below_q1: 1, within_q1_q3: 0, above_q3: 1 },
  pl_orbeccen: { below_q1: 1, within_q1_q3: 0, above_q3: 1 },
}

const overview: OutlierOverview = {
  summary: { catalogue_records: 3, assigned_records: 2, unassigned_records: 1, negative_silhouette_records: 1 },
  distributions: {
    centroid_distance_percentile: {
      minimum: 60, q1: 65, median: 77, q3: 88, maximum: 99.6,
      histogram: { '0-10': 0, '10-20': 0, '20-30': 0, '30-40': 0, '40-50': 0, '50-60': 0, '60-70': 1, '70-80': 0, '80-90': 0, '90-100': 1 },
    },
    silhouette: { minimum: -0.08, median: 0.03, maximum: 0.14, negative_count: 1, histogram: { '0 to 0.25': 2 } },
    feature_relations: featureRelations,
  },
  method: { model_fitting: false },
  limitations: ['A high distance does not prove an incorrect measurement.'],
  cluster_profiles: [
    { cluster_id: 1, planet_count: 1, physical_features: {} },
    { cluster_id: 2, planet_count: 1, physical_features: {} },
  ],
}

function detailFor(record: OutlierObservation): OutlierDetail {
  return {
    record,
    diagnostics_available: true,
    cluster_profile: overview.cluster_profiles.find((item) => item.cluster_id === record.cluster_id) ?? null,
    feature_comparisons: [
      { feature: 'pl_rade', label: 'Planetary radius', value: record.pl_rade, unit: 'Earth radii', relation: record.pl_rade_relation, iqr_from_median: -0.5, reference: { unit: 'Earth radii', median: 2.5, q1: 2, q3: 3, iqr: 1 } },
      { feature: 'pl_orbper', label: 'Orbital period', value: record.pl_orbper, unit: 'days', relation: record.pl_orbper_relation, iqr_from_median: 0.2, reference: { unit: 'days', median: 12, q1: 8, q3: 16, iqr: 8 } },
      { feature: 'pl_eqt', label: 'Equilibrium temperature', value: record.pl_eqt, unit: 'K', relation: record.pl_eqt_relation, iqr_from_median: 1.1, reference: { unit: 'K', median: 650, q1: 500, q3: 800, iqr: 300 } },
      { feature: 'pl_orbeccen', label: 'Orbital eccentricity', value: record.pl_orbeccen, unit: 'dimensionless', relation: record.pl_orbeccen_relation, iqr_from_median: null, reference: { unit: 'dimensionless', median: 0, q1: 0, q3: 0, iqr: 0 } },
    ],
    unavailable_reason: null,
  }
}

function LocationProbe() {
  const location = useLocation()
  useEffect(() => { window.history.replaceState({}, '', `${location.pathname}${location.search}`) }, [location])
  return <output data-testid="location">{location.pathname}{location.search}</output>
}

function jsonResponse(value: unknown, status = 200) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: async () => value } as Response)
}

function mockFetch() {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), window.location.origin)
    if (url.pathname === '/api/outliers/overview') return jsonResponse(overview)
    if (url.pathname === '/api/outliers/observations') {
      const cluster = url.searchParams.get('cluster_id')
      const term = url.searchParams.get('search')?.toLowerCase()
      const min = Number(url.searchParams.get('percentile_min') ?? 0)
      let records = planets.filter((item) => item.cluster_distance_percentile !== null && item.cluster_distance_percentile >= min)
      if (cluster) records = records.filter((item) => String(item.cluster_id) === cluster)
      if (term) records = records.filter((item) => `${item.pl_name} ${item.hostname}`.toLowerCase().includes(term))
      return jsonResponse({
        pagination: { page: Number(url.searchParams.get('page') ?? 1), page_size: 20, total_records: records.length, total_pages: records.length ? 1 : 0 },
        filters: {}, records, ranking_note: 'The selected percentile is a review range.',
      })
    }
    if (url.pathname.startsWith('/api/outliers/planets/')) {
      const name = decodeURIComponent(url.pathname.split('/').at(-1) ?? '')
      const record = planets.find((item) => item.pl_name === name)
      return record ? jsonResponse(detailFor(record)) : jsonResponse({ error: { message: 'Missing planet.' } }, 404)
    }
    return jsonResponse({ error: { message: 'Unexpected test request.' } }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPage(initialEntry = '/outliers') {
  return render(<MemoryRouter initialEntries={[initialEntry]}><LocationProbe /><OutliersPage /></MemoryRouter>)
}

describe('OutliersPage', () => {
  beforeEach(() => { mockFetch() })
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  it('renders the saved-results overview, D3 distribution, and selected planet details', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Three diagnostics, three questions.' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'The Outliers' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Kepler-11 b' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /histogram of within-cluster centroid-distance percentiles/i })).toBeInTheDocument()
    expect(await screen.findByText(/Euclidean · standardized feature space/)).toBeInTheDocument()
    expect(screen.getByText('Original measurements against cluster quartiles')).toBeInTheDocument()
    expect(screen.getByText('Negative saved silhouettes')).toBeInTheDocument()
  })

  it('filters by cluster and searches the planet or host-star names', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('heading', { name: 'Kepler-11 b' })
    const resultList = screen.getByRole('list', { name: 'Ranked outlier observations' })
    await user.selectOptions(screen.getAllByRole('combobox', { name: 'Filter by cluster' })[0], '1')
    await waitFor(() => expect(within(resultList).queryByText('Kepler-11 b')).not.toBeInTheDocument())
    expect(within(resultList).getByText('Kepler-11 c')).toBeInTheDocument()
    const search = screen.getByRole('searchbox', { name: 'Search planets or host stars' })
    await user.type(search, 'kepler-11')
    await waitFor(() => expect(within(resultList).getByText('Kepler-11 c')).toBeInTheDocument())
    expect(within(resultList).queryByText('Kepler-11 b')).not.toBeInTheDocument()
  })

  it('selects a planet, updates the URL, and links to its Explorer dossier', async () => {
    const user = userEvent.setup()
    renderPage()
    const observationButton = (await screen.findAllByRole('button', { name: /Kepler-11 c/ }))[0]
    await user.click(observationButton)
    expect(await screen.findByRole('heading', { name: 'Kepler-11 c' })).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/outliers?planet=Kepler-11+c')
    expect(screen.getByRole('link', { name: /open this planet in the explorer/i })).toHaveAttribute('href', '/explorer?planet=Kepler-11%20c')
  })

  it('compares two observations and keeps physical measurements readable', async () => {
    const user = userEvent.setup()
    renderPage()
    const resultList = await screen.findByRole('list', { name: 'Ranked outlier observations' })
    const rowB = within(resultList).getByText('Kepler-11 b').closest('li')!
    const rowC = within(resultList).getByText('Kepler-11 c').closest('li')!
    await user.click(within(rowB).getByRole('button', { name: 'Compare' }))
    await user.click(within(rowC).getByRole('button', { name: 'Compare' }))
    expect(await screen.findByRole('heading', { name: 'Compare selected observations.' })).toBeInTheDocument()
    const comparisonSection = screen.getByRole('region', { name: 'Compare selected observations.' })
    expect(within(comparisonSection).getByText('1.8')).toBeInTheDocument()
    expect(within(comparisonSection).getByText('2.9')).toBeInTheDocument()
    expect(within(comparisonSection).getAllByText('Earth radii').length).toBeGreaterThan(0)
  })

  it('exposes a keyboard-operable observation control', async () => {
    const user = userEvent.setup()
    renderPage()
    const observation = (await screen.findAllByRole('button', { name: /Kepler-11 c/ }))[0]
    observation.focus()
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('heading', { name: 'Kepler-11 c' })).toBeInTheDocument()
  })
})
