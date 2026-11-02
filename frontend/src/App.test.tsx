import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { createUniverseTestPlanets, universeFixtureFetch } from './features/universe/universeTestFixtures'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function renderShell(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppShell />
    </MemoryRouter>,
  )
}

describe('ExoAtlas application shell', () => {
  it('renders the introduction and its central scientific question', () => {
    renderShell()

    expect(screen.getByRole('heading', { level: 1, name: 'What can confirmed worlds tell us?' })).toBeInTheDocument()
    expect(screen.getByText(/Can confirmed exoplanets be grouped by their physical and orbital characteristics/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Begin with The Universe/ })).toHaveAttribute('href', '/universe')
  })

  it('exposes five named destinations through semantic primary navigation', () => {
    renderShell()

    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' })
    const links = within(navigation).getAllByRole('link')
    expect(links).toHaveLength(5)
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/universe',
      '/patterns',
      '/explorer',
      '/outliers',
      '/discovery-lens',
    ])
    for (const name of ['The Universe', 'The Patterns', 'The Explorer', 'The Outliers', 'The Discovery Lens']) {
      expect(within(navigation).getByRole('link', { name: new RegExp(name) })).toBeInTheDocument()
    }
  })

  it('marks the route as active and focuses its page heading after navigation', async () => {
    const user = userEvent.setup()
    renderShell()

    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' })
    await user.click(within(navigation).getByRole('link', { name: /The Patterns/ }))

    const activeLink = within(navigation).getByRole('link', { name: /The Patterns/ })
    expect(activeLink).toHaveAttribute('aria-current', 'page')
    expect(await screen.findByRole('heading', { level: 1, name: 'The Patterns' }, { timeout: 12000 })).toHaveFocus()
  }, 15000)

  it('routes The Outliers to the saved scientific investigation', async () => {
    const observation = {
      pl_name: 'Test Planet b', hostname: 'Test Star', assignment_status: 'assigned', cluster_id: 0,
      centroid_distance: 1, cluster_distance_percentile: 99, silhouette_score: 0.1,
      pl_rade: 1, pl_orbper: 3, pl_eqt: 500, pl_orbeccen: 0,
      pl_rade_relation: 'within_q1_q3', pl_orbper_relation: 'above_q3', pl_eqt_relation: 'below_q1', pl_orbeccen_relation: 'within_q1_q3',
    }
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input), window.location.origin)
      const json = (payload: unknown) => Promise.resolve({ ok: true, status: 200, json: async () => payload } as Response)
      if (url.pathname === '/api/outliers/overview') return json({
        summary: { catalogue_records: 1, assigned_records: 1, unassigned_records: 0, negative_silhouette_records: 0 },
        distributions: {
          centroid_distance_percentile: { minimum: 99, q1: 99, median: 99, q3: 99, maximum: 99, histogram: { '0-10': 0, '10-20': 0, '20-30': 0, '30-40': 0, '40-50': 0, '50-60': 0, '60-70': 0, '70-80': 0, '80-90': 0, '90-100': 1 } },
          silhouette: { minimum: 0.1, median: 0.1, maximum: 0.1, negative_count: 0, histogram: {} },
          feature_relations: {
            pl_rade: { below_q1: 0, within_q1_q3: 1, above_q3: 0 },
            pl_orbper: { below_q1: 0, within_q1_q3: 1, above_q3: 0 },
            pl_eqt: { below_q1: 0, within_q1_q3: 1, above_q3: 0 },
            pl_orbeccen: { below_q1: 0, within_q1_q3: 1, above_q3: 0 },
          },
        },
        method: {}, limitations: [], cluster_profiles: [],
      })
      if (url.pathname === '/api/outliers/observations') return json({
        pagination: { page: 1, page_size: 20, total_records: 1, total_pages: 1 },
        filters: {}, records: [observation], ranking_note: 'Test fixture only.',
      })
      if (url.pathname.startsWith('/api/outliers/planets/')) return json({
        record: observation, diagnostics_available: true, cluster_profile: null, feature_comparisons: [], unavailable_reason: null,
      })
      return Promise.resolve({ ok: false, status: 404, json: async () => ({ error: { message: 'Not found.' } }) } as Response)
    }))
    renderShell('/outliers')

    expect(await screen.findByRole('heading', { level: 1, name: 'The Outliers' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { level: 2, name: 'Three diagnostics, three questions.' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { level: 3, name: 'Test Planet b' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open this planet in the explorer/i })).toHaveAttribute('href', '/explorer?planet=Test%20Planet%20b')
  })

  it('routes The Universe to the complete population experience', async () => {
    vi.stubGlobal('fetch', vi.fn(universeFixtureFetch(createUniverseTestPlanets(101))))
    renderShell('/universe')

    expect(await screen.findByRole('heading', { level: 1, name: 'The Universe' }, { timeout: 5000 })).toBeInTheDocument()
    expect(await screen.findByText(/100 shown/)).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Primary navigation' }).querySelector('[aria-current="page"]'))
      .toHaveTextContent('The Universe')
  })

  it('restores a selected planet from the URL and links its dossier into The Explorer', async () => {
    vi.stubGlobal('fetch', vi.fn(universeFixtureFetch(createUniverseTestPlanets(101))))
    renderShell('/universe?planet=Fixture%20Planet%20001')

    const title = await screen.findByRole('heading', { level: 2, name: 'Fixture Planet 001' })
    expect(title).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Open scientific dossier/ })).toHaveAttribute(
      'href',
      '/explorer?planet=Fixture%20Planet%20001',
    )
  })

  it('keeps the selected planet available while moving between chapters', () => {
    renderShell('/universe?planet=Kepler-22b')

    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' })
    expect(within(navigation).getByRole('link', { name: /The Patterns/ })).toHaveAttribute(
      'href',
      '/patterns?planet=Kepler-22b',
    )
    expect(within(navigation).getByRole('link', { name: /The Explorer/ })).toHaveAttribute(
      'href',
      '/explorer?planet=Kepler-22b',
    )
    expect(screen.getByText('Kepler-22b')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Open planet dossier/ })).toHaveAttribute(
      'href',
      '/explorer?planet=Kepler-22b',
    )
  })

  it('opens the mobile navigation and closes it after choosing a chapter', async () => {
    const user = userEvent.setup()
    renderShell()

    const menuButton = screen.getByRole('button', { name: 'Open navigation' })
    await user.click(menuButton)
    expect(menuButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('navigation', { name: 'Primary navigation' }).querySelector('ul')).toHaveAttribute('data-open', 'true')

    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' })
    await user.click(within(navigation).getByRole('link', { name: /The Explorer/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'The Explorer' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open navigation' })).toHaveAttribute('aria-expanded', 'false')
    expect(within(navigation).getByRole('link', { name: /The Explorer/ })).toHaveAttribute('aria-current', 'page')
  })

  it('closes the mobile menu on Escape and returns focus to its control', () => {
    renderShell()

    const menuButton = screen.getByRole('button', { name: 'Open navigation' })
    fireEvent.click(menuButton)
    expect(menuButton).toHaveAttribute('aria-expanded', 'true')
    fireEvent.keyDown(window, { key: 'Escape' })

    expect(screen.getByRole('button', { name: 'Open navigation' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('button', { name: 'Open navigation' })).toHaveFocus()
  })

  it('provides a keyboard-accessible skip link to the main content', () => {
    renderShell()

    const skipLink = screen.getByRole('link', { name: 'Skip to main content' })
    expect(skipLink).toHaveAttribute('href', '#main-content')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
  })
})
