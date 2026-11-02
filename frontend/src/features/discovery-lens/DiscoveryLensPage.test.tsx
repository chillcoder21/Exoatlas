import '@testing-library/jest-dom/vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DiscoveryLensPage } from './DiscoveryLensPage'

type CsvRow = Record<string, string>

function parseCsv(content: string): CsvRow[] {
  const lines = content.trim().split(/\r?\n/)
  function parseLine(line: string): string[] {
    const values: string[] = []
    let value = ''
    let quoted = false
    for (let index = 0; index < line.length; index += 1) {
      const character = line[index]
      if (character === '"') {
        if (quoted && line[index + 1] === '"') { value += '"'; index += 1 }
        else quoted = !quoted
      } else if (character === ',' && !quoted) {
        values.push(value)
        value = ''
      } else value += character
    }
    values.push(value)
    return values
  }
  const header = parseLine(lines[0])
  return lines.slice(1).map((line) => {
    const fields = parseLine(line)
    return Object.fromEntries(header.map((column, index) => [column, fields[index] ?? '']))
  })
}

function readProjectFile(relative: string) {
  return readFileSync(resolve(process.cwd(), '..', relative), 'utf8')
}

const report = JSON.parse(readProjectFile('data/metadata/discovery_lens_report.json')) as {
  source: Record<string, unknown>
  dataset: Record<string, number>
  methods: Record<string, number | string>[]
  limitations: string[]
}
const timelineRows = parseCsv(readProjectFile('data/processed/discovery_method_timeline.csv'))
const propertyRows = parseCsv(readProjectFile('data/processed/discovery_method_property_summary.csv'))
const propertyValues = parseCsv(readProjectFile('data/processed/discovery_property_values.csv'))
const facilityRows = parseCsv(readProjectFile('data/processed/discovery_facility_counts.csv'))

function response(payload: unknown, status = 200) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: async () => payload } as Response)
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function selectedFrom(url: URL) {
  const methods = url.searchParams.getAll('method')
  return methods.length ? methods : report.methods.map((item) => String(item.discovery_method))
}

