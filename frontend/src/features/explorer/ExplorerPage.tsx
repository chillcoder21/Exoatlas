import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import type { CSSProperties } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { ClusterProfile, FeatureKey } from '../patterns/types'
import type { DossierRecord, SimilarPlanet, SimilarityResponse } from './types'
import styles from './ExplorerPage.module.css'

type SearchRecord = Pick<DossierRecord, 'pl_name' | 'hostname' | 'cluster_id'>
type SuggestionResponse = { records: SearchRecord[]; pagination: { total_records: number } }
type DetailResponse = { record: DossierRecord }
type ClusterResponse = { clusters: ClusterProfile[] }
type LoadState = 'loading' | 'ready' | 'error'

const FEATURE_META: Array<{ key: FeatureKey; label: string; unit: string }> = [
  { key: 'pl_rade', label: 'Planetary radius', unit: 'Earth radii' },
  { key: 'pl_orbper', label: 'Orbital period', unit: 'days' },
  { key: 'pl_eqt', label: 'Equilibrium temperature', unit: 'K' },
  { key: 'pl_orbeccen', label: 'Orbital eccentricity', unit: 'unitless' },
]

async function fetchJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal, headers: { Accept: 'application/json' } })
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const message = typeof payload === 'object' && payload !== null && 'error' in payload
      ? String((payload as { error?: { message?: unknown } }).error?.message ?? response.statusText)
      : response.statusText
    throw new Error(message || `HTTP ${response.status}`)
  }
  return payload as T
}

function validateSimilarity(payload: SimilarityResponse, planetId: string) {
  if (
    !payload ||
    payload.planet_id !== planetId ||
    typeof payload.eligibility?.eligible !== 'boolean' ||
    payload.method?.features?.join('|') !== 'log10(pl_rade)|log10(pl_orbper)|pl_eqt|pl_orbeccen' ||
    !payload.method?.scaling ||
    !Number.isInteger(payload.candidate_pool_size) ||
    payload.candidate_pool_size < 0 ||
    !Number.isInteger(payload.neighbor_count) ||
    !Array.isArray(payload.neighbors) ||
    payload.neighbor_count !== payload.neighbors.length ||
    payload.neighbor_count > 20 ||
    payload.neighbor_count > payload.candidate_pool_size
  ) {
    throw new Error('The similarity service returned an inconsistent result for this planet.')
  }
  const names = new Set<string>()
  let previousDistance = -Infinity
  for (const neighbor of payload.neighbors) {
    if (
      !neighbor.pl_name ||
      neighbor.pl_name === planetId ||
      names.has(neighbor.pl_name) ||
      !Number.isFinite(neighbor.similarity_distance) ||
      neighbor.similarity_distance < previousDistance
    ) {
      throw new Error('The similarity service returned invalid or unsorted neighbors.')
    }
    names.add(neighbor.pl_name)
    previousDistance = neighbor.similarity_distance
  }
  if (!payload.eligibility.eligible && payload.neighbors.length > 0) {
    throw new Error('The similarity service returned neighbors for an ineligible record.')
  }
  return payload
}

function display(value: unknown, maximum = 5): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return new Intl.NumberFormat('en', { maximumSignificantDigits: maximum }).format(value)
  }
  if (typeof value === 'string' && value.trim()) return value
  return 'Not available'
}

function clusterColor(clusterId: number) {
  return `var(--cluster-${clusterId})`
}

