import { motion, useReducedMotion } from 'motion/react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { useSearchParams } from 'react-router-dom'
import { loadUniverseData } from './api'
import { FeatureSpacePlot } from './FeatureSpacePlot'
import { FEATURE_OPTIONS, getPlottablePlanets } from './features'
import { PlanetInspector } from './PlanetInspector'
import { PlanetSearch } from './PlanetSearch'
import type { FeatureKey, PlanetRecord, UniverseData } from './types'
import styles from './UniversePage.module.css'

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; data: UniverseData }
  | { status: 'error'; message: string }

const NUMBER_FORMAT = new Intl.NumberFormat('en-US')

export function UniversePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [loadState, setLoadState] = useState<LoadState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [xKey, setXKey] = useState<FeatureKey>('pl_orbper')
  const [yKey, setYKey] = useState<FeatureKey>('pl_rade')
  const [search, setSearch] = useState('')
  const [selectedPlanetId, setSelectedPlanetId] = useState<string | null>(() => searchParams.get('planet'))
  const [hiddenClusters, setHiddenClusters] = useState<Set<number>>(() => new Set())
  const [showUnassigned, setShowUnassigned] = useState(true)
  const [zoomResetKey, setZoomResetKey] = useState(0)
  const reducedMotion = useReducedMotion()

  useEffect(() => {
    const controller = new AbortController()
    setLoadState({ status: 'loading' })
    loadUniverseData(controller.signal)
      .then((data) => setLoadState({ status: 'ready', data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setLoadState({
          status: 'error',
          message: error instanceof Error ? error.message : 'The API request failed.',
        })
      })
    return () => controller.abort()
  }, [attempt])

  const handleSelectPlanet = useCallback((planet: PlanetRecord) => {
    setSelectedPlanetId(planet.pl_name)
    setSearch(planet.pl_name)
    setSearchParams({ planet: planet.pl_name })
  }, [setSearchParams])

  const data = loadState.status === 'ready' ? loadState.data : null
  const planetsByName = useMemo(
    () => new Map(data?.planets.map((planet) => [planet.pl_name, planet]) ?? []),
    [data],
  )
  const selectedPlanet = selectedPlanetId ? planetsByName.get(selectedPlanetId) ?? null : null
  useEffect(() => {
    const planetId = searchParams.get('planet')
    if (planetId && planetsByName.has(planetId)) {
      setSelectedPlanetId(planetId)
      setSearch(planetId)
    } else if (!planetId) {
      setSelectedPlanetId(null)
      setSearch('')
    }
  }, [searchParams, planetsByName])
  const points = useMemo(
    () => (data ? getPlottablePlanets(data.planets, xKey, yKey) : []),
    [data, xKey, yKey],
  )
  const visiblePoints = useMemo(
    () =>
      points.filter(({ planet }) =>
        planet.cluster_id === null
          ? showUnassigned
          : !hiddenClusters.has(planet.cluster_id),
      ),
    [points, hiddenClusters, showUnassigned],
  )

  function setClusterVisible(clusterId: number, visible: boolean) {
    setHiddenClusters((current) => {
      const next = new Set(current)
      if (visible) next.delete(clusterId)
      else next.add(clusterId)
      return next
    })
  }

  if (loadState.status === 'loading') {
    return (
      <section className={styles.loadState} aria-labelledby="page-title" aria-busy="true">
        <p className={styles.eyebrow}>NASA Exoplanet Archive · PSCompPars</p>
        <h1 className={styles.pageTitle} id="page-title" tabIndex={-1}>
          The Universe
        </h1>
        <div className={styles.loadingNotice} role="status">
          <span className={styles.loadingMark} aria-hidden="true" />
          <span>Loading and checking the confirmed planet records…</span>
        </div>
      </section>
    )
  }

  if (loadState.status === 'error') {
    return (
      <section className={styles.loadState} aria-labelledby="page-title">
        <p className={styles.eyebrow}>NASA Exoplanet Archive · PSCompPars</p>
        <h1 className={styles.pageTitle} id="page-title" tabIndex={-1}>
          The Universe
        </h1>
        <div className={styles.errorNotice} role="alert">
          <div>
            <p className={styles.noticeTitle}>The scientific dataset could not be loaded.</p>
            <p className={styles.noticeCopy}>
              No partial or sample population is being shown. Start the Flask API, then retry the
              request.
            </p>
            <p className={styles.errorDetail}>{loadState.message}</p>
          </div>
          <button className={styles.retryButton} onClick={() => setAttempt((value) => value + 1)} type="button">
            Retry loading
          </button>
        </div>
      </section>
    )
  }

  const { overview, clusters } = data!
  const notPlottedForAxes = overview.total_confirmed_planets - points.length
  const hiddenByPopulationControls = selectedPlanet
    ? selectedPlanet.cluster_id === null
      ? !showUnassigned
      : hiddenClusters.has(selectedPlanet.cluster_id)
    : false

  return (
    <motion.section
      animate={{ opacity: 1, y: 0 }}
      aria-labelledby="page-title"
      className={styles.page}
      initial={reducedMotion ? false : { opacity: 0, y: 6 }}
      transition={{ duration: reducedMotion ? 0 : 0.24, ease: 'easeOut' }}
    >
      <header className={styles.intro}>
        <p className={styles.eyebrow}>
          <span className={styles.chapterNumber}>01</span>
          Confirmed population · {overview.version}
        </p>
        <div className={styles.introCopy}>
          <h1 className={styles.pageTitle} id="page-title" tabIndex={-1}>
            The Universe
          </h1>
          <p className={styles.description}>
            Explore confirmed planets through the measured properties selected below. Every mark is
            one catalogue record; its coordinates encode only the two chosen measurements.
          </p>
        </div>
      </header>

      <PopulationSummary data={data!} />

      <div className={styles.scientificNote}>
        <span className={styles.noteRule} aria-hidden="true" />
        <p>
          The four K-means groups are exploratory statistical assignments, not established
          astronomical classes. Planets without an assignment remain part of the confirmed
          population.
        </p>
      </div>

      <section className={styles.explorer} aria-labelledby="feature-space-title">
        <div className={styles.explorerHeader}>
          <div>
            <p className={styles.sectionEyebrow}>Measured feature space</p>
            <h2 className={styles.sectionTitle} id="feature-space-title">
              Compare two properties at a time
            </h2>
          </div>
          <p className={styles.chartContext}>
            A feature-space view · not a map of sky position
          </p>
        </div>

        <div className={styles.controls}>
          <PlanetSearch
            planets={data!.planets}
            value={search}
            onChange={setSearch}
            onSelect={handleSelectPlanet}
          />
          <fieldset className={styles.axisControls}>
            <legend className={styles.controlLabel}>Choose plot axes</legend>
            <label className={styles.axisControl}>
              <span>Horizontal</span>
              <select
                aria-label="Horizontal axis"
                value={xKey}
                onChange={(event) => setXKey(event.target.value as FeatureKey)}
              >
                {FEATURE_OPTIONS.map((feature) => (
                  <option disabled={feature.key === yKey} key={feature.key} value={feature.key}>
                    {feature.label} · {feature.scale}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.axisControl}>
              <span>Vertical</span>
              <select
                aria-label="Vertical axis"
                value={yKey}
                onChange={(event) => setYKey(event.target.value as FeatureKey)}
              >
                {FEATURE_OPTIONS.map((feature) => (
                  <option disabled={feature.key === xKey} key={feature.key} value={feature.key}>
                    {feature.label} · {feature.scale}
                  </option>
                ))}
              </select>
            </label>
          </fieldset>
        </div>

        <div className={styles.explorationGrid}>
          <div className={styles.plotColumn}>
            <div className={styles.plotHeading}>
              <div>
                <p className={styles.plotCount} aria-live="polite">
                  {NUMBER_FORMAT.format(visiblePoints.length)} shown
                  <span> of {NUMBER_FORMAT.format(overview.total_confirmed_planets)} confirmed records</span>
                </p>
                <p className={styles.plotSubcount}>
                  {NUMBER_FORMAT.format(notPlottedForAxes)} not plotted: one or both axis values
                  are missing, non-finite, or non-positive on a logarithmic axis
                  {points.length - visiblePoints.length > 0 &&
                    ` · ${NUMBER_FORMAT.format(points.length - visiblePoints.length)} hidden by population controls`}
                </p>
              </div>
              <button
                className={styles.resetZoom}
                onClick={() => setZoomResetKey((value) => value + 1)}
                type="button"
              >
                Reset zoom
              </button>
            </div>

            <FeatureSpacePlot
              hiddenClusters={hiddenClusters}
              onSelectPlanet={handleSelectPlanet}
              planets={data!.planets}
              reducedMotion={Boolean(reducedMotion)}
              resetZoomKey={zoomResetKey}
              selectedPlanetId={selectedPlanetId}
              showUnassigned={showUnassigned}
              xKey={xKey}
              yKey={yKey}
            />

            <fieldset className={styles.legend}>
              <legend className={styles.legendTitle}>Population visibility</legend>
              <div className={styles.legendItems}>
                {clusters.map((cluster) => (
                  <label className={styles.legendItem} key={cluster.cluster_id}>
                    <input
                      checked={!hiddenClusters.has(cluster.cluster_id)}
                      onChange={(event) => setClusterVisible(cluster.cluster_id, event.target.checked)}
                      type="checkbox"
                    />
                    <span
                      aria-hidden="true"
                      className={styles.legendSymbol}
                      data-symbol={cluster.cluster_id}
                      style={{ '--cluster-color': `var(--cluster-${cluster.cluster_id})` } as CSSProperties}
                    />
                    <span>
                      Cluster {cluster.cluster_id}
                      <span className={styles.legendCount}> · {NUMBER_FORMAT.format(cluster.planet_count)}</span>
                    </span>
                  </label>
                ))}
                <label className={styles.legendItem}>
                  <input
                    checked={showUnassigned}
                    onChange={(event) => setShowUnassigned(event.target.checked)}
                    type="checkbox"
                  />
                  <span aria-hidden="true" className={`${styles.legendSymbol} ${styles.unassignedSymbol}`} />
                  <span>
                    Unassigned
                    <span className={styles.legendCount}>
                      {' '}
                      · {NUMBER_FORMAT.format(overview.without_cluster_assignment)}
                    </span>
                  </span>
                </label>
              </div>
              <p className={styles.legendNote}>
                Shape and label distinguish clusters in addition to colour. Hollow marks show
                confirmed planets without a saved cluster assignment.
              </p>
            </fieldset>
          </div>

          <PlanetInspector
            hiddenByPopulationControls={hiddenByPopulationControls}
            onClear={() => {
              setSelectedPlanetId(null)
              setSearch('')
              setSearchParams({}, { replace: true })
            }}
            planet={selectedPlanet}
            xKey={xKey}
            yKey={yKey}
          />
        </div>
      </section>

      <footer className={styles.pageFooter}>
        <span>Source: NASA Exoplanet Archive · Confirmed planets snapshot</span>
        <span>{overview.version} · original catalogue measurements shown</span>
      </footer>
    </motion.section>
  )
}

function PopulationSummary({ data }: { data: UniverseData }) {
  const { overview } = data
  const summaryItems = [
    { label: 'Confirmed planets', value: overview.total_confirmed_planets },
    { label: 'Clustered · exploratory K=4', value: overview.with_primary_cluster_assignment },
    { label: 'Unassigned', value: overview.without_cluster_assignment },
    { label: 'Exploratory groups', value: overview.number_of_clusters },
  ]

  return (
    <dl className={styles.populationSummary} aria-label="Confirmed population counts">
      {summaryItems.map((item) => (
        <div className={styles.summaryItem} key={item.label}>
          <dt>{item.label}</dt>
          <dd>{NUMBER_FORMAT.format(item.value)}</dd>
        </div>
      ))}
    </dl>
  )
}
