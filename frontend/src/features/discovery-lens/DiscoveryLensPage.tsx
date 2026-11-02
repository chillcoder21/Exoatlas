import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  loadDiscoveryDistributions,
  loadDiscoveryFacilities,
  loadDiscoveryOverview,
  loadDiscoveryTimeline,
} from './api'
import {
  CompositionChart,
  DistributionChart,
  FacilitiesChart,
  MissingnessChart,
  TimelineChart,
} from './DiscoveryLensCharts'
import type {
  DiscoveryDistributions,
  DiscoveryFacilities,
  DiscoveryOverview,
  DiscoveryProperty,
  DiscoveryTimeline,
} from './types'
import styles from './DiscoveryLensPage.module.css'

const propertyOptions: { value: DiscoveryProperty; label: string; unit: string }[] = [
  { value: 'pl_rade', label: 'Planet radius', unit: 'Earth radii' },
  { value: 'pl_orbper', label: 'Orbital period', unit: 'days' },
  { value: 'pl_eqt', label: 'Equilibrium temperature', unit: 'K' },
  { value: 'pl_orbeccen', label: 'Orbital eccentricity', unit: 'dimensionless' },
]

const investigations = [
  ['catalogue-composition', '01', 'Catalogue composition'],
  ['discovery-through-time', '02', 'Discovery through time'],
  ['detection-fingerprints', '03', 'Detection fingerprints'],
  ['method-comparison', '04', 'Method comparison'],
  ['observational-blind-spot', '05', 'Observational blind spot'],
] as const

function number(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'Not measured'
  return new Intl.NumberFormat('en', { maximumFractionDigits: digits }).format(value)
}

function percent(value: number) {
  return `${value.toFixed(1)}%`
}

function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return (
    <div className={styles.errorState} role="alert">
      <div>
        <strong>The Discovery Lens could not load.</strong>
        <p>{message}</p>
      </div>
      <button className={styles.retryButton} type="button" onClick={retry}>Retry</button>
    </div>
  )
}

function MethodFilters({
  overview,
  selectedMethods,
  onToggle,
  onClear,
}: {
  overview: DiscoveryOverview
  selectedMethods: string[]
  onToggle: (method: string) => void
  onClear: () => void
}) {
  return (
    <fieldset className={styles.methodFilters}>
      <legend>Compare discovery methods</legend>
      <p className={styles.filterNote}>
        {selectedMethods.length === 0
          ? 'No filter is active; all 11 methods are shown.'
          : `Filtering to ${selectedMethods.length} selected ${selectedMethods.length === 1 ? 'method' : 'methods'}.`}
      </p>
      <div className={styles.methodOptions}>
        {overview.methods.map((method) => (
          <label className={styles.methodOption} key={method.discovery_method}>
            <input
              type="checkbox"
              checked={selectedMethods.includes(method.discovery_method)}
              onChange={() => onToggle(method.discovery_method)}
            />
            <span>{method.discovery_method}</span>
          </label>
        ))}
      </div>
      {selectedMethods.length > 0 && (
        <button className={styles.textButton} type="button" onClick={onClear}>Show all methods</button>
      )}
    </fieldset>
  )
}

