import { useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { axisBottom, axisLeft, max, scaleLinear, select } from 'd3'
import type { OutlierDetail, OutlierObservation, OutlierOverview, OutlierListResponse } from './types'
import styles from './OutliersPage.module.css'

const featureDefinitions = [
  { key: 'pl_rade', label: 'Planetary radius', unit: 'Earth radii' },
  { key: 'pl_orbper', label: 'Orbital period', unit: 'days' },
  { key: 'pl_eqt', label: 'Equilibrium temperature', unit: 'K' },
  { key: 'pl_orbeccen', label: 'Orbital eccentricity', unit: 'dimensionless' },
] as const

async function fetchJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal })
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { error?: { message?: string } } | null
    throw new Error(payload?.error?.message ?? `The scientific data service returned ${response.status}.`)
  }
  return response.json() as Promise<T>
}

function formatValue(value: number | null | undefined, digits = 5): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'Not available'
  return new Intl.NumberFormat('en', { maximumSignificantDigits: digits }).format(value)
}

function labelRelation(value: string | null | undefined): string {
  if (value === 'below_q1') return 'Below Q1'
  if (value === 'above_q3') return 'Above Q3'
  if (value === 'within_q1_q3') return 'Within Q1–Q3'
  return 'Unavailable'
}

function PercentileChart({
  distribution,
  threshold,
  selectedPercentile,
}: {
  distribution: OutlierOverview['distributions']['centroid_distance_percentile']
  threshold: number
  selectedPercentile: number | null
}) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    const svg = select(svgRef.current)
    svg.selectAll('*').remove()
    const width = 720
    const height = 310
    const margin = { top: 24, right: 20, bottom: 62, left: 56 }
    const plotWidth = width - margin.left - margin.right
    const plotHeight = height - margin.top - margin.bottom
    const bins = Object.entries(distribution.histogram).map(([range, count]) => ({
      range,
      start: Number(range.split('-')[0]),
      end: Number(range.split('-')[1]),
      count,
    }))
    const x = scaleLinear().domain([0, 100]).range([0, plotWidth])
    const y = scaleLinear().domain([0, max(bins, (item) => item.count) ?? 1]).nice().range([plotHeight, 0])
    const plot = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

    plot.append('g')
      .attr('class', styles.chartGrid)
      .call(axisLeft(y).ticks(4).tickSize(-plotWidth).tickFormat(() => ''))
    plot.append('g')
      .attr('transform', `translate(0,${plotHeight})`)
      .attr('class', styles.chartAxis)
      .call(axisBottom(x).tickValues([0, 20, 40, 60, 80, 100]).tickFormat((value) => `${value}%`))
    plot.append('g').attr('class', styles.chartAxis).call(axisLeft(y).ticks(4).tickFormat((value) => Number(value).toLocaleString()))

    plot.selectAll('rect')
      .data(bins)
      .join('rect')
      .attr('x', (item) => x(item.start) + 2)
      .attr('y', (item) => y(item.count))
      .attr('width', (item) => Math.max(1, x(item.end) - x(item.start) - 4))
      .attr('height', (item) => plotHeight - y(item.count))
      .attr('fill', (item) => item.end > threshold ? 'var(--accent-coral)' : 'var(--accent-blue-muted)')
      .attr('fill-opacity', (item) => item.end > threshold ? 0.88 : 0.66)
      .append('title')
      .text((item) => `${item.range}% within-cluster distance percentile: ${item.count.toLocaleString()} planets`)

    if (selectedPercentile !== null) {
      plot.append('line')
        .attr('x1', x(selectedPercentile)).attr('x2', x(selectedPercentile))
        .attr('y1', 0).attr('y2', plotHeight)
        .attr('stroke', 'var(--color-text)').attr('stroke-width', 2).attr('stroke-dasharray', '4 4')
      plot.append('text')
        .attr('x', Math.min(plotWidth - 4, x(selectedPercentile) + 5)).attr('y', 12)
        .attr('fill', 'var(--color-text)').attr('font-size', 11)
        .text(`selected ${selectedPercentile.toFixed(1)}%`)
    }

    svg.attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet')
  }, [distribution, threshold, selectedPercentile])

  return (
    <svg
      ref={svgRef}
      className={styles.percentileChart}
      role="img"
      aria-label={`Histogram of within-cluster centroid-distance percentiles across ${Object.values(distribution.histogram).reduce((total, count) => total + count, 0).toLocaleString()} assigned planets.`}
    >
      <title>Within-cluster centroid-distance percentile distribution</title>
    </svg>
  )
}

