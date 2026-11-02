import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import * as d3 from 'd3'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { UniversePage } from './UniversePage'
import { createUniverseTestPlanets, jsonResponse, universeFixtureFetch } from './universeTestFixtures'

vi.mock('motion/react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('motion/react')>()
  return { ...actual, useReducedMotion: () => true }
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(universeFixtureFetch(createUniverseTestPlanets(101))))
})

describe('The Universe experience', () => {
  it('loads the complete API population and shows the API-reported totals', async () => {
    render(<MemoryRouter><UniversePage /></MemoryRouter>)

    expect(await screen.findByText(/100 shown/)).toBeInTheDocument()
    const summary = document.querySelector('dl[aria-label="Confirmed population counts"]')
    expect(summary).toHaveTextContent('101')
    expect(summary).toHaveTextContent('100')
    expect(summary).toHaveTextContent('1')
    expect(summary).toHaveTextContent('4')
    expect(screen.getAllByText(/PSCompPars-test-fixture/)).toHaveLength(2)
  })

  it('keeps unassigned planets visible and gives them a distinct hollow mark and legend entry', async () => {
    render(<MemoryRouter><UniversePage /></MemoryRouter>)
    await screen.findByText(/100 shown/)

    const visibility = screen.getByRole('group', { name: 'Population visibility' })
    expect(within(visibility).getByRole('checkbox', { name: /Unassigned/ })).toBeChecked()
    expect(within(visibility).getByText(/Unassigned/)).toBeInTheDocument()

    const unassignedMark = document.querySelector('[data-planet-id="Fixture Planet 101"]')
    expect(unassignedMark).toHaveAttribute('fill', 'var(--color-canvas)')
    expect(unassignedMark).toHaveAttribute('stroke-dasharray', '2.2 1.8')
  })

  it('updates axis labels and plots zero eccentricity on a linear axis', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><UniversePage /></MemoryRouter>)
    await screen.findByText(/100 shown/)

    await user.selectOptions(screen.getByRole('combobox', { name: 'Horizontal axis' }), 'pl_orbeccen')

    await waitFor(() => {
      expect(document.body).toHaveTextContent('Orbital eccentricity (unitless) · linear scale')
    })
    const circularOrbit = document.querySelector('[data-planet-id="Fixture Planet 001"]')
    expect(circularOrbit).toBeInTheDocument()
    expect(circularOrbit).toHaveAttribute('transform', expect.stringMatching(/^translate\(58,/))
    expect(document.body).toHaveTextContent('Planetary radius (Earth radii) · logarithmic scale')
  })

  it('shows the actual selected point record and supports clearing the selection', async () => {
    render(<MemoryRouter><UniversePage /></MemoryRouter>)
    await screen.findByText(/100 shown/)
    await waitFor(() => expect(document.querySelector('[data-planet-id="Fixture Planet 001"]')).toBeInTheDocument())

    fireEvent.click(document.querySelector('[data-planet-id="Fixture Planet 001"]')!)

    expect(await screen.findByRole('heading', { name: 'Fixture Planet 001' })).toBeInTheDocument()
    const inspector = screen.getByRole('complementary', { name: 'Fixture Planet 001' })
    expect(inspector).toHaveTextContent('Fixture Star 001')
    expect(inspector).toHaveTextContent('Exploratory K=4 · cluster 0')
    expect(inspector).toHaveTextContent('Orbital eccentricity')
    expect(inspector).toHaveTextContent('0 unitless')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Clear selection' }))
    expect(screen.getByText('A planet, in its measurements')).toBeInTheDocument()
  })

  it('reveals the hovered planet values in a concise tooltip', async () => {
    render(<MemoryRouter><UniversePage /></MemoryRouter>)
    await screen.findByText(/100 shown/)

    fireEvent.pointerEnter(document.querySelector('[data-planet-id="Fixture Planet 001"]')!, {
      clientX: 80,
      clientY: 100,
      pointerType: 'mouse',
    })

    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip).toHaveTextContent('Fixture Planet 001')
    expect(tooltip).toHaveTextContent('Eccentricity')
    expect(tooltip).toHaveTextContent('Exploratory cluster 0')
  })

  it('zooms the plot and resets its zoom transform', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><UniversePage /></MemoryRouter>)
    await screen.findByText(/100 shown/)
    const svg = screen.getByRole('img', { name: 'Interactive planetary feature-space map' }) as unknown as SVGSVGElement & {
      __zoom: { k: number }
    }

    fireEvent.wheel(svg, { deltaY: -220, clientX: 140, clientY: 140 })
    await waitFor(() => expect(svg.__zoom.k).toBeGreaterThan(1))
    await user.click(screen.getByRole('button', { name: 'Reset zoom' }))
    await waitFor(() => expect(svg.__zoom.k).toBe(1))
  })

  it('searches the full loaded population, including a last-page unassigned planet with missing measurements', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><UniversePage /></MemoryRouter>)
    await screen.findByText(/100 shown/)
    const search = screen.getByRole('searchbox', { name: 'Find a planet' })

    await user.type(search, 'Fixture Planet 101')
    await user.click(screen.getByRole('button', { name: /Fixture Planet 101/ }))

    const heading = await screen.findByRole('heading', { name: 'Fixture Planet 101' })
    expect(heading).toBeInTheDocument()
    expect(screen.getByText('Unassigned · confirmed planet')).toBeInTheDocument()
    const inspector = heading.closest('aside')!
    expect(inspector).toHaveTextContent('Not available K')
    expect(inspector).toHaveTextContent('valid values on both selected axes')
  })

  it('updates the visible population when a cluster is toggled', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><UniversePage /></MemoryRouter>)
    await screen.findByText(/100 shown/)

    await user.click(screen.getByRole('checkbox', { name: /Cluster 0/ }))

    expect(await screen.findByText(/75 shown/)).toBeInTheDocument()
    expect(screen.getByText(/25 hidden by population controls/)).toBeInTheDocument()
  })

  it('reports an empty name search without confusing it with an API failure', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><UniversePage /></MemoryRouter>)
    await screen.findByText(/100 shown/)
    await user.type(screen.getByRole('searchbox', { name: 'Find a planet' }), 'No Such Fixture')

    expect(screen.getByText(/No planet names or host stars match/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a loading state before any API data is available', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => undefined)))
    render(<MemoryRouter><UniversePage /></MemoryRouter>)

    expect(screen.getByRole('status')).toHaveTextContent('Loading and checking the confirmed planet records')
    expect(document.querySelector('dl[aria-label="Confirmed population counts"]')).not.toBeInTheDocument()
  })

  it('shows an honest retryable error when the API is unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ error: { message: 'API unavailable' } }, 503)),
    )
    render(<MemoryRouter><UniversePage /></MemoryRouter>)

    expect(await screen.findByRole('alert')).toHaveTextContent('The scientific dataset could not be loaded')
    expect(screen.getByRole('alert')).toHaveTextContent('No partial or sample population is being shown')
    expect(screen.queryByLabelText('Confirmed population counts')).not.toBeInTheDocument()
  })

  it('does not start D3 transitions when the reduced-motion preference is active', async () => {
    const transitionSpy = vi.spyOn(d3.selection.prototype, 'transition')
    render(<MemoryRouter><UniversePage /></MemoryRouter>)

    await screen.findByText(/100 shown/)
    expect(transitionSpy).not.toHaveBeenCalled()
  })
})