export function ExplorerPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState(() => searchParams.get('planet') ?? '')
  const [suggestions, setSuggestions] = useState<SearchRecord[]>([])
  const [suggestionCount, setSuggestionCount] = useState(0)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [clusters, setClusters] = useState<ClusterProfile[]>([])
  const [selected, setSelected] = useState<DossierRecord | null>(null)
  const [similarity, setSimilarity] = useState<SimilarityResponse | null>(null)
  const [comparing, setComparing] = useState<SimilarPlanet | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const reducedMotion = useReducedMotion()
  const selectedId = searchParams.get('planet')

  useEffect(() => {
    setQuery(selectedId ?? '')
  }, [selectedId])

  useEffect(() => {
    const controller = new AbortController()
    fetchJson<ClusterResponse>('/api/clusters', controller.signal)
      .then((payload) => setClusters(payload.clusters))
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Cluster profiles could not be loaded.')
      })
    return () => controller.abort()
  }, [attempt])

  useEffect(() => {
    const text = query.trim()
    if (!text || text === selectedId) {
      setSuggestions([])
      setSuggestionCount(0)
      setSearchError(null)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setSearchLoading(true)
      setSearchError(null)
      fetchJson<SuggestionResponse>(`/api/planets?search=${encodeURIComponent(text)}&page_size=8`, controller.signal)
        .then((payload) => {
          setSuggestions(payload.records)
          setSuggestionCount(payload.pagination.total_records)
        })
        .catch((cause: unknown) => {
          if (!controller.signal.aborted) setSearchError(cause instanceof Error ? cause.message : 'Planet search failed.')
        })
        .finally(() => { if (!controller.signal.aborted) setSearchLoading(false) })
    }, 180)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query, selectedId])

  useEffect(() => {
    if (!selectedId) {
      setSelected(null)
      setSimilarity(null)
      setComparing(null)
      setLoadState('ready')
      setError(null)
      return
    }
    const controller = new AbortController()
    setLoadState('loading')
    setError(null)
    setComparing(null)
    Promise.all([
      fetchJson<DetailResponse>(`/api/planets/${encodeURIComponent(selectedId)}`, controller.signal),
      fetchJson<SimilarityResponse>(`/api/planets/${encodeURIComponent(selectedId)}/similar`, controller.signal),
    ])
      .then(([detail, similarityResult]) => {
        if (detail.record?.pl_name !== selectedId) {
          throw new Error('The planet service returned a different catalogue record than requested.')
        }
        setSelected(detail.record)
        setSimilarity(validateSimilarity(similarityResult, selectedId))
        setLoadState('ready')
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : 'Planet dossier could not be loaded.')
        setLoadState('error')
      })
    return () => controller.abort()
  }, [selectedId, attempt])

  const selectedCluster = useMemo(
    () => selected?.cluster_id === null || selected?.cluster_id === undefined
      ? null
      : clusters.find((item) => item.cluster_id === selected.cluster_id) ?? null,
    [selected, clusters],
  )

  function choosePlanet(planetId: string) {
    setQuery(planetId)
    setSearchParams({ planet: planetId })
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (suggestions[0]) choosePlanet(suggestions[0].pl_name)
    else if (query.trim()) setSearchError('Choose a confirmed planet from the search suggestions.')
  }

  function handleSearchKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') setSuggestions([])
    if (event.key === 'Enter' && suggestions[0]) {
      event.preventDefault()
      choosePlanet(suggestions[0].pl_name)
    }
  }

  function clearSelection() {
    setQuery('')
    setSearchParams({}, { replace: true })
  }

  return (
    <motion.article
      animate={{ opacity: 1, y: 0 }}
      className={styles.page}
      initial={reducedMotion ? false : { opacity: 0, y: 7 }}
      transition={{ duration: reducedMotion ? 0 : 0.24, ease: 'easeOut' }}
      aria-labelledby="page-title"
    >
      <header className={styles.intro}>
        <p className={styles.eyebrow}><span className={styles.chapterNumber}>03</span> Confirmed worlds · individual records</p>
        <h1 className={styles.title} id="page-title" tabIndex={-1}>The Explorer</h1>
        <p className={styles.lead}>Open a confirmed planet’s scientific dossier, review its catalogue measurements and saved group context, then find the closest measured neighbors in the frozen four-feature space.</p>
        <nav className={styles.relatedLinks} aria-label="Related atlas chapters">
          <Link to={selected ? `/universe?planet=${encodeURIComponent(selected.pl_name)}` : '/universe'}>View in The Universe</Link>
          <Link to="/patterns">Read The Patterns</Link>
        </nav>
      </header>

      <section className={styles.searchPanel} aria-labelledby="search-title">
        <div>
          <p className={styles.sectionEyebrow}>Catalogue lookup</p>
          <h2 className={styles.sectionTitle} id="search-title">Find a confirmed planet</h2>
          <p className={styles.helpText}>Search by planet or host name. Suggestions come from the prepared NASA catalogue.</p>
        </div>
        <form onSubmit={submitSearch} role="search" className={styles.searchForm}>
          <label htmlFor="explorer-search">Planet or host name</label>
          <div className={styles.inputRow}>
            <input
              id="explorer-search"
              type="search"
              autoComplete="off"
              value={query}
              placeholder="e.g. 11 Com b or Kepler-22"
              aria-describedby="explorer-search-help"
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={handleSearchKey}
            />
            <button type="submit">Open dossier</button>
          </div>
          <span className={styles.srOnly} id="explorer-search-help">Type a planet or host name, then choose a result below. Press Enter to open the first match.</span>
          {searchLoading && <p className={styles.searchStatus} role="status">Searching catalogue…</p>}
          {searchError && <p className={styles.inlineError} role="alert">{searchError}</p>}
          {suggestions.length > 0 && (
            <ul className={styles.suggestions} id="explorer-suggestions" aria-label="Planet suggestions">
              {suggestions.map((item) => (
                <li key={item.pl_name}>
                  <button type="button" onClick={() => choosePlanet(item.pl_name)}>
                    <span><strong>{item.pl_name}</strong><small>{item.hostname ?? 'Host star not available'}</small></span>
                    <span className={styles.suggestionState}>{item.cluster_id === null ? 'Unassigned' : `Cluster ${item.cluster_id}`}</span>
                  </button>
                </li>
              ))}
              {suggestionCount > suggestions.length && <li className={styles.moreResults}>Showing {suggestions.length} of {suggestionCount.toLocaleString()} matches</li>}
            </ul>
          )}
          {suggestions.length > 0 && <p className={styles.srOnly} role="status">{suggestionCount.toLocaleString()} matching confirmed planet records. Showing {suggestions.length} suggestions.</p>}
          {query.trim() && query.trim() !== selectedId && !searchLoading && !searchError && suggestions.length === 0 && (
            <p className={styles.searchStatus} role="status">No confirmed planets match “{query.trim()}”.</p>
          )}
          {error && !selectedId && <p className={styles.inlineError} role="alert">{error}</p>}
        </form>
      </section>

      {loadState === 'loading' && selectedId && <p className={styles.notice} role="status" aria-busy="true">Loading the saved planet record and similarity results…</p>}
      {loadState === 'error' && <div className={styles.errorNotice} role="alert"><p>The dossier is unavailable.</p><p>{error}</p><button type="button" onClick={() => setAttempt((current) => current + 1)}>Retry</button></div>}
      {loadState === 'ready' && !selected && <section className={styles.emptyState} aria-label="No planet selected"><p className={styles.sectionEyebrow}>Start with a name</p><h2>A record, in context</h2><p>Choose one of the catalogue suggestions to see original measurements, group ranges and nearest eligible neighbors.</p></section>}

      {selected && loadState === 'ready' && (
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            className={styles.dossier}
            key={selected.pl_name}
            initial={reducedMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reducedMotion ? 0 : 0.2 }}
          >
            <section className={styles.recordCard} aria-labelledby="record-title">
              <header className={styles.recordHeader}>
                <div>
                  <p className={styles.sectionEyebrow}>Planet dossier · NASA PSCompPars</p>
                  <h2 className={styles.recordTitle} id="record-title">{selected.pl_name}</h2>
                  <p className={styles.hostLine}>Host star · {display(selected.hostname)}</p>
                </div>
                <button className={styles.clearButton} type="button" onClick={clearSelection}>Clear selection</button>
              </header>

              <div className={styles.statusRow}>
                {selected.cluster_id === null
                  ? <span className={styles.unassignedBadge}>Unassigned · confirmed planet</span>
                  : <span className={styles.clusterBadge} style={{ '--cluster-color': clusterColor(selected.cluster_id) } as CSSProperties}>Exploratory cluster {selected.cluster_id}</span>}
                <span className={styles.assignmentNote}>Saved K=4 assignment; cluster numbers are arbitrary statistical labels.</span>
              </div>

              <div className={styles.recordColumns}>
                <section aria-labelledby="measurements-title">
                  <h3 className={styles.subhead} id="measurements-title">Physical and orbital measurements</h3>
                  <dl className={styles.measurementGrid}>
                    <Measurement label="Mass" value={display(selected.pl_bmasse)} unit="Earth masses" detail={selected.pl_bmassprov ? `Provenance: ${selected.pl_bmassprov}` : undefined} />
                    <Measurement label="Radius" value={display(selected.pl_rade)} unit="Earth radii" />
                    <Measurement label="Equilibrium temperature" value={display(selected.pl_eqt)} unit="K" />
                    <Measurement label="Orbital period" value={display(selected.pl_orbper)} unit="days" />
                    <Measurement label="Eccentricity" value={display(selected.pl_orbeccen)} unit="unitless · zero retained" />
                    <Measurement label="Semi-major axis" value={display(selected.pl_orbsmax)} unit="AU" />
                    <Measurement label="Orbital inclination" value={display(selected.pl_orbincl)} unit="degrees" />
                  </dl>
                  <h3 className={styles.subhead}>Discovery record</h3>
                  <dl className={styles.compactGrid}>
                    <Measurement label="Method" value={display(selected.discoverymethod)} />
                    <Measurement label="Year" value={display(selected.disc_year)} />
                    <Measurement label="Facility" value={display(selected.disc_facility)} />
                  </dl>
                </section>
                <section aria-labelledby="host-title">
                  <h3 className={styles.subhead} id="host-title">Host star and system</h3>
                  <dl className={styles.compactGrid}>
                    <Measurement label="Spectral type" value={display(selected.st_spectype)} />
                    <Measurement label="Effective temperature" value={display(selected.st_teff)} unit="K" />
                    <Measurement label="Stellar radius" value={display(selected.st_rad)} unit="Solar radii" />
                    <Measurement label="Stellar mass" value={display(selected.st_mass)} unit="Solar masses" />
                    <Measurement label="Known stars in system" value={display(selected.sy_snum)} />
                    <Measurement label="Known planets in system" value={display(selected.sy_pnum)} />
                  </dl>
                  <ClusterContext planet={selected} profile={selectedCluster} />
                </section>
              </div>
            </section>

            <section className={styles.similarSection} aria-labelledby="similar-title">
              <div className={styles.similarHeading}>
                <div><p className={styles.sectionEyebrow}>Measured neighbors</p><h2 className={styles.sectionTitle} id="similar-title">Similar worlds</h2></div>
                {similarity?.eligibility.eligible && <p className={styles.poolCount}>Nearest {similarity.neighbor_count} of {similarity.candidate_pool_size.toLocaleString()} candidates</p>}
              </div>
              {!similarity?.eligibility.eligible ? (
                <div className={styles.unavailable} role="status">
                  <h3>Four-feature comparison is unavailable for this record.</h3>
                  <p>{similarity?.eligibility.detail ?? similarity?.eligibility.message ?? 'Eligibility details are unavailable.'}</p>
                  <p>The planet remains in the confirmed catalogue. It is not assigned a neighbor rank when required measurements are incomplete or cannot use the approved transformations.</p>
                </div>
              ) : (
                <>
                  <p className={styles.methodNote}>Ranked by Euclidean distance in the frozen standardized input space: log10 radius, log10 orbital period, raw equilibrium temperature and raw eccentricity. The saved StandardScaler is reused. Distance is a numerical comparison under this representation, not a probability, physical identity or measure of composition or habitability.</p>
                  <ol className={styles.neighborList}>
                    {similarity.neighbors.map((neighbor, index) => (
                      <li className={styles.neighborCard} key={neighbor.pl_name}>
                        <span className={styles.rank}>{String(index + 1).padStart(2, '0')}</span>
                        <div className={styles.neighborIdentity}>
                          <h3>{neighbor.pl_name}</h3>
                          <p>{neighbor.hostname ?? 'Host star not available'} · {neighbor.cluster_id === null ? 'Unassigned' : `cluster ${neighbor.cluster_id}`}</p>
                          <p className={styles.neighborValues}>{FEATURE_META.map(({ key, label }) => `${label}: ${display(neighbor[key])}`).join(' · ')}</p>
                        </div>
                        <div className={styles.distance}><span>Distance</span><strong>{neighbor.similarity_distance.toFixed(4)}</strong></div>
                        <div className={styles.neighborActions}>
                          <button type="button" onClick={() => choosePlanet(neighbor.pl_name)}>Open dossier</button>
                          <button type="button" onClick={() => setComparing(neighbor)} aria-pressed={comparing?.pl_name === neighbor.pl_name}>Compare</button>
                        </div>
                      </li>
                    ))}
                  </ol>
                  <p className={styles.methodFootnote}>{similarity.method.scaling}</p>
                </>
              )}
            </section>

            <AnimatePresence initial={false}>
              {comparing && <Comparison key={comparing.pl_name} current={selected} other={comparing} reducedMotion={Boolean(reducedMotion)} onClose={() => setComparing(null)} />}
            </AnimatePresence>
          </motion.div>
        </AnimatePresence>
      )}

      <footer className={styles.footer}><span>Source: NASA Exoplanet Archive · PSCompPars snapshot</span><span>Original catalogue measurements · frozen primary assignment</span></footer>
    </motion.article>
  )
}