function ComparisonTable({
  overview,
  data,
  selectedMethods,
}: {
  overview: DiscoveryOverview
  data: DiscoveryDistributions
  selectedMethods: string[]
}) {
  const selected = selectedMethods.length ? selectedMethods : overview.methods.map((item) => item.discovery_method)
  const methods = overview.methods.filter((item) => selected.includes(item.discovery_method))
  const distributions = new Map(data.distributions.map((item) => [item.discovery_method, item]))
  return (
    <div className={styles.tableScroll} role="region" aria-label={`${data.label} comparison by method`} tabIndex={0}>
      <table className={styles.comparisonTable}>
        <caption>
          Planet and host counts are separate. Host totals can overlap between methods; measured values can be missing.
        </caption>
        <thead>
          <tr>
            <th scope="col">Discovery method</th>
            <th scope="col">Planet records</th>
            <th scope="col">Unique hosts</th>
            <th scope="col">Measured / missing</th>
            <th scope="col">Measured zeros</th>
            <th scope="col">Availability</th>
            <th scope="col">Q1 · median · Q3 ({data.unit})</th>
            <th scope="col">Paired uncertainty</th>
          </tr>
        </thead>
        <tbody>
          {methods.map((method) => {
            const distribution = distributions.get(method.discovery_method)
            return (
              <tr key={method.discovery_method}>
                <th scope="row">
                  {method.discovery_method}
                  {distribution?.sample_size_warning.is_small && <span className={styles.smallSample}>Small n</span>}
                </th>
                <td>{number(method.planet_count)} <span>({percent(method.catalogue_percentage)} of {number(overview.total_planet_records)})</span></td>
                <td>{number(method.unique_host_count)}</td>
                <td>{distribution ? `${number(distribution.measured_count)} / ${number(distribution.missing_count)}` : '—'}</td>
                <td>{distribution ? number(distribution.zero_measurement_count) : '—'}</td>
                <td>{distribution ? percent(distribution.measurement_availability_pct) : '—'}</td>
                <td>
                  {distribution?.measured_count === 0
                    ? 'No measured values'
                    : distribution?.sample_size_warning.is_small
                      ? `Raw observations only · n=${number(distribution.measured_count)}`
                      : distribution && distribution.median !== null
                    ? `${number(distribution.q1, 4)} · ${number(distribution.median, 4)} · ${number(distribution.q3, 4)}`
                    : 'Not measured'}
                </td>
                <td>
                  {distribution
                    ? `${number(distribution.uncertainty_count)} of ${number(distribution.measured_count)} measured (${percent(distribution.uncertainty_availability_pct)})`
                    : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function SmallSampleNote({ data }: { data: DiscoveryDistributions }) {
  const smallSamples = data.distributions.filter((item) => item.sample_size_warning.is_small)
  if (smallSamples.length === 0) return null

  return (
    <p className={styles.smallSampleNote} role="note">
      <strong>Small samples:</strong>{' '}
      {smallSamples.map((item) => `${item.discovery_method} n=${number(item.measured_count)}`).join(' · ')}.
      {' '}Raw observations are shown and quartile summaries are withheld; these groups are descriptive, not statistically representative.
      {data.property === 'pl_orbeccen' && (
        <> Measured zero eccentricities are retained ({number(data.distributions.reduce((total, item) => total + item.zero_measurement_count, 0))} in this view).</>
      )}
    </p>
  )
}

export function DiscoveryLensPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const propertyParam = searchParams.get('property')
  const property: DiscoveryProperty = propertyOptions.some((item) => item.value === propertyParam)
    ? propertyParam as DiscoveryProperty
    : 'pl_rade'
  const selectedMethods = useMemo(() => searchParams.getAll('method'), [searchParams])
  const methodsKey = selectedMethods.join('\u0000')
  const [overview, setOverview] = useState<DiscoveryOverview | null>(null)
  const [timeline, setTimeline] = useState<DiscoveryTimeline | null>(null)
  const [distributions, setDistributions] = useState<DiscoveryDistributions | null>(null)
  const [facilities, setFacilities] = useState<DiscoveryFacilities | null>(null)
  const [overviewError, setOverviewError] = useState<string | null>(null)
  const [dataError, setDataError] = useState<string | null>(null)
  const [overviewLoading, setOverviewLoading] = useState(true)
  const [dataLoading, setDataLoading] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setOverviewLoading(true)
    setOverviewError(null)
    loadDiscoveryOverview(controller.signal)
      .then(setOverview)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setOverviewError(cause instanceof Error ? cause.message : 'Catalogue metadata could not be loaded.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setOverviewLoading(false)
      })
    return () => controller.abort()
  }, [attempt])

  useEffect(() => {
    if (!overview) return
    const controller = new AbortController()
    const methods = methodsKey ? methodsKey.split('\u0000') : []
    setDataLoading(true)
    setDataError(null)
    setTimeline(null)
    setDistributions(null)
    setFacilities(null)
    Promise.all([
      loadDiscoveryTimeline(methods, controller.signal),
      loadDiscoveryDistributions(property, methods, controller.signal),
      loadDiscoveryFacilities(methods, controller.signal),
    ])
      .then(([nextTimeline, nextDistributions, nextFacilities]) => {
        if (controller.signal.aborted) return
        setTimeline(nextTimeline)
        setDistributions(nextDistributions)
        setFacilities(nextFacilities)
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setDataError(cause instanceof Error ? cause.message : 'Discovery summaries could not be loaded.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false)
      })
    return () => controller.abort()
  }, [overview, property, methodsKey, attempt])

  function updateQuery(nextProperty: DiscoveryProperty, methods: string[]) {
    const next = new URLSearchParams(searchParams)
    next.delete('property')
    if (nextProperty !== 'pl_rade') next.set('property', nextProperty)
    next.delete('method')
    methods.forEach((method) => next.append('method', method))
    setSearchParams(next, { replace: true })
  }

  function toggleMethod(method: string) {
    const next = selectedMethods.includes(method)
      ? selectedMethods.filter((item) => item !== method)
      : [...selectedMethods, method]
    updateQuery(property, next)
  }

  if (overviewLoading && !overview) {
    return <div className={styles.loadState} role="status">Loading the confirmed-planet catalogue summaries…</div>
  }
  if (overviewError || !overview) {
    return <ErrorState message={overviewError ?? 'Catalogue metadata is unavailable.'} retry={() => setAttempt((value) => value + 1)} />
  }

  const activeProperty = propertyOptions.find((item) => item.value === property) ?? propertyOptions[0]
  const selectedMethodCount = selectedMethods.length || overview.number_of_discovery_methods

  return (
    <article className={styles.page}>
      <header className={styles.intro}>
        <p className={styles.eyebrow}><span className={styles.chapterNumber}>05</span> Observation · confirmation · catalogue</p>
        <h1 className={styles.title} id="page-title" tabIndex={-1}>The Discovery Lens</h1>
        <p className={styles.lead}>
          Compare the archive’s discovery methods, recorded years, measured properties and missingness. These are catalogue counts and measurements shaped by observation and reporting, not occurrence rates for the wider universe.
        </p>
        <p className={styles.boundaryNote}>
          These counts describe confirmed records in this catalogue. They are not planet occurrence rates, and observed associations do not show that a method causes a planet property.
        </p>
        <nav className={styles.investigationNav} aria-label="Discovery Lens investigations">
          {investigations.map(([id, index, label]) => <a key={id} href={`#${id}`}><span>{index}</span>{label}</a>)}
        </nav>
        <dl className={styles.catalogueFacts} aria-label="Catalogue scope">
          <div><dt>Planet records</dt><dd>{number(overview.total_planet_records)}</dd></div>
          <div><dt>Discovery methods</dt><dd>{number(overview.number_of_discovery_methods)}</dd></div>
          <div><dt>Host systems</dt><dd>{number(overview.number_of_unique_host_systems)}</dd></div>
          <div><dt>Facilities</dt><dd>{number(overview.number_of_facilities)}</dd></div>
          <div><dt>Snapshot</dt><dd>{overview.snapshot_date}</dd></div>
        </dl>
      </header>

      {dataError && <ErrorState message={dataError} retry={() => setAttempt((value) => value + 1)} />}
      {dataLoading && <div className={styles.inlineLoading} role="status">Updating the selected catalogue view…</div>}

      <section className={styles.investigation} id="catalogue-composition" aria-labelledby="composition-title">
        <div className={styles.sectionHeading}>
          <p className={styles.sectionIndex}>01 / Catalogue composition</p>
          <h2 id="composition-title">Which methods dominate this catalogue?</h2>
          <p>Every one of the 11 categories remains visible, including groups with only one or two records. Percentages use all {number(overview.total_planet_records)} catalogue planet records as their denominator.</p>
        </div>
        <MethodFilters
          overview={overview}
          selectedMethods={selectedMethods}
          onToggle={toggleMethod}
          onClear={() => updateQuery(property, [])}
        />
        <div className={styles.chartBlock}>
          <div className={styles.chartHeading}><h3>Planet records by discovery method</h3><span>Denominator: {number(overview.total_planet_records)} records</span></div>
          <CompositionChart overview={overview} selectedMethods={selectedMethods} />
          <p className={styles.chartCaption}>Bars show catalogue records and their share of the full catalogue. A larger count does not mean a higher occurrence rate in the universe.</p>
        </div>
        <div className={styles.facilityBlock}>
          <div className={styles.chartHeading}><h3>Facilities named in the catalogue</h3><span>{number(facilities?.facility_count ?? overview.number_of_facilities)} facilities · denominator {number(facilities?.denominator_planet_records ?? overview.total_planet_records)}</span></div>
          {facilities && <FacilitiesChart data={facilities} />}
          <p className={styles.chartCaption}>Facility counts are attributed planet records, not independent surveys, detections, or host systems. The bars show the 12 most represented facilities.</p>
          {facilities && (
            <details className={styles.facilityDetails}>
              <summary>View all {number(facilities.facility_count)} facilities and exact counts</summary>
              <ul>{facilities.facilities.map((facility) => <li key={facility.facility}><span>{facility.facility}</span><strong>{number(facility.planet_count)} records · {percent(facility.percentage)}</strong></li>)}</ul>
            </details>
          )}
        </div>
        <p className={styles.contextNote}>Methods have different sensitivities to planet size, orbit, system geometry, and signal. Their catalogue counts reflect which planets were detected, confirmed, and reported under those conditions.</p>
      </section>

      <section className={styles.investigation} id="discovery-through-time" aria-labelledby="timeline-title">
        <div className={styles.sectionHeading}>
          <p className={styles.sectionIndex}>02 / Discovery through time</p>
          <h2 id="timeline-title">How has the recorded mix changed?</h2>
          <p>The timeline follows discovery years recorded in the catalogue. Publication, confirmation, survey coverage, curation, and reporting also influence the pattern.</p>
        </div>
        {timeline && (
          <div className={styles.chartBlock}>
            <div className={styles.chartHeading}><h3>{selectedMethods.length ? 'Annual counts for selected methods' : 'All catalogue records by year'}</h3><span>1992–2026 · 2026 partial</span></div>
            <TimelineChart timeline={timeline} selectedMethods={selectedMethods} />
            <p className={styles.chartCaption}>1993 is shown as zero records. The dashed 2026 marker identifies a partial snapshot as of October 30, 2026; the line is not a complete census of discovery activity.</p>
            <details className={styles.dataDetails}>
              <summary>Read exact annual counts</summary>
              <div className={styles.annualList}>
                {timeline.years.map((year) => (
                  <div key={year.year}><strong>{year.year}{year.is_partial_year ? ' · partial' : ''}</strong><span>{number(year.total_planet_records)} total</span><span>{number(year.selected_method_planet_records)} selected</span></div>
                ))}
              </div>
            </details>
          </div>
        )}
      </section>

      <section className={styles.investigation} id="detection-fingerprints" aria-labelledby="fingerprints-title">
        <div className={styles.sectionHeading}>
          <p className={styles.sectionIndex}>03 / Detection fingerprints</p>
          <h2 id="fingerprints-title">What properties are represented by each method?</h2>
          <p>Quartile summaries describe measured catalogue values. Radius and orbital period use logarithmic axes; temperature and eccentricity use linear axes. No missing values are filled in.</p>
        </div>
        <label className={styles.propertyPicker}>
          <span>Physical property</span>
          <select value={property} onChange={(event) => updateQuery(event.target.value as DiscoveryProperty, selectedMethods)}>
            {propertyOptions.map((option) => <option key={option.value} value={option.value}>{option.label} · {option.unit}</option>)}
          </select>
        </label>
        {distributions && (
          <div className={styles.chartBlock}>
            <div className={styles.chartHeading}><h3>{activeProperty.label} ({activeProperty.unit})</h3><span>{selectedMethodCount} {selectedMethodCount === 1 ? 'method' : 'methods'} · measured observations only</span></div>
            <DistributionChart data={distributions} />
            <SmallSampleNote data={distributions} />
            <p className={styles.chartCaption}>Whiskers show the observed minimum and maximum; boxes show Q1–Q3 with the median marked. Groups with fewer than five measured values use individual points and an explicit sample size instead of a box.</p>
          </div>
        )}
      </section>

      <section className={styles.investigation} id="method-comparison" aria-labelledby="comparison-title">
        <div className={styles.sectionHeading}>
          <p className={styles.sectionIndex}>04 / Method comparison</p>
          <h2 id="comparison-title">How do the selected catalogue groups differ?</h2>
          <p>Compare record counts, unique hosts, measured and missing values, quartiles, and uncertainty coverage. Multiple planets around one host are not independent observations.</p>
        </div>
        {distributions && (
          <>
            <ComparisonTable overview={overview} data={distributions} selectedMethods={selectedMethods} />
            <SmallSampleNote data={distributions} />
            <p className={styles.contextNote}>{distributions.host_independence_note} Both catalogue error fields are required for paired uncertainty availability. {distributions.uncertainty_note}</p>
          </>
        )}
      </section>

      <section className={styles.investigation} id="observational-blind-spot" aria-labelledby="blindspot-title">
        <div className={styles.sectionHeading}>
          <p className={styles.sectionIndex}>05 / The observational blind spot</p>
          <h2 id="blindspot-title">What does the catalogue not measure consistently?</h2>
          <p>Each bar is partitioned into planet records with a measurement and records without one, within that method. Missingness can change which planets enter a property comparison.</p>
        </div>
        {distributions && (
          <div className={styles.chartBlock}>
            <div className={styles.chartHeading}><h3>{activeProperty.label}: measured and missing</h3><span>Denominator is the planet records in each method</span></div>
            <div className={styles.legend}><span><i data-kind="measured" />Measured</span><span><i data-kind="missing" />Missing measurement</span></div>
            <MissingnessChart data={distributions} />
            <p className={styles.chartCaption}>A missing measurement belongs to an existing planet record. It is not a zero value: 0 eccentricity is a measured circular-orbit value, while missing eccentricity is unknown. A missing temperature is not 0 K.</p>
          </div>
        )}
        <p className={styles.contextNote}>The catalogue includes {number(overview.number_of_unique_host_systems)} unique host systems, but method-level host counts can overlap. Observed groups also carry different selection effects and measurement availability, so comparisons describe this catalogue rather than an unbiased planetary population.</p>
      </section>

      <footer className={styles.sourceNote}>
        <p><strong>Catalogue snapshot:</strong> {overview.snapshot_date} · NASA Exoplanet Archive PSCompPars, downloaded {overview.source.download_timestamp}.</p>
        {!overview.source.raw_source_present && <p><strong>Source-file note:</strong> {overview.source.note}</p>}
        <p>Continue the story: <Link to="/universe">The Universe</Link> · <Link to="/patterns">The Patterns</Link> · <Link to="/explorer">The Explorer</Link> · <Link to="/outliers">The Outliers</Link></p>
      </footer>
    </article>
  )
}
