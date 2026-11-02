import { describe, expect, it } from 'vitest'
import { getPlottablePlanets, getPlanetAxisStatus } from './features'
import type { PlanetRecord } from './types'

const featureFixture = (values: Partial<PlanetRecord> = {}): PlanetRecord => ({
  pl_name: 'Fixture Planet',
  hostname: 'Fixture Star',
  pl_rade: 1.2,
  pl_orbper: 20,
  pl_eqt: 450,
  pl_orbeccen: 0,
  cluster_id: 0,
  assignment_status: 'assigned',
  discoverymethod: 'Transit',
  disc_year: 2020,
  ...values,
})

describe('feature-space value eligibility', () => {
  it('requires positive finite values for log-scaled radius and period', () => {
    const planets = [
      featureFixture({ pl_name: 'positive', pl_rade: 1, pl_orbper: 4 }),
      featureFixture({ pl_name: 'zero-period', pl_orbper: 0 }),
      featureFixture({ pl_name: 'negative-radius', pl_rade: -1 }),
      featureFixture({ pl_name: 'infinite-period', pl_orbper: Number.POSITIVE_INFINITY }),
    ]

    expect(getPlottablePlanets(planets, 'pl_orbper', 'pl_rade').map(({ planet }) => planet.pl_name)).toEqual([
      'positive',
    ])
    expect(getPlanetAxisStatus(planets[1], 'pl_orbper', 'pl_rade')).toBe('outside-log-domain')
  })

  it('preserves a zero eccentricity on a linear axis', () => {
    const zeroEccentricity = featureFixture({ pl_name: 'circular-orbit', pl_orbeccen: 0 })
    const [point] = getPlottablePlanets([zeroEccentricity], 'pl_orbeccen', 'pl_rade')

    expect(point?.x).toBe(0)
    expect(point?.planet.pl_orbeccen).toBe(0)
  })

  it('does not turn a missing measurement into zero', () => {
    const missing = featureFixture({ pl_name: 'measurement-missing', pl_rade: null })

    expect(getPlottablePlanets([missing], 'pl_orbper', 'pl_rade')).toHaveLength(0)
    expect(getPlanetAxisStatus(missing, 'pl_orbper', 'pl_rade')).toBe('missing')
  })
})
