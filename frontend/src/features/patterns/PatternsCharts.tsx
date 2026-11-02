import { format, scaleLinear, scaleLog } from 'd3'
import type { ClusterProfile, FeatureKey, ValidationSummary } from './types'
import styles from './PatternsPage.module.css'

const featureLabels: Record<FeatureKey, string> = {
  pl_rade: 'Planetary radius',
  pl_orbper: 'Orbital period',
  pl_eqt: 'Equilibrium temperature',
  pl_orbeccen: 'Orbital eccentricity',
}

const compactNumber = format('~g')

export function ClusterPopulationChart({ clusters }: { clusters: ClusterProfile[] }) {
  const width = 760
  const height = 228
  const margin = { top: 8, right: 94, bottom: 25, left: 36 }
  const x = scaleLinear()
    .domain([0, Math.max(...clusters.map((cluster) => cluster.percent_of_eligible_cohort)) * 1.08])
    .range([margin.left, width - margin.right])
  const rowHeight = 40
  const ticks = x.ticks(4)

  return (
    <svg className={styles.chart} viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="population-title population-description">
      <title id="population-title">Relative sizes of the four exploratory populations</title>
      <desc id="population-description">Horizontal bars show each cluster's share of the 5,273-planet assigned cohort and its count.</desc>
      {ticks.map((tick) => (
        <g key={tick} transform={`translate(${x(tick)},0)`}>
          <line x1="0" x2="0" y1={margin.top} y2={height - margin.bottom} className={styles.gridLine} />
          <text y={height - 6} textAnchor="middle" className={styles.axisText}>{`${tick}%`}</text>
        </g>
      ))}
      {clusters.map((cluster, index) => {
        const y = margin.top + 14 + index * rowHeight
        return (
          <g key={cluster.cluster_id}>
            <text x={margin.left - 10} y={y + 12} textAnchor="end" className={styles.rowLabel}>C{cluster.cluster_id}</text>
            <rect x={margin.left} y={y} width={Math.max(1, x(cluster.percent_of_eligible_cohort) - margin.left)} height="20" fill={`var(--cluster-${cluster.cluster_id})`} />
            <text x={width - margin.right + 10} y={y + 14} className={styles.barLabel}>
              {`${cluster.planet_count.toLocaleString()} · ${cluster.percent_of_eligible_cohort.toFixed(2)}%`}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export function FeatureQuartileChart({
  feature,
  clusters,
  selectedClusterIds,
}: {
  feature: FeatureKey
  clusters: ClusterProfile[]
  selectedClusterIds: number[]
}) {
  const width = 430
  const height = 230
  const margin = { top: 22, right: 30, bottom: 35, left: 40 }
  const values = clusters.map((cluster) => cluster.physical_features[feature])
  const minValue = Math.min(...values.map((value) => value.q1))
  const maxValue = Math.max(...values.map((value) => value.q3))
  const isLog = feature === 'pl_orbper'
  const domainMin = isLog ? Math.max(Number.MIN_VALUE, minValue * 0.7) : Math.min(0, minValue)
  const domainMax = maxValue > domainMin ? maxValue * (isLog ? 1.2 : 1.08) : domainMin + 1
  const x = isLog
    ? scaleLog().domain([domainMin, domainMax]).range([margin.left, width - margin.right])
    : scaleLinear().domain([domainMin, domainMax]).range([margin.left, width - margin.right])
  const ticks = x.ticks(5)
  const rowHeight = 36

  return (
    <figure className={styles.featureChart}>
      <figcaption>
        <span className={styles.featureName}>{featureLabels[feature]}</span>
        <span className={styles.featureUnit}>{values[0].unit}{isLog ? ' · logarithmic axis' : ''}</span>
      </figcaption>
      <svg className={styles.chart} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${featureLabels[feature]} quartile ranges by cluster. Bars show first to third quartiles, with a vertical median marker. The period axis is logarithmic.`}>
        {ticks.map((tick) => (
          <g key={tick} transform={`translate(${x(tick)},0)`}>
            <line x1="0" x2="0" y1={margin.top - 6} y2={height - margin.bottom + 1} className={styles.gridLine} />
            <text y={height - 9} textAnchor="middle" className={styles.axisText}>{compactNumber(tick)}</text>
          </g>
        ))}
        {clusters.map((cluster, index) => {
          const stats = cluster.physical_features[feature]
          const y = margin.top + 10 + index * rowHeight
          const isSelected = selectedClusterIds.length === 0 || selectedClusterIds.includes(cluster.cluster_id)
          const opacity = isSelected ? 1 : 0.2
          return (
            <g key={cluster.cluster_id} opacity={opacity}>
              <text x={margin.left - 10} y={y + 4} textAnchor="end" className={styles.rowLabel}>C{cluster.cluster_id}</text>
              <line x1={x(stats.q1)} x2={x(stats.q3)} y1={y} y2={y} stroke={`var(--cluster-${cluster.cluster_id})`} strokeWidth="8" strokeLinecap="round" />
              <line x1={x(stats.median)} x2={x(stats.median)} y1={y - 8} y2={y + 8} stroke="var(--color-text)" strokeWidth="2" />
              <text x={width - margin.right + 7} y={y + 4} className={styles.chartCount}>{cluster.planet_count.toLocaleString()}</text>
            </g>
          )
        })}
      </svg>
    </figure>
  )
}

export function SilhouetteByClusterChart({ validation }: { validation: ValidationSummary }) {
  const rows = validation.cluster_silhouette
  const width = 740
  const height = 232
  const margin = { top: 12, right: 128, bottom: 28, left: 38 }
  const maxMean = Math.max(0.5, ...rows.map((row) => row.mean_silhouette))
  const x = scaleLinear().domain([0, maxMean]).range([margin.left, width - margin.right])
  const ticks = x.ticks(4)
  const rowHeight = 40

  return (
    <svg className={styles.chart} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Mean silhouette by cluster, with the number and share of negative silhouette observations shown at right">
      <title>Silhouette summaries by cluster</title>
      <desc>Mean silhouette is a geometric separation diagnostic in the standardized four-feature space. Negative values indicate observations closer to another cluster on average.</desc>
      {ticks.map((tick) => (
        <g key={tick} transform={`translate(${x(tick)},0)`}>
          <line x1="0" x2="0" y1={margin.top} y2={height - margin.bottom} className={styles.gridLine} />
          <text y={height - 7} textAnchor="middle" className={styles.axisText}>{tick.toFixed(1)}</text>
        </g>
      ))}
      {rows.map((row, index) => {
        const y = margin.top + 10 + index * rowHeight
        return (
          <g key={row.cluster_id}>
            <text x={margin.left - 10} y={y + 12} textAnchor="end" className={styles.rowLabel}>C{row.cluster_id}</text>
            <rect x={margin.left} y={y} width={x(row.mean_silhouette) - margin.left} height="20" fill={`var(--cluster-${row.cluster_id})`} />
            <text x={width - margin.right + 9} y={y + 9} className={styles.axisText}>{`mean ${row.mean_silhouette.toFixed(3)}`}</text>
            <text x={width - margin.right + 9} y={y + 23} className={styles.chartCount}>{`${row.negative_silhouette_count} negative · ${row.negative_silhouette_percent.toFixed(2)}%`}</text>
          </g>
        )
      })}
    </svg>
  )
}

export function CentroidDistanceChart({ validation }: { validation: ValidationSummary }) {
  const rows = validation.cluster_separation.centroid_distances
  const width = 620
  const height = 258
  const margin = { top: 8, right: 70, bottom: 24, left: 74 }
  const maxDistance = Math.max(...rows.map((row) => row.distance))
  const x = scaleLinear().domain([0, maxDistance * 1.12]).range([margin.left, width - margin.right])
  const ticks = x.ticks(4)
  const closest = validation.cluster_separation.closest_centroid_pair

  return (
    <svg className={styles.chart} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Pairwise centroid distances between the four clusters, measured in standardized feature space">
      <title>Distances between cluster centroids</title>
      <desc>The C1–C2 pair has the smallest Euclidean centroid distance in the standardized four-feature input space.</desc>
      {ticks.map((tick) => (
        <g key={tick} transform={`translate(${x(tick)},0)`}>
          <line x1="0" x2="0" y1={margin.top} y2={height - margin.bottom} className={styles.gridLine} />
          <text y={height - 5} textAnchor="middle" className={styles.axisText}>{tick.toFixed(1)}</text>
        </g>
      ))}
      {rows.map((row, index) => {
        const y = margin.top + 10 + index * 32
        const isClosest = row.cluster_a === closest.cluster_a && row.cluster_b === closest.cluster_b
        return (
          <g key={`${row.cluster_a}-${row.cluster_b}`}>
            <text x={margin.left - 10} y={y + 12} textAnchor="end" className={styles.rowLabel}>C{row.cluster_a}–C{row.cluster_b}</text>
            <rect x={margin.left} y={y} width={x(row.distance) - margin.left} height="19" fill={isClosest ? 'var(--accent-amber)' : 'var(--color-border-strong)'} />
            <text x={x(row.distance) + 6} y={y + 13} className={styles.chartCount}>{row.distance.toFixed(3)}</text>
          </g>
        )
      })}
    </svg>
  )
}