function mockFetch() {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), window.location.origin)
    if (url.pathname === '/api/discovery/overview') {
      return response({
        source: report.source,
        snapshot_date: report.source.snapshot_date,
        total_planet_records: report.dataset.planet_records,
        number_of_discovery_methods: report.dataset.discovery_methods,
        number_of_discovery_years: report.dataset.discovery_years_with_records,
        number_of_facilities: report.dataset.facilities,
        number_of_unique_host_systems: report.dataset.unique_host_systems,
        first_discovery_year: report.dataset.first_discovery_year,
        last_discovery_year: report.dataset.last_discovery_year,
        methods: report.methods,
        limitations: report.limitations,
      })
    }
    if (url.pathname === '/api/discovery/timeline') {
      const methods = selectedFrom(url)
      const years = Array.from({ length: 35 }, (_, offset) => {
        const year = 1992 + offset
        const rows = timelineRows.filter((row) => Number(row.discovery_year) === year)
        const selected = rows.filter((row) => methods.includes(row.discovery_method))
        return {
          year,
          total_planet_records: Number(rows[0]?.year_total ?? 0),
          selected_method_planet_records: selected.reduce((total, row) => total + Number(row.planet_count), 0),
          methods: selected.map((row) => ({
            discovery_method: row.discovery_method,
            planet_count: Number(row.planet_count),
            within_year_percentage: Number(row.within_year_percentage),
          })),
          is_partial_year: year === 2026,
        }
      })
      return response({ snapshot_date: report.source.snapshot_date, selected_methods: methods, partial_year: { year: 2026, is_partial: true, as_of_date: report.source.snapshot_date, note: 'Partial year' }, interpretation_note: 'Catalogue timeline', years })
    }
    if (url.pathname === '/api/discovery/distributions') {
      const property = url.searchParams.get('property') ?? 'pl_rade'
      const methods = selectedFrom(url)
      const distributions = propertyRows.filter((row) => row.property === property && methods.includes(row.discovery_method)).map((row) => ({
        discovery_method: row.discovery_method,
        total_planet_records: Number(row.total_planet_records),
        error_1_field: row.error_1_field,
        error_2_field: row.error_2_field,
        measured_count: Number(row.measured_count),
        missing_count: Number(row.missing_count),
        zero_measurement_count: Number(row.zero_measurement_count),
        measurement_availability_pct: Number(row.measurement_availability_pct),
        median: row.median === '' ? null : Number(row.median),
        q1: row.q1 === '' ? null : Number(row.q1),
        q3: row.q3 === '' ? null : Number(row.q3),
        minimum: row.minimum === '' ? null : Number(row.minimum),
        maximum: row.maximum === '' ? null : Number(row.maximum),
        unique_hosts_measured: Number(row.unique_hosts_measured),
        uncertainty_count: Number(row.uncertainty_count),
        error_1_count: Number(row.error_1_count),
        error_2_count: Number(row.error_2_count),
        uncertainty_availability_pct: Number(row.uncertainty_availability_pct),
        sample_size_warning: { is_small: row.sample_size_is_small === 'True', message: row.sample_size_is_small === 'True' ? 'Small sample' : null },
        observations: propertyValues.filter((item) => item.property === property && item.discovery_method === row.discovery_method).map((item) => ({
          pl_name: item.pl_name,
          hostname: item.hostname,
          value: Number(item.value),
          error_1: item.error_1 === '' ? null : Number(item.error_1),
          error_2: item.error_2 === '' ? null : Number(item.error_2),
          uncertainty_available: item.uncertainty_available === 'True',
        })),
      }))
      const properties = { pl_rade: ['Planet radius', 'Earth radii', 'log'], pl_orbper: ['Orbital period', 'days', 'log'], pl_eqt: ['Equilibrium temperature', 'K', 'linear'], pl_orbeccen: ['Orbital eccentricity', 'dimensionless', 'linear'] } as const
      const [label, unit, axis_scale] = properties[property as keyof typeof properties]
      return response({ property, label, unit, axis_scale, selected_methods: methods, host_independence_note: 'Not independent host observations.', uncertainty_note: 'Original signed err1 and err2 values are kept.', distributions })
    }
    if (url.pathname === '/api/discovery/facilities') {
      const methods = selectedFrom(url)
      const selected = facilityRows.filter((row) => methods.includes(row.discovery_method))
      const counts = new Map<string, number>()
      selected.forEach((row) => counts.set(row.facility, (counts.get(row.facility) ?? 0) + Number(row.planet_count)))
      const denominator = report.methods.filter((row) => methods.includes(String(row.discovery_method))).reduce((total, row) => total + Number(row.planet_count), 0)
      const facilities = [...counts].map(([facility, planet_count]) => ({ facility, planet_count, percentage: planet_count / denominator * 100 }))
        .sort((left, right) => right.planet_count - left.planet_count || left.facility.localeCompare(right.facility))
      return response({ scope: url.searchParams.getAll('method'), denominator_planet_records: denominator, records_without_facility: 0, facility_count: facilities.length, facilities, interpretation_note: 'Facility counts are not independent surveys.' })
    }
    return response({ error: { message: 'Unexpected test request.' } }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function LocationProbe() {
  const location = useLocation()
  useEffect(() => { window.history.replaceState({}, '', `${location.pathname}${location.search}`) }, [location])
  return <output data-testid="location">{location.pathname}{location.search}</output>
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('The Discovery Lens', () => {
  it('presents the five connected investigations and the catalogue boundary', async () => {
    mockFetch()
    render(<MemoryRouter initialEntries={['/discovery-lens']}><LocationProbe /><DiscoveryLensPage /></MemoryRouter>)

    expect(await screen.findByRole('heading', { level: 1, name: 'The Discovery Lens' })).toBeInTheDocument()
    expect(screen.getByText(/not planet occurrence rates/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Which methods dominate this catalogue?' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'How has the recorded mix changed?' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'What properties are represented by each method?' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'How do the selected catalogue groups differ?' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'What does the catalogue not measure consistently?' })).toBeInTheDocument()
    expect(await screen.findByText(/1993 is shown as zero records/)).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Disk Kinematics' })).toBeInTheDocument()
    expect(screen.getAllByText('2026-10-30').length).toBeGreaterThan(0)
    const smallGroupRow = await screen.findByRole('row', { name: /Pulsation Timing Variations/ })
    expect(smallGroupRow).toHaveTextContent('Raw observations only · n=2')
    const distributionChart = screen.getByRole('img', { name: /Planet radius distribution/ })
    expect(Array.from(distributionChart.querySelectorAll('circle title'))
      .filter((node) => node.textContent?.includes('Pulsation Timing Variations:'))).toHaveLength(2)
  })

  it('keeps the selected property and exact discovery method in the URL', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch()
    render(<MemoryRouter initialEntries={['/discovery-lens']}><LocationProbe /><DiscoveryLensPage /></MemoryRouter>)

    const selector = await screen.findByRole('combobox', { name: 'Physical property' })
    await user.selectOptions(selector, 'pl_eqt')
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('property=pl_eqt'))
    await user.click(screen.getByRole('checkbox', { name: 'Transit' }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('method=Transit'))
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/api/discovery/distributions?property=pl_eqt&method=Transit'))).toBe(true)
    })
    await user.click(screen.getByRole('checkbox', { name: 'Radial Velocity' }))
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/api/discovery/distributions?property=pl_eqt&method=Transit&method=Radial+Velocity'))).toBe(true)
    })
    expect(screen.getByRole('row', { name: /Transit/ })).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /Radial Velocity/ })).toBeInTheDocument()
  })

  it.each([
    ['pl_rade', 'Planet radius', 'Earth radii', 'logarithmic'],
    ['pl_orbper', 'Orbital period', 'days', 'logarithmic'],
    ['pl_eqt', 'Equilibrium temperature', 'K', 'linear'],
    ['pl_orbeccen', 'Orbital eccentricity', 'dimensionless', 'linear'],
  ])('switches to %s with its measured unit and %s axis', async (property, label, unit, scale) => {
    const user = userEvent.setup()
    const fetchMock = mockFetch()
    render(<MemoryRouter initialEntries={['/discovery-lens']}><DiscoveryLensPage /></MemoryRouter>)
    const selector = await screen.findByRole('combobox', { name: 'Physical property' })

    await user.selectOptions(selector, property)

    const chart = await screen.findByRole('img', {
      name: new RegExp(`${label} distribution.*${unit} on a ${scale} scale`, 'i'),
    })
    expect(screen.getByRole('heading', { name: `${label} (${unit})` })).toBeInTheDocument()
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input]) => String(input).includes(`/api/discovery/distributions?property=${property}`))).toBe(true)
    })
    await waitFor(() => {
      expect(Array.from(chart.querySelectorAll('text')).some((node) =>
        node.textContent?.includes(`${label} (${unit}) · ${scale} scale`),
      )).toBe(true)
    })
    if (property === 'pl_orbeccen') {
      await waitFor(() => expect(screen.getAllByText(/Measured zero eccentricities are retained \(3,156 in this view\)/)).toHaveLength(2))
      expect(screen.getByRole('columnheader', { name: 'Measured zeros' })).toBeInTheDocument()
      expect(screen.getByRole('row', { name: /Disk Kinematics/ })).toHaveTextContent('No measured values')
    }
  })

  it('reveals every facility with exact counts in descending-count and name order', async () => {
    const user = userEvent.setup()
    mockFetch()
    render(<MemoryRouter initialEntries={['/discovery-lens']}><DiscoveryLensPage /></MemoryRouter>)

    const summary = await screen.findByText('View all 73 facilities and exact counts')
    await user.click(summary)
    const items = screen.getByRole('list').querySelectorAll('li')
    const totals = new Map<string, number>()
    facilityRows.forEach((row) => totals.set(row.facility, (totals.get(row.facility) ?? 0) + Number(row.planet_count)))
    const expected = [...totals].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))

    expect(items).toHaveLength(73)
    expect(expected.reduce((total, [, count]) => total + count, 0)).toBe(6451)
    expected.forEach(([facility, count], index) => {
      expect(items[index]).toHaveTextContent(facility)
      expect(items[index]).toHaveTextContent(`${new Intl.NumberFormat('en').format(count)} records`)
    })
  })

  it('does not let a delayed property response replace a newer selection', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch()
    const defaultFetch = fetchMock.getMockImplementation()!
    const delayed = deferred<Response>()
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), window.location.origin)
      if (url.pathname === '/api/discovery/distributions' && url.searchParams.get('property') === 'pl_eqt') {
        return delayed.promise
      }
      return defaultFetch(input)
    })
    render(<MemoryRouter initialEntries={['/discovery-lens']}><DiscoveryLensPage /></MemoryRouter>)

    const selector = await screen.findByRole('combobox', { name: 'Physical property' })
    await user.selectOptions(selector, 'pl_eqt')
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).includes('property=pl_eqt'))).toBe(true))
    await user.selectOptions(selector, 'pl_orbeccen')
    await screen.findByRole('img', { name: /Orbital eccentricity distribution/ })
    delayed.resolve(await defaultFetch('/api/discovery/distributions?property=pl_eqt'))

    await waitFor(() => {
      expect(screen.getByRole('img', { name: /Orbital eccentricity distribution/ })).toBeInTheDocument()
      expect(screen.queryByRole('img', { name: /Equilibrium temperature distribution/ })).not.toBeInTheDocument()
    })
  })

  it('shows a retry action after a catalogue request fails', async () => {
    const user = userEvent.setup()
    const fetchMock = mockFetch()
    const defaultFetch = fetchMock.getMockImplementation()!
    let shouldFail = true
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), window.location.origin)
      if (shouldFail && url.pathname === '/api/discovery/overview') return Promise.reject(new Error('offline for this request'))
      return defaultFetch(input)
    })
    render(<MemoryRouter initialEntries={['/discovery-lens']}><DiscoveryLensPage /></MemoryRouter>)

    expect(await screen.findByRole('alert')).toHaveTextContent('offline for this request')
    shouldFail = false
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('heading', { name: 'The Discovery Lens' })).toBeInTheDocument()
  })

  it('announces loading while the overview request is pending', async () => {
    const fetchMock = mockFetch()
    const defaultFetch = fetchMock.getMockImplementation()!
    const pending = deferred<Response>()
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), window.location.origin)
      return url.pathname === '/api/discovery/overview' ? pending.promise : defaultFetch(input)
    })
    render(<MemoryRouter initialEntries={['/discovery-lens']}><DiscoveryLensPage /></MemoryRouter>)

    expect(screen.getByRole('status')).toHaveTextContent('Loading the confirmed-planet catalogue summaries')
    pending.resolve(await defaultFetch('/api/discovery/overview'))
    expect(await screen.findByRole('heading', { name: 'The Discovery Lens' })).toBeInTheDocument()
  })
})
