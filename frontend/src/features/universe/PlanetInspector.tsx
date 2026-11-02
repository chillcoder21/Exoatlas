import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Link } from 'react-router-dom'
import { formatMeasurement, getFeature, getPlanetAxisStatus } from './features'
import type { FeatureKey, PlanetRecord } from './types'
import styles from './PlanetInspector.module.css'

type PlanetInspectorProps = {
  planet: PlanetRecord | null
  xKey: FeatureKey
  yKey: FeatureKey
  hiddenByPopulationControls: boolean
  onClear: () => void
}

export function PlanetInspector({
  planet,
  xKey,
  yKey,
  hiddenByPopulationControls,
  onClear,
}: PlanetInspectorProps) {
  const reducedMotion = useReducedMotion()
  const transition = { duration: reducedMotion ? 0 : 0.22, ease: 'easeOut' as const }

  return (
    <AnimatePresence mode="wait" initial={false}>
      {planet ? (
        <motion.aside
          animate={{ opacity: 1, y: 0 }}
          aria-labelledby="planet-record-title"
          className={styles.inspector}
          exit={{ opacity: 0, y: reducedMotion ? 0 : 5 }}
          initial={{ opacity: 0, y: reducedMotion ? 0 : 8 }}
          key={planet.pl_name}
          transition={transition}
        >
          <div className={styles.inspectorHeader}>
            <div>
              <p className={styles.eyebrow}>Selected catalogue record</p>
              <h2 className={styles.title} id="planet-record-title">
                {planet.pl_name}
              </h2>
              <p className={styles.host}>{planet.hostname ?? 'Host star not available'}</p>
            </div>
            <button className={styles.clearButton} onClick={onClear} type="button">
              Clear selection
            </button>
          </div>

          <p className={planet.cluster_id === null ? styles.unassigned : styles.clusterStatus}>
            {planet.cluster_id === null
              ? 'Unassigned · confirmed planet'
              : `Exploratory K=4 · cluster ${planet.cluster_id}`}
          </p>
          <p className={styles.modelNote}>
            Cluster IDs describe the saved exploratory grouping; they are not astronomical classes.
          </p>
          <Link className={styles.explorerLink} to={`/explorer?planet=${encodeURIComponent(planet.pl_name)}`}>
            Open scientific dossier <span aria-hidden="true">↗</span>
          </Link>

          <dl className={styles.measurements}>
            <Measurement
              label={getFeature('pl_rade').label}
              value={formatMeasurement(planet.pl_rade, 'pl_rade')}
              unit="Earth radii"
            />
            <Measurement
              label={getFeature('pl_orbper').label}
              value={formatMeasurement(planet.pl_orbper, 'pl_orbper')}
              unit="days"
            />
            <Measurement
              label={getFeature('pl_eqt').label}
              value={formatMeasurement(planet.pl_eqt, 'pl_eqt')}
              unit="K"
            />
            <Measurement
              label={getFeature('pl_orbeccen').label}
              value={formatMeasurement(planet.pl_orbeccen, 'pl_orbeccen')}
              unit="unitless"
            />
            <Measurement label="Discovery method" value={planet.discoverymethod ?? 'Not available'} />
            <Measurement
              label="Discovery year"
              value={planet.disc_year === null ? 'Not available' : String(planet.disc_year)}
            />
          </dl>

          {hiddenByPopulationControls ? (
            <p className={styles.visibilityNote} role="status">
              This planet is hidden on the map by the current population visibility controls.
            </p>
          ) : (
            <AxisStatus planet={planet} xKey={xKey} yKey={yKey} />
          )}
        </motion.aside>
      ) : (
        <motion.aside
          animate={{ opacity: 1, y: 0 }}
          aria-label="Planet inspection"
          className={`${styles.inspector} ${styles.emptyInspector}`}
          exit={{ opacity: 0 }}
          initial={{ opacity: 0, y: reducedMotion ? 0 : 5 }}
          key="empty"
          transition={transition}
        >
          <p className={styles.eyebrow}>Inspect a record</p>
          <h2 className={styles.emptyTitle}>A planet, in its measurements</h2>
          <p className={styles.emptyCopy}>
            Select a plotted point or search by planet or host name to review the available archive
            values.
          </p>
          <p className={styles.emptyCopy}>
            Confirmed planets with incomplete measurements remain part of the population and can
            still be found through search.
          </p>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}

function Measurement({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className={styles.measurement}>
      <dt>{label}</dt>
      <dd>
        {value}
        {unit && <span className={styles.unit}> {unit}</span>}
      </dd>
    </div>
  )
}

function AxisStatus({ planet, xKey, yKey }: { planet: PlanetRecord; xKey: FeatureKey; yKey: FeatureKey }) {
  const status = getPlanetAxisStatus(planet, xKey, yKey)
  if (status === 'plotted') {
    return <p className={styles.visibilityNote}>This record has valid values on both selected axes.</p>
  }
  if (status === 'missing') {
    return (
      <p className={styles.visibilityNote}>
        This planet is not plotted because a value for {getFeature(xKey).label.toLowerCase()} or{' '}
        {getFeature(yKey).label.toLowerCase()} is not available.
      </p>
    )
  }
  return (
    <p className={styles.visibilityNote}>
      This planet is not plotted because a selected logarithmic axis requires a positive value. The
      recorded measurement above is preserved as supplied.
    </p>
  )
}
