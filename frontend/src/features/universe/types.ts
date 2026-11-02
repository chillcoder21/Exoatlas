export type PlanetRecord = {
  pl_name: string
  hostname: string | null
  pl_rade: number | null
  pl_orbper: number | null
  pl_eqt: number | null
  pl_orbeccen: number | null
  cluster_id: number | null
  assignment_status: 'assigned' | 'unassigned'
  discoverymethod: string | null
  disc_year: number | null
  [column: string]: string | number | boolean | null
}

export type FeatureKey = 'pl_rade' | 'pl_orbper' | 'pl_eqt' | 'pl_orbeccen'

export type ClusterProfile = {
  cluster_id: number
  planet_count: number
  [key: string]: unknown
}

export type UniverseOverview = {
  total_confirmed_planets: number
  with_primary_cluster_assignment: number
  without_cluster_assignment: number
  number_of_clusters: number
  version: string
}

export type UniverseData = {
  planets: PlanetRecord[]
  overview: UniverseOverview
  clusters: ClusterProfile[]
}
