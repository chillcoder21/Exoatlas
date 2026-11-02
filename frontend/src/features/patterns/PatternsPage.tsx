import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { CSSProperties } from 'react'
import {
  CentroidDistanceChart,
  ClusterPopulationChart,
  FeatureQuartileChart,
  SilhouetteByClusterChart,
} from './PatternsCharts'
import type { ClusterProfile, FeatureKey, ModelSummary, ValidationSummary } from './types'
import styles from './PatternsPage.module.css'

const features: Array<{ key: FeatureKey; label: string }> = [
  { key: 'pl_rade', label: 'Planetary radius' },
  { key: 'pl_orbper', label: 'Orbital period' },
  { key: 'pl_eqt', label: 'Equilibrium temperature' },
  { key: 'pl_orbeccen', label: 'Orbital eccentricity' },
]

const clusterColor = (id: number) => `var(--cluster-${id})`

async function fetchJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(`The scientific data service returned ${response.status}.`)
  return response.json() as Promise<T>
}

function formatValue(value: number, feature: FeatureKey) {
  if (feature === 'pl_orbeccen') return value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
  if (feature === 'pl_eqt') return Math.round(value).toLocaleString()
  return new Intl.NumberFormat('en', { maximumSignificantDigits: 5 }).format(value)
}

function formatPercent(value: number) {
  return `${value.toFixed(2)}%`
}