function Measurement({ label, value, unit, detail }: { label: string; value: string; unit?: string; detail?: string }) {
  return <div className={styles.measurement}><dt>{label}</dt><dd>{value}{unit && value !== 'Not available' && <span> {unit}</span>}</dd>{detail && <small>{detail}</small>}</div>
}

function ClusterContext({ planet, profile }: { planet: DossierRecord; profile: ClusterProfile | null }) {
  if (planet.cluster_id === null || !profile) {
    return <div className={styles.clusterContext}><h3 className={styles.subhead}>Saved cluster context</h3><p>This planet has no primary K=4 assignment because it is outside the approved four-feature complete-case cohort. Its original record remains available; no missing values are imputed.</p>{planet.four_feature_eligibility_reason && <p className={styles.reason}>Eligibility note: {planet.four_feature_eligibility_reason}</p>}</div>
  }
  return <div className={styles.clusterContext}><h3 className={styles.subhead}>Cluster {profile.cluster_id} reference ranges</h3><p>Reference values for {profile.planet_count.toLocaleString()} assigned planets. This group summary does not predict an individual planet’s nature.</p><dl className={styles.rangeList}>{FEATURE_META.map(({ key, label }) => {
    const stats = profile.physical_features[key]
    const value = planet[key]
    const relation = typeof value !== 'number' || !Number.isFinite(value) ? 'Not available'
      : value < stats.q1 ? 'Below Q1' : value > stats.q3 ? 'Above Q3' : 'Within Q1–Q3'
    return <div key={key}><dt>{label}</dt><dd>{relation}</dd><small>Q1 {display(stats.q1)} · median {display(stats.median)} · Q3 {display(stats.q3)} {stats.unit}</small></div>
  })}</dl></div>
}