export function OutliersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get('planet')
  const [overview, setOverview] = useState<OutlierOverview | null>(null)
  const [observations, setObservations] = useState<OutlierObservation[]>([])
  const [selected, setSelected] = useState<OutlierDetail | null>(null)
  const [comparison, setComparison] = useState<OutlierObservation[]>([])
  const [minimumPercentile, setMinimumPercentile] = useState(90)
  const [clusterFilter, setClusterFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState<'distance_percentile' | 'silhouette'>('distance_percentile')
  const [pageSize, setPageSize] = useState(20)
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState<OutlierListResponse['pagination'] | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    fetchJson<OutlierOverview>('/api/outliers/overview', controller.signal)
      .then(setOverview)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Outlier summaries could not be loaded.')
      })
    return () => controller.abort()
  }, [attempt])

  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true)
      setError(null)
      const params = new URLSearchParams({
        percentile_min: String(minimumPercentile),
        page: String(page),
        page_size: String(pageSize),
        sort_by: sortBy,
      })
      if (clusterFilter !== 'all') params.set('cluster_id', clusterFilter)
      if (search.trim()) params.set('search', search.trim())
      fetchJson<OutlierListResponse>(`/api/outliers/observations?${params.toString()}`, controller.signal)
        .then((payload) => {
          setObservations(payload.records)
          setPagination(payload.pagination)
        })
        .catch((cause: unknown) => {
          if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Outlier observations could not be loaded.')
        })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, 160)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [attempt, minimumPercentile, clusterFilter, search, sortBy, page, pageSize])

  useEffect(() => {
    if (!selectedId) {
      setSelected(null)
      setDetailError(null)
      return
    }
    const controller = new AbortController()
    setDetailLoading(true)
    setDetailError(null)
    fetchJson<OutlierDetail>(`/api/outliers/planets/${encodeURIComponent(selectedId)}`, controller.signal)
      .then((payload) => {
        if (payload.record.pl_name !== selectedId) throw new Error('The outlier service returned a different planet record.')
        setSelected(payload)
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setDetailError(cause instanceof Error ? cause.message : 'Planet diagnostics could not be loaded.')
      })
      .finally(() => { if (!controller.signal.aborted) setDetailLoading(false) })
    return () => controller.abort()
  }, [selectedId, attempt])

  useEffect(() => {
    if (selectedId || loading || observations.length === 0) return
    setSearchParams({ planet: observations[0].pl_name }, { replace: true })
  }, [selectedId, loading, observations, setSearchParams])

  const selectedPercentile = selected?.record.cluster_distance_percentile ?? null
  const selectedCluster = useMemo(
    () => selected?.record.cluster_id === null || selected?.record.cluster_id === undefined
      ? null
      : overview?.cluster_profiles.find((cluster) => cluster.cluster_id === selected.record.cluster_id) ?? null,
    [selected, overview],
  )

  function setPlanet(planet: string) {
    setSearchParams({ planet })
  }

  function updateListFilter(update: () => void) {
    update()
    setPage(1)
  }

  function toggleComparison(observation: OutlierObservation) {
    setComparison((current) => {
      const existing = current.find((item) => item.pl_name === observation.pl_name)
      if (existing) return current.filter((item) => item.pl_name !== observation.pl_name)
      if (current.length >= 2) return current
      return [...current, observation]
    })
  }

  if (!overview && error) {
    return (
      <div className={styles.loadState} role="alert">
        <p className={styles.eyebrow}>The Outliers · data unavailable</p>
        <h1 className={styles.title} id="page-title" tabIndex={-1}>The Outliers</h1>
        <p>{error}</p>
        <button className={styles.actionButton} type="button" onClick={() => setAttempt((value) => value + 1)}>Try again</button>
      </div>
    )
  }

  if (!overview) {
    return (
      <div className={styles.loadState} role="status">
        <p className={styles.eyebrow}>The Outliers · saved model diagnostics</p>
        <h1 className={styles.title} id="page-title" tabIndex={-1}>The Outliers</h1>
        <p>Loading precomputed observations and cluster references…</p>
      </div>
    )
  }

  const distribution = overview.distributions.centroid_distance_percentile

  return (
    <article className={styles.page} aria-labelledby="page-title">
      <header className={styles.intro}>
        <p className={styles.eyebrow}><span className={styles.chapterNumber}>04</span> Frozen K=4 · four-feature representation</p>
        <h1 className={styles.title} id="page-title" tabIndex={-1}>The Outliers</h1>
        <p className={styles.lead}>Which confirmed planets sit far from the patterns we identified, and what makes each observation unusual? Here, “unusual” means relative to a selected statistical representation of this catalogue. It does not establish physical uniqueness or an incorrect measurement.</p>
        <nav className={styles.relatedLinks} aria-label="Related atlas chapters">
          <Link to="/patterns">Review the four cluster profiles</Link>
          {selected?.record.pl_name && <Link to={`/explorer?planet=${encodeURIComponent(selected.record.pl_name)}`}>Open the selected planet in The Explorer</Link>}
        </nav>
      </header>

      <section className={styles.overview} aria-labelledby="overview-title">
        <div className={styles.overviewHeading}>
          <div>
            <p className={styles.sectionEyebrow}>01 · The population</p>
            <h2 className={styles.sectionTitle} id="overview-title">Three diagnostics, three questions.</h2>
            <p className={styles.sectionLead}>The catalogue remains intact. The frozen model assigns {overview.summary.assigned_records.toLocaleString()} planets; {overview.summary.unassigned_records.toLocaleString()} records have no diagnostics in this four-feature space.</p>
          </div>
          <dl className={styles.summaryStats}>
            <div><dt>Assigned observations</dt><dd>{overview.summary.assigned_records.toLocaleString()}</dd></div>
            <div><dt>In current review range</dt><dd>{pagination?.total_records.toLocaleString() ?? '—'}</dd></div>
            <div><dt>Negative saved silhouettes</dt><dd>{overview.summary.negative_silhouette_records.toLocaleString()}</dd></div>
          </dl>
        </div>

        <div className={styles.distributionLayout}>
          <figure className={styles.chartCard}>
            <figcaption>
              <span className={styles.panelKicker}>Distance within assigned cluster</span>
              <p>Percentile distribution · {overview.summary.assigned_records.toLocaleString()} assigned planets</p>
            </figcaption>
            <PercentileChart distribution={distribution} threshold={minimumPercentile} selectedPercentile={selectedPercentile} />
            <p className={styles.chartNote}>A planet’s distance is measured in the saved standardized feature space. Percentiles are ranked against members of that planet’s assigned cluster.</p>
          </figure>
          <aside className={styles.diagnosticGuide} aria-label="How to read the diagnostics">
            <div><span className={styles.guideMark} data-kind="distance">01</span><p><strong>Centroid distance</strong><br />How far the observation lies from its assigned group centre.</p></div>
            <div><span className={styles.guideMark} data-kind="measurement">02</span><p><strong>Individual measurements</strong><br />Where each original physical value sits relative to its cluster’s Q1–Q3 range.</p></div>
            <div><span className={styles.guideMark} data-kind="separation">03</span><p><strong>Silhouette</strong><br />How separated the assigned group is from neighboring groups for this observation.</p></div>
            <p className={styles.caveat}>These diagnostics are kept separate. None is a probability, a physical category, or proof of a data error.</p>
          </aside>
        </div>
        <div className={styles.secondaryDistributions}>
          <section className={styles.silhouetteDistribution} aria-labelledby="silhouette-distribution-title">
            <div className={styles.distributionHeading}>
              <div><span className={styles.panelKicker}>Cluster separation</span><h3 id="silhouette-distribution-title">Saved silhouette values</h3></div>
              <span className={styles.negativeCount}>{overview.distributions.silhouette.negative_count.toLocaleString()} below zero</span>
            </div>
            <div className={styles.silhouetteBins}>
              {Object.entries(overview.distributions.silhouette.histogram).map(([label, count]) => {
                const share = overview.summary.assigned_records ? count / overview.summary.assigned_records * 100 : 0
                return <div className={styles.silhouetteBin} key={label}>
                  <div className={styles.binLabel}><span>{label}</span><strong>{count.toLocaleString()}</strong></div>
                  <div className={styles.binTrack}><span data-negative={label.endsWith('to 0')} style={{ width: `${share}%` }} /></div>
                </div>
              })}
            </div>
            <p className={styles.distributionFootnote}>Saved Euclidean silhouette range: {formatValue(overview.distributions.silhouette.minimum, 4)} to {formatValue(overview.distributions.silhouette.maximum, 4)}. Negative values suggest weak separation in this selected feature space.</p>
          </section>
          <section className={styles.featureDistribution} aria-labelledby="feature-distribution-title">
            <div className={styles.distributionHeading}>
              <div><span className={styles.panelKicker}>Individual measurements</span><h3 id="feature-distribution-title">Values outside the middle half</h3></div>
            </div>
            <div className={styles.featureRelationList}>
              {featureDefinitions.map((feature) => {
                const counts = overview.distributions.feature_relations[feature.key]
                const total = overview.summary.assigned_records || 1
                return <div className={styles.featureRelationRow} key={feature.key}>
                  <strong>{feature.label}</strong>
                  <div className={styles.relationTrack} role="img" aria-label={`${feature.label}: ${counts.below_q1.toLocaleString()} below Q1, ${counts.within_q1_q3.toLocaleString()} within Q1 to Q3, ${counts.above_q3.toLocaleString()} above Q3`}>
                    <span data-relation="below" style={{ width: `${counts.below_q1 / total * 100}%` }} />
                    <span data-relation="within" style={{ width: `${counts.within_q1_q3 / total * 100}%` }} />
                    <span data-relation="above" style={{ width: `${counts.above_q3 / total * 100}%` }} />
                  </div>
                  <small>{counts.below_q1.toLocaleString()} below · {counts.within_q1_q3.toLocaleString()} within · {counts.above_q3.toLocaleString()} above</small>
                </div>
              })}
            </div>
            <p className={styles.distributionFootnote}>Each feature is compared with the assigned cluster’s original-unit Q1–Q3 interval. These values overlap across planets and are not combined into one score.</p>
          </section>
        </div>
      </section>

      <section className={styles.exploration} aria-labelledby="exploration-title">
        <div className={styles.explorationHeader}>
          <div>
            <p className={styles.sectionEyebrow}>02 · Investigate observations</p>
            <h2 className={styles.sectionTitle} id="exploration-title">Browse the model-relative tails.</h2>
            <p className={styles.sectionLead}>The list ranks observations by within-cluster distance percentile, or by saved silhouette when inspecting cluster boundaries.</p>
          </div>
          <div className={styles.filters}>
            <label className={styles.thresholdControl}>
              <span>Minimum distance percentile <strong>{minimumPercentile}%</strong></span>
              <input
                aria-label="Minimum distance percentile"
                type="range"
                min="0"
                max="95"
                step="5"
                value={minimumPercentile}
                onChange={(event) => updateListFilter(() => setMinimumPercentile(Number(event.target.value)))}
              />
            </label>
            <label>
              <span>Assigned cluster</span>
              <select aria-label="Filter by cluster" value={clusterFilter} onChange={(event) => updateListFilter(() => setClusterFilter(event.target.value))}>
                <option value="all">All clusters</option>
                {overview.cluster_profiles.map((cluster) => <option key={cluster.cluster_id} value={cluster.cluster_id}>Cluster {cluster.cluster_id}</option>)}
              </select>
            </label>
            <label>
              <span>Rank observations by</span>
              <select aria-label="Rank observations by" value={sortBy} onChange={(event) => updateListFilter(() => setSortBy(event.target.value as typeof sortBy))}>
                <option value="distance_percentile">Distance percentile</option>
                <option value="silhouette">Lowest silhouette</option>
              </select>
            </label>
            <label>
              <span>Planet or host star</span>
              <input aria-label="Search planets or host stars" type="search" value={search} onChange={(event) => updateListFilter(() => setSearch(event.target.value))} placeholder="Search the assigned cohort" />
            </label>
            <label>
              <span>Observations per page</span>
              <select aria-label="Observations per page" value={pageSize} onChange={(event) => updateListFilter(() => setPageSize(Number(event.target.value)))}>
                {[10, 20, 50].map((size) => <option key={size} value={size}>{size} observations</option>)}
              </select>
            </label>
          </div>
        </div>

        {error && <div className={styles.errorNotice} role="alert"><p>{error}</p><button type="button" onClick={() => setAttempt((value) => value + 1)}>Retry</button></div>}
        {loading && <p className={styles.status} role="status">Loading saved outlier diagnostics…</p>}
        {!loading && !error && observations.length === 0 && (
          <div className={styles.emptyState}><h3>No assigned observations match these filters.</h3><p>Lower the percentile range, clear the search, or choose another cluster.</p></div>
        )}

        {!loading && observations.length > 0 && (
          <div className={styles.resultsLayout}>
            <div className={styles.observationColumn}>
              <ol className={styles.observationList} aria-label="Ranked outlier observations">
                {observations.map((observation, index) => {
                  const isSelected = selectedId === observation.pl_name
                  const isCompared = comparison.some((item) => item.pl_name === observation.pl_name)
                  return (
                    <li key={observation.pl_name}>
                      <article className={styles.observationCard} data-selected={isSelected} style={{ '--cluster-color': `var(--cluster-${observation.cluster_id})` } as CSSProperties}>
                        <button className={styles.observationSelect} type="button" aria-pressed={isSelected} onClick={() => setPlanet(observation.pl_name)}>
                          <span className={styles.rankIndex}>{String((page - 1) * pageSize + index + 1).padStart(2, '0')}</span>
                          <span className={styles.observationIdentity}><strong>{observation.pl_name}</strong><small>{observation.hostname} · Cluster {observation.cluster_id}</small></span>
                          <span className={styles.rankMetric}><strong>{formatValue(observation.cluster_distance_percentile, 4)}%</strong><small>within-cluster percentile</small></span>
                        </button>
                        <div className={styles.observationMeta}><span>Distance {formatValue(observation.centroid_distance, 4)}</span><span>Silhouette {formatValue(observation.silhouette_score, 4)}</span></div>
                        <button className={styles.compareToggle} type="button" disabled={!isCompared && comparison.length >= 2} aria-pressed={isCompared} onClick={() => toggleComparison(observation)}>
                          {isCompared ? 'Remove comparison' : 'Compare'}
                        </button>
                      </article>
                    </li>
                  )
                })}
              </ol>
              {pagination && <nav className={styles.pagination} aria-label="Observation pages">
                <button type="button" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button>
                <span>Page {pagination.page} of {pagination.total_pages || 1} · {pagination.total_records.toLocaleString()} matched</span>
                <button type="button" disabled={page >= pagination.total_pages} onClick={() => setPage((value) => value + 1)}>Next</button>
              </nav>}
            </div>

            <aside className={styles.detailColumn} aria-live="polite">
              {detailLoading && <p className={styles.status} role="status">Loading selected planet diagnostics…</p>}
              {detailError && <div className={styles.errorNotice} role="alert"><p>{detailError}</p></div>}
              {!detailLoading && selected && (
                <section className={styles.detailCard} aria-labelledby="planet-detail-title">
                  <header className={styles.detailHeader}>
                    <div><p className={styles.panelKicker}>Selected observation</p><h3 id="planet-detail-title">{selected.record.pl_name}</h3><p className={styles.hostName}>Host star · {selected.record.hostname}</p></div>
                    {selectedCluster && <span className={styles.clusterBadge} style={{ '--cluster-color': `var(--cluster-${selectedCluster.cluster_id})` } as CSSProperties}>Cluster {selectedCluster.cluster_id}</span>}
                  </header>
                  {selected.diagnostics_available ? (
                    <>
                      <div className={styles.diagnosticStats}>
                        <div><span>Centroid distance</span><strong>{formatValue(selected.record.centroid_distance, 5)}</strong><small>Euclidean · standardized feature space</small></div>
                        <div><span>Within-cluster percentile</span><strong>{formatValue(selected.record.cluster_distance_percentile, 4)}%</strong><small>Relative to Cluster {selected.record.cluster_id}</small></div>
                        <div><span>Saved silhouette</span><strong>{formatValue(selected.record.silhouette_score, 5)}</strong><small>{(selected.record.silhouette_score ?? 0) < 0 ? 'Negative: weak separation under this representation' : 'Separation diagnostic; not a physical class'}</small></div>
                      </div>
                      <h4 className={styles.subhead}>Original measurements against cluster quartiles</h4>
                      <div className={styles.featureComparisons}>
                        {selected.feature_comparisons.map((comparisonItem) => (
                          <div className={styles.featureComparison} key={comparisonItem.feature}>
                            <div className={styles.featureHeading}><strong>{comparisonItem.label}</strong><span>{labelRelation(comparisonItem.relation)}</span></div>
                            <p className={styles.physicalValue}>{formatValue(comparisonItem.value)} <small>{comparisonItem.unit}</small></p>
                            {comparisonItem.reference && <p className={styles.quartileRange}>Cluster Q1–Q3: {formatValue(comparisonItem.reference.q1)}–{formatValue(comparisonItem.reference.q3)} {comparisonItem.unit}</p>}
                            {comparisonItem.iqr_from_median !== null
                              ? <p className={styles.deviation}>Median-relative displacement: {formatValue(comparisonItem.iqr_from_median, 4)} cluster IQR</p>
                              : <p className={styles.deviation}>IQR displacement unavailable because the cluster IQR is zero.</p>}
                          </div>
                        ))}
                      </div>
                      <p className={styles.interpretationNote}>An outside-quartile value describes this cluster-relative sample position. It is not an error flag. The three diagnostics above answer separate questions and are not combined.</p>
                    </>
                  ) : (
                    <div className={styles.unassignedNotice}><p>{selected.unavailable_reason}</p><p>Original measurements remain available in the planet dossier.</p></div>
                  )}
                  <Link className={styles.explorerLink} to={`/explorer?planet=${encodeURIComponent(selected.record.pl_name)}`}>Open this planet in The Explorer <span aria-hidden="true">↗</span></Link>
                </section>
              )}
              {!selected && !detailError && !detailLoading && <p className={styles.emptyDetail}>Choose an observation to inspect its measurements and saved cluster context.</p>}
            </aside>
          </div>
        )}
      </section>

      {comparison.length > 0 && <section className={styles.comparisonSection} aria-labelledby="comparison-title">
        <div className={styles.comparisonHeader}><div><p className={styles.sectionEyebrow}>03 · Compare</p><h2 className={styles.sectionTitle} id="comparison-title">Compare selected observations.</h2><p className={styles.sectionLead}>The values remain in their original physical units, with each observation’s frozen cluster context.</p></div><button type="button" onClick={() => setComparison([])}>Clear comparison</button></div>
        <div className={styles.comparisonGrid}>
          {comparison.map((item) => <article className={styles.comparisonCard} key={item.pl_name}>
            <header><div><h3>{item.pl_name}</h3><p>{item.hostname} · {item.cluster_id === null ? 'Unassigned' : `Cluster ${item.cluster_id}`}</p></div><button type="button" aria-label={`Remove ${item.pl_name} from comparison`} onClick={() => toggleComparison(item)}>Remove</button></header>
            <dl>{featureDefinitions.map((feature) => <div key={feature.key}><dt>{feature.label}</dt><dd>{formatValue(item[feature.key])} <small>{feature.unit}</small><span>{labelRelation(item[`${feature.key}_relation`])}</span></dd></div>)}
              <div><dt>Within-cluster percentile</dt><dd>{item.cluster_distance_percentile === null ? 'Unavailable' : `${formatValue(item.cluster_distance_percentile, 4)}%`}</dd></div>
              <div><dt>Saved silhouette</dt><dd>{formatValue(item.silhouette_score, 5)}</dd></div>
            </dl>
          </article>)}
        </div>
        {comparison.length < 2 && <p className={styles.comparisonHint}>Select one more observation from the ranked list to compare two records.</p>}
      </section>}

      <section className={styles.methodSection} aria-labelledby="method-title">
        <div><p className={styles.sectionEyebrow}>04 · Method and limits</p><h2 className={styles.sectionTitle} id="method-title">A model-relative view.</h2></div>
        <div className={styles.methodCopy}>
          <p>Centroid distance is calculated in the existing standardized space of log10 radius, log10 orbital period, equilibrium temperature, and eccentricity. Distance percentiles are ranked separately within each assigned cluster. The range control filters observations for review; the project does not define a universal distance cutoff.</p>
          <p>Measurement comparisons use each cluster’s saved physical-unit median, Q1, Q3, and IQR. The IQR displacement is (measurement − cluster median) / cluster IQR and is unavailable when the IQR is zero. Silhouette values are reused from the saved validation output.</p>
          <ul>{overview.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
          <p>Confirmed-planet catalogues reflect discovery and observational biases. These measurements alone do not support claims about habitability, atmospheres, composition, or physical mechanisms.</p>
        </div>
      </section>
    </article>
  )
}