export function PatternsPage() {
  const [clusters, setClusters] = useState<ClusterProfile[] | null>(null)
  const [model, setModel] = useState<ModelSummary['model'] | null>(null)
  const [validation, setValidation] = useState<ValidationSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedClusterIds, setSelectedClusterIds] = useState<number[] | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    async function loadData() {
      setLoading(true)
      setError(null)
      try {
        const [clusterResponse, modelResponse, validationResponse] = await Promise.all([
          fetchJson<{ clusters: ClusterProfile[]; cohort_size: number }>('/api/clusters', controller.signal),
          fetchJson<ModelSummary>('/api/model', controller.signal),
          fetchJson<ValidationSummary>('/api/validation/summary', controller.signal),
        ])
        if (clusterResponse.clusters.length !== 4 || modelResponse.model.k !== 4) {
          throw new Error('The saved primary model does not match the expected four-cluster configuration.')
        }
        setClusters(clusterResponse.clusters)
        setModel(modelResponse.model)
        setValidation(validationResponse)
        setSelectedClusterIds(null)
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setError(cause instanceof Error ? cause.message : 'Scientific results could not be loaded.')
      } finally {
        setLoading(false)
      }
    }
    void loadData()
    return () => controller.abort()
  }, [retryCount])

  if (loading && !clusters) {
    return (
      <div className={styles.loadState} role="status">
        <p className={styles.eyebrow}>The Patterns · saved scientific results</p>
        <h1 className={styles.pageTitle} id="page-title" tabIndex={-1}>The Patterns</h1>
        <p>Loading cluster profiles and validation results…</p>
      </div>
    )
  }

  if (error || !clusters || !model || !validation) {
    return (
      <div className={styles.loadState} role="alert">
        <p className={styles.eyebrow}>The Patterns · data unavailable</p>
        <h1 className={styles.pageTitle} id="page-title" tabIndex={-1}>The Patterns</h1>
        <p>{error ?? 'The saved scientific results could not be loaded.'}</p>
        <button className={styles.actionButton} type="button" onClick={() => setRetryCount((count) => count + 1)}>Try again</button>
      </div>
    )
  }

  const selectedProfiles = selectedClusterIds === null
    ? clusters
    : clusters.filter((cluster) => selectedClusterIds.includes(cluster.cluster_id))
  const isAllSelected = selectedClusterIds === null
  const clusterTotal = clusters.length

  function toggleCluster(clusterId: number) {
    setSelectedClusterIds((current) => {
      if (current === null) return [clusterId]
      const next = current.includes(clusterId)
        ? current.filter((id) => id !== clusterId)
        : [...current, clusterId].sort((a, b) => a - b)
      return next.length === 0 || next.length === clusterTotal ? null : next
    })
  }

  function resetClusterSelection() {
    setSelectedClusterIds(null)
  }

  return (
    <article className={styles.page}>
      <header className={styles.intro}>
        <p className={styles.eyebrow}><span className={styles.chapterNumber}>02</span> Statistical groupings · PSCompPars 2026-10-30</p>
        <div className={styles.introCopy}>
          <div>
            <p className={styles.kicker}>The Patterns</p>
            <h1 className={styles.pageTitle} id="page-title" tabIndex={-1}>Four exploratory groups in the confirmed-planet sample.</h1>
          </div>
          <p className={styles.description}>
            K-means groups planets by the measurements supplied to it. Here, we examine what the saved four-feature partition describes, where it overlaps, and how it shifts when equilibrium temperature is left out.
          </p>
        </div>
        <div className={styles.heroMeta} aria-label="Primary model configuration">
          <span><strong>{validation.cohort_size.toLocaleString()}</strong> planets in the complete-case cohort</span>
          <span><strong>K = {model.k}</strong> exploratory groups</span>
          <span><strong>{model.ordered_features.length}</strong> transformed / measured features</span>
        </div>
        <nav className={styles.sectionNav} aria-label="On this page">
          <a href="#populations">Populations</a>
          <a href="#profiles">Profiles</a>
          <a href="#overlap">Overlap</a>
          <a href="#temperature">Temperature experiment</a>
          <a href="#reliability">Reliability & limits</a>
        </nav>
        <p className={styles.explorerPrompt}>Continue to an individual record: <Link to="/explorer">open The Explorer</Link></p>
      </header>

      <section className={styles.chapter} id="populations" aria-labelledby="populations-title">
        <div className={styles.chapterHeading}>
          <p className={styles.sectionEyebrow}>01 · The discovery</p>
          <h2 className={styles.sectionTitle} id="populations-title">Four groups, very different in size.</h2>
          <p className={styles.sectionLead}>The bars show each group’s share of the 5,273 planets assigned by the frozen primary model. Cluster IDs are arbitrary labels.</p>
        </div>
        <div className={styles.populationLayout}>
          <div className={styles.populationChartWrap}>
            <ClusterPopulationChart clusters={clusters} />
            <p className={styles.chartNote}>Planets in the assigned cohort · labels C0–C3 correspond to the existing cluster colours throughout ExoAtlas.</p>
          </div>
          <aside className={styles.populationAside}>
            <span className={styles.asideIndex}>A population, not a taxonomy</span>
            <p>These are statistical partitions of a confirmed-planet catalogue. They are not established astronomical classes, and the algorithm’s numbering does not rank their importance.</p>
          </aside>
        </div>
      </section>

      <section className={`${styles.chapter} ${styles.profileChapter}`} id="profiles" aria-labelledby="profiles-title">
        <div className={styles.chapterHeading}>
          <p className={styles.sectionEyebrow}>02 · The profiles</p>
          <h2 className={styles.sectionTitle} id="profiles-title">Compare the middle half of each group.</h2>
          <p className={styles.sectionLead}>Each bar spans the first to third quartile; its marker is the median. These intervals show variation within a cluster and can reveal overlap that a median alone would hide.</p>
        </div>
        <div className={styles.profileControls}>
          <div>
            <p className={styles.controlTitle}>Highlight clusters</p>
            <div className={styles.clusterToggles} role="group" aria-label="Select clusters to compare">
              {clusters.map((cluster) => {
                const pressed = isAllSelected || selectedClusterIds?.includes(cluster.cluster_id) === true
                return (
                  <button
                    className={styles.clusterToggle}
                    data-selected={pressed}
                    key={cluster.cluster_id}
                    onClick={() => toggleCluster(cluster.cluster_id)}
                    type="button"
                    aria-pressed={pressed}
                    style={{ '--cluster-color': clusterColor(cluster.cluster_id) } as CSSProperties}
                  >
                    <span aria-hidden="true" className={styles.clusterDot} />
                    C{cluster.cluster_id}
                  </button>
                )
              })}
              {!isAllSelected && <button className={styles.resetButton} type="button" onClick={resetClusterSelection}>Show all</button>}
            </div>
          </div>
          <p className={styles.controlHint} aria-live="polite">
            {isAllSelected ? 'All four groups are visible.' : `Highlighting ${selectedProfiles.map((cluster) => `C${cluster.cluster_id}`).join(' and ')} across all four measurements.`}
          </p>
        </div>
        <div className={styles.featureChartGrid}>
          {features.map(({ key }) => (
            <FeatureQuartileChart
              key={key}
              feature={key}
              clusters={clusters}
              selectedClusterIds={selectedClusterIds ?? []}
            />
          ))}
        </div>
        <p className={styles.chartNote}>Values use original physical units. Orbital period is displayed on a logarithmic axis to make its wide range legible. Counts at the right of each row are cluster sample sizes; eccentricity zeros are retained.</p>
        <details className={styles.dataDetails}>
          <summary>Read the profile values</summary>
          <div className={styles.tableScroller}>
            <table className={styles.dataTable}>
              <caption>Primary four-feature model · original physical measurements</caption>
              <thead><tr><th scope="col">Cluster</th><th scope="col">Planets</th>{features.map(({ key, label }) => <th key={key} scope="col">{label}<span>{clusters[0].physical_features[key].unit}</span></th>)}</tr></thead>
              <tbody>{clusters.map((cluster) => <tr key={cluster.cluster_id}>
                <th scope="row"><span className={styles.tableClusterDot} style={{ background: clusterColor(cluster.cluster_id) }} />C{cluster.cluster_id}</th>
                <td>{cluster.planet_count.toLocaleString()}</td>
                {features.map(({ key }) => {
                  const stats = cluster.physical_features[key]
                  return <td key={key}>Median {formatValue(stats.median, key)}<br /><span>Q1 {formatValue(stats.q1, key)} · Q3 {formatValue(stats.q3, key)} · IQR {formatValue(stats.iqr, key)}</span></td>
                })}
              </tr>)}</tbody>
            </table>
          </div>
        </details>
        {selectedProfiles.length === 1 && (
          <p className={styles.profileDescription} aria-live="polite">{selectedProfiles[0].descriptive_summary}</p>
        )}
        <p className={styles.scienceNote}><span className={styles.noteRule} aria-hidden="true" />Quartiles describe the central half of the observed values. They do not describe every planet or show the full tails of each distribution.</p>
      </section>

      <section className={styles.chapter} id="overlap" aria-labelledby="overlap-title">
        <div className={styles.chapterHeading}>
          <p className={styles.sectionEyebrow}>03 · The overlap</p>
          <h2 className={styles.sectionTitle} id="overlap-title">A partition can still have fuzzy edges.</h2>
          <p className={styles.sectionLead}>Silhouette values and centroid distances describe geometry in the standardized input space. They are diagnostics of this partition, not proof of natural boundaries.</p>
        </div>
        <div className={styles.overlapGrid}>
          <div className={styles.chartPanel}>
            <div className={styles.panelHeading}>
              <span className={styles.panelKicker}>Within-cluster pattern</span>
              <h3>Most assignments sit inside their group.</h3>
              <p>Negative silhouette observations are closer, on average, to another group than their assigned group.</p>
            </div>
            <SilhouetteByClusterChart validation={validation} />
            <p className={styles.chartNote}>Bars show mean silhouette per cluster. The right column gives negative counts and share.</p>
          </div>
          <div className={styles.chartPanel}>
            <div className={styles.panelHeading}>
              <span className={styles.panelKicker}>Between-centroid spacing</span>
              <h3>C1 and C2 are the closest centroids.</h3>
              <p>{validation.cluster_separation.centroid_distance_metric}.</p>
            </div>
            <CentroidDistanceChart validation={validation} />
            <p className={styles.chartNote}>Distance is computed in standardized feature space and is not a physical distance.</p>
          </div>
        </div>
        <div className={styles.overlapCallout}>
          <div className={styles.overlapValue}>{validation.cluster_separation.eccentricity_overlap.coefficient.toFixed(3)}</div>
          <div>
            <p className={styles.panelKicker}>C1–C2 eccentricity overlap coefficient</p>
            <p>The one-dimensional binned overlap diagnostic suggests substantial shared eccentricity values for these groups. It is not a multivariate separation test and does not mean the clusters are identical.</p>
            <span className={styles.methodNote}>{validation.cluster_separation.eccentricity_overlap.method}</span>
          </div>
        </div>
      </section>

      <section className={`${styles.chapter} ${styles.temperatureChapter}`} id="temperature" aria-labelledby="temperature-title">
        <div className={styles.chapterHeading}>
          <p className={styles.sectionEyebrow}>04 · The sensitivity experiment</p>
          <h2 className={styles.sectionTitle} id="temperature-title">Remove temperature. The map changes.</h2>
          <p className={styles.sectionLead}>Both K=4 runs use the same 5,273 planets in the same order. The no-temperature experiment changes the feature set, not the population.</p>
        </div>
        <div className={styles.experimentMetrics}>
          <div className={styles.experimentColumn}>
            <p className={styles.panelKicker}>With equilibrium temperature · 4 features</p>
            <div className={styles.metricRow}><span>Silhouette</span><strong>{validation.silhouette.mean.toFixed(4)}</strong></div>
            <div className={styles.metricRow}><span>Seed stability · mean ARI</span><strong>{validation.stability.ari_mean.toFixed(4)}</strong></div>
          </div>
          <div className={styles.experimentColumn}>
            <p className={styles.panelKicker}>Without temperature · 3 features</p>
            <div className={styles.metricRow}><span>Silhouette</span><strong>{validation.feature_configuration_sensitivity.without_temperature.silhouette.toFixed(4)}</strong></div>
            <div className={styles.metricRow}><span>Seed stability · mean ARI</span><strong>{validation.feature_configuration_sensitivity.without_temperature.stability_ari_mean.toFixed(4)}</strong></div>
          </div>
          <div className={styles.changeMetric}>
            <span>Adjusted Rand index between partitions</span>
            <strong>{validation.feature_configuration_sensitivity.adjusted_rand_index.toFixed(4)}</strong>
            <p>{validation.feature_configuration_sensitivity.changed_planet_count.toLocaleString()} planets · {formatPercent(validation.feature_configuration_sensitivity.changed_planet_percent)} changed membership after one-to-one label matching.</p>
          </div>
        </div>
        <p className={styles.interpretationNote}>The higher silhouette in the three-feature run is measured in a different feature space; it does not by itself establish that configuration as scientifically better. The agreement statistic shows sensitivity to feature choice, not a causal effect of temperature.</p>
        <details className={styles.dataDetails}>
          <summary>Inspect the profiles without temperature</summary>
          <p className={styles.detailsIntro}>Cluster labels are assigned independently in each run. These C0–C3 IDs must not be read as direct matches to the with-temperature IDs. Temperature is shown only as physical context in this experiment.</p>
          <div className={styles.tableScroller}>
            <table className={styles.dataTable}>
              <caption>No-temperature K=4 experiment · same planets, three clustering features</caption>
              <thead><tr><th scope="col">Cluster</th><th scope="col">Planets</th>{features.map(({ key, label }) => <th key={key} scope="col">{label}<span>{clusters[0].physical_features[key].unit}</span></th>)}</tr></thead>
              <tbody>{[0, 1, 2, 3].map((clusterId) => {
                const entries = validation.feature_configuration_sensitivity.without_temperature.profiles.filter((profile) => profile.cluster_id === clusterId)
                const count = entries[0]?.planet_count ?? 0
                return <tr key={clusterId}>
                  <th scope="row"><span className={styles.tableClusterDot} style={{ background: clusterColor(clusterId) }} />C{clusterId}</th>
                  <td>{count.toLocaleString()}</td>
                  {features.map(({ key }) => {
                    const stats = entries.find((entry) => entry.feature === key)
                    return <td key={key}>{stats ? <>Median {formatValue(stats.median, key)}<br /><span>Q1 {formatValue(stats.q1, key)} · Q3 {formatValue(stats.q3, key)} · IQR {formatValue(stats.iqr, key)}</span></> : '—'}</td>
                  })}
                </tr>
              })}</tbody>
            </table>
          </div>
        </details>
      </section>

      <section className={styles.chapter} id="reliability" aria-labelledby="reliability-title">
        <div className={styles.chapterHeading}>
          <p className={styles.sectionEyebrow}>05 · Reliability and limits</p>
          <h2 className={styles.sectionTitle} id="reliability-title">Stable to reruns. Sensitive to the question.</h2>
          <p className={styles.sectionLead}>With-temperature K=4 has a mean silhouette of {validation.silhouette.mean.toFixed(4)} and a mean seed stability ARI of {validation.stability.ari_mean.toFixed(4)} across {validation.stability.comparison_seed_count} alternate initializations. {validation.negative_silhouette.count} planets ({formatPercent(validation.negative_silhouette.percent)}) have negative silhouette values.</p>
        </div>
        <div className={styles.conclusionGrid}>
          <div>
            <p className={styles.panelKicker}>What these results support</p>
            <p>The saved measurements and assignments support a descriptive comparison of four reproducible geometric groups under this specific feature set and preprocessing pipeline.</p>
          </div>
          <div>
            <p className={styles.panelKicker}>What they do not establish</p>
            <p>They do not establish four natural planet classes, causal effects, or population boundaries independent of the selected features, catalogue selection, and shared host systems.</p>
          </div>
        </div>
        <ul className={styles.caveatList}>
          {validation.scientific_caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}
        </ul>
        <p className={styles.sourceNote}>Source: NASA Exoplanet Archive PSCompPars snapshot dated 2026-10-30. Results shown here come from the frozen saved assignments and validation artifacts; this experience does not fit or alter a model.</p>
      </section>
    </article>
  )
}
