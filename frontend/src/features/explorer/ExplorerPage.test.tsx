import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { ExplorerPage } from './ExplorerPage'
import type { DossierRecord, SimilarPlanet } from './types'

vi.mock('motion/react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('motion/react')>()
  return { ...actual, useReducedMotion: () => true }
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const assigned: DossierRecord = {
  pl_name: 'Fixture Planet A', hostname: 'Fixture Star A', pl_rade: 2, pl_orbper: 10,
  pl_eqt: 500, pl_orbeccen: 0, cluster_id: 1, assignment_status: 'assigned',
  discoverymethod: 'Transit', disc_year: 2020, pl_bmasse: null, pl_bmassprov: null,
  pl_orbsmax: 0.1, pl_orbincl: 89, disc_facility: 'Fixture Facility',
  st_spectype: 'G2 V', st_teff: 5700, st_rad: 1, st_mass: 1,
  sy_snum: 1, sy_pnum: 2, four_feature_eligibility_reason: null,
}

const neighborB: SimilarPlanet = { ...assigned, pl_name: 'Fixture Planet B', hostname: 'Fixture Star B', pl_rade: 3, cluster_id: 0, similarity_distance: 0.2 }
const neighborC: SimilarPlanet = { ...assigned, pl_name: 'Fixture Planet C', hostname: 'Fixture Star C', pl_orbper: 15, cluster_id: 2, similarity_distance: 0.4 }
const unassigned: DossierRecord = {
  ...assigned,
  pl_name: 'Fixture Incomplete',
  pl_rade: null,
  pl_orbper: null,
  pl_eqt: 400,
  pl_orbeccen: null,
  cluster_id: null,
  assignment_status: 'unassigned',
  four_feature_eligibility_reason: 'missing: pl_rade, pl_orbper, pl_orbeccen',
}

const clusters = [0, 1, 2, 3].map((cluster_id) => ({
  cluster_id,
  planet_count: 100 + cluster_id,
  physical_features: Object.fromEntries([
    ['pl_rade', { median: 2, q1: 1, q3: 3, iqr: 2, unit: 'Earth radii' }],
    ['pl_orbper', { median: 10, q1: 5, q3: 20, iqr: 15, unit: 'days' }],
    ['pl_eqt', { median: 500, q1: 300, q3: 700, iqr: 400, unit: 'K' }],
    ['pl_orbeccen', { median: 0.1, q1: 0, q3: 0.2, iqr: 0.2, unit: 'unitless' }],
  ]),
}))

function installApi(selected: DossierRecord = assigned, neighbors: SimilarPlanet[] = [neighborB, neighborC]) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    let payload: unknown
    if (url === '/api/clusters') payload = { clusters }
    else if (url.startsWith('/api/planets?search=')) payload = { records: [assigned, unassigned], pagination: { total_records: 2 } }
    else if (url.endsWith('/similar')) payload = {
      planet_id: selected.pl_name,
      eligibility: { eligible: selected.cluster_id !== null, message: 'Similarity status', detail: selected.cluster_id === null ? 'missing: pl_rade, pl_orbper, pl_orbeccen' : undefined },
      method: { name: 'Euclidean', features: ['log10(pl_rade)', 'log10(pl_orbper)', 'pl_eqt', 'pl_orbeccen'], scaling: 'Existing fitted scaler; not refit.', interpretation: 'Distance is not a probability.' },
      candidate_pool_size: selected.cluster_id === null ? 0 : 5272,
      neighbor_count: selected.cluster_id === null ? 0 : neighbors.length,
      neighbors: selected.cluster_id === null ? [] : neighbors,
    }
    else if (url.startsWith('/api/planets/')) payload = { record: selected }
    else payload = {}
    return new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }))
}

function renderExplorer(path = '/explorer') {
  return render(<MemoryRouter initialEntries={[path]}><ExplorerPage /></MemoryRouter>)
}

describe('The Explorer scientific dossier', () => {
  it('shows catalogue measurements, missing values, group quartiles and ranked neighbors', async () => {
    installApi()
    renderExplorer('/explorer?planet=Fixture%20Planet%20A')

    expect(await screen.findByRole('heading', { name: 'Fixture Planet A' })).toBeInTheDocument()
    const dossier = screen.getByRole('region', { name: /Physical and orbital measurements/ })
    expect(dossier).toHaveTextContent('Mass')
    expect(dossier).toHaveTextContent('Not available')
    expect(dossier).toHaveTextContent('0 unitless · zero retained')
    expect(dossier).toHaveTextContent('Fixture Facility')
    expect(screen.getAllByText('Within Q1–Q3')).toHaveLength(4)
    expect(screen.getByText(/Nearest 2 of 5,272 candidates/)).toBeInTheDocument()
    const orderedNeighbors = screen.getByRole('list')
    expect(within(orderedNeighbors).getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent)).toEqual(['Fixture Planet B', 'Fixture Planet C'])
    expect(screen.queryByText('Fixture Planet A', { selector: 'h3' })).not.toBeInTheDocument()
    expect(screen.getByText(/not a probability, physical identity/)).toBeInTheDocument()
  })

  it('compares the original measurements side by side', async () => {
    const user = userEvent.setup()
    installApi()
    renderExplorer('/explorer?planet=Fixture%20Planet%20A')
    await screen.findByRole('heading', { name: 'Fixture Planet A' })
    await user.click(screen.getAllByRole('button', { name: 'Compare' })[0])

    const comparison = await screen.findByRole('region', { name: /Fixture Planet A and Fixture Planet B/ })
    expect(comparison).toHaveTextContent('Planetary radius')
    expect(comparison).toHaveTextContent('2 Earth radii')
    expect(comparison).toHaveTextContent('3 Earth radii')
    await user.click(within(comparison).getByRole('button', { name: 'Close comparison' }))
    await waitFor(() => expect(screen.queryByRole('region', { name: /Fixture Planet A and Fixture Planet B/ })).not.toBeInTheDocument())
  })

  it('keeps a confirmed but ineligible planet and explains why no neighbors are ranked', async () => {
    installApi(unassigned)
    renderExplorer('/explorer?planet=Fixture%20Incomplete')

    expect(await screen.findByRole('heading', { name: 'Fixture Incomplete' })).toBeInTheDocument()
    expect(screen.getByText('Unassigned · confirmed planet')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Four-feature comparison is unavailable for this record.' })).toBeInTheDocument()
    expect(screen.getByText(/outside the approved four-feature complete-case cohort/)).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('uses actual catalogue search suggestions and opens the selected record', async () => {
    const user = userEvent.setup()
    installApi()
    renderExplorer()
    const input = screen.getByRole('searchbox', { name: 'Planet or host name' })
    await user.type(input, 'Fixture')
    const suggestion = await screen.findByRole('button', { name: /Fixture Planet A/ })
    await user.click(suggestion)
    expect(await screen.findByRole('heading', { name: 'Fixture Planet A' })).toBeInTheDocument()
  })

  it('reports an API error without substituting sample records', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: { message: 'Record service unavailable.' } }), { status: 503 })))
    renderExplorer('/explorer?planet=Missing%20Planet')
    expect(await screen.findByRole('alert')).toHaveTextContent('Record service unavailable.')
    expect(screen.queryByText('Fixture Planet A')).not.toBeInTheDocument()
  })
})
