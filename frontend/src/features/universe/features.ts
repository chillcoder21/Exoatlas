import type { FeatureKey, PlanetRecord } from './types'

export const FEATURE_OPTIONS: Array<{
  key: FeatureKey
  label: string
  unit: string
  scale: 'logarithmic' | 'linear'
}> = [
  { key: 'pl_rade', label: 'Planetary radius', unit: 'Earth radii', scale: 'logarithmic' },
  { key: 'pl_orbper', label: 'Orbital period', unit: 'days', scale: 'logarithmic' },
  { key: 'pl_eqt', label: 'Equilibrium temperature', unit: 'K', scale: 'linear' },
  { key: 'pl_orbeccen', label: 'Orbital eccentricity', unit: 'unitless', scale: 'linear' },
]

export function getFeature(key: FeatureKey) {
  return FEATURE_OPTIONS.find((feature) => feature.key === key)!
}

export function numericValue(record: PlanetRecord, key: FeatureKey): number | null {
  const value = record[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function isAxisEligible(value: number | null, scale: 'linear' | 'logarithmic') {
  return value !== null && (scale === 'linear' || value > 0)
}

export function getPlottablePlanets(
  planets: PlanetRecord[],
  xKey: FeatureKey,
  yKey: FeatureKey,
) {
  const xFeature = getFeature(xKey)
  const yFeature = getFeature(yKey)
  return planets.flatMap((planet) => {
    const x = numericValue(planet, xKey)
    const y = numericValue(planet, yKey)
    return isAxisEligible(x, xFeature.scale) && isAxisEligible(y, yFeature.scale)
      ? [{ planet, x: x!, y: y! }]
      : []
  })
}

export function formatMeasurement(value: number | null, key: FeatureKey) {
  if (value === null || !Number.isFinite(value)) return 'Not available'
  if (value !== 0 && (Math.abs(value) < 0.001 || Math.abs(value) >= 1_000_000)) {
    return value.toExponential(2)
  }
  const maximumSignificantDigits = key === 'pl_orbeccen' ? 4 : 5
  return new Intl.NumberFormat('en-US', { maximumSignificantDigits }).format(value)
}

export function getPlanetAxisStatus(
  planet: PlanetRecord,
  xKey: FeatureKey,
  yKey: FeatureKey,
): 'plotted' | 'missing' | 'outside-log-domain' {
  const xValue = numericValue(planet, xKey)
  const yValue = numericValue(planet, yKey)
  if (xValue === null || yValue === null) return 'missing'
  if (
    !isAxisEligible(xValue, getFeature(xKey).scale) ||
    !isAxisEligible(yValue, getFeature(yKey).scale)
  ) {
    return 'outside-log-domain'
  }
  return 'plotted'
}
