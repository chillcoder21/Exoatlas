import type { PlanetRecord } from '../universe/types'
import type { ClusterProfile } from '../patterns/types'

export type DossierRecord = PlanetRecord & {
  pl_bmasse: number | null
  pl_bmassprov: string | null
  pl_orbsmax: number | null
  pl_orbincl: number | null
  disc_facility: string | null
  st_spectype: string | null
  st_teff: number | null
  st_rad: number | null
  st_mass: number | null
  sy_snum: number | null
  sy_pnum: number | null
  four_feature_eligibility_reason: string | null
}

export type SimilarPlanet = DossierRecord & { similarity_distance: number }

export type SimilarityResponse = {
  planet_id: string
  eligibility: {
    eligible: boolean
    message: string
    blockers?: Array<{ feature: string; reason: string }>
    detail?: string
    saved_eligibility_reason?: string | null
  }
  method: {
    name: string
    features: string[]
    scaling: string
    interpretation: string
  }
  candidate_pool_size: number
  neighbor_count: number
  neighbors: SimilarPlanet[]
}

export type ExplorerData = {
  clusters: ClusterProfile[]
}