function Comparison({ current, other, reducedMotion, onClose }: { current: DossierRecord; other: SimilarPlanet; reducedMotion: boolean; onClose: () => void }) {
  return <motion.section className={styles.comparison} aria-labelledby="comparison-title" aria-live="polite" initial={reducedMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: reducedMotion ? 0 : 0.18 }}>
    <header className={styles.comparisonHeader}><div><p className={styles.sectionEyebrow}>Side by side · catalogue values</p><h2 className={styles.sectionTitle} id="comparison-title">{current.pl_name} and {other.pl_name}</h2></div><button type="button" onClick={onClose}>Close comparison</button></header>
    <div className={styles.comparisonScroller}><table><thead><tr><th scope="col">Measurement</th><th scope="col">{current.pl_name}</th><th scope="col">{other.pl_name}</th></tr></thead><tbody>{[...FEATURE_META.map((feature) => ({ ...feature, unit: feature.unit })), { key: 'cluster_id' as const, label: 'Saved exploratory cluster', unit: '' }].map((item) => {
      const a = item.key === 'cluster_id' ? current.cluster_id === null ? 'Unassigned' : `Cluster ${current.cluster_id}` : `${display(current[item.key])}${item.unit ? ` ${item.unit}` : ''}`
      const b = item.key === 'cluster_id' ? other.cluster_id === null ? 'Unassigned' : `Cluster ${other.cluster_id}` : `${display(other[item.key])}${item.unit ? ` ${item.unit}` : ''}`
      return <tr key={item.key}><th scope="row">{item.label}</th><td>{a}</td><td>{b}</td></tr>
    })}</tbody></table></div>
    <p className={styles.methodFootnote}>Physical values above are original catalogue measurements. The neighbor distance uses transformed and standardized values.</p>
  </motion.section>
}
