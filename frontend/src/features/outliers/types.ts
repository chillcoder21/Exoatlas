export type OutlierSummary = {
  catalogue_records: number
  assigned_records: number
  unassigned_records: number
  negative_silhouette_records: number
}

export type PercentileDistribution = {
  minimum: number
  q1: number
  median: number
  q3: number
  maximum: number
  histogram: Record<string, number>
}

export type SilhouetteDistribution = {
  minimum: number
  median: number
  maximum: number
  negative_count: number
  histogram: Record<string, number>
}

export type OutlierOverview = {
  summary: OutlierSummary
  distributions: {
    centroid_distance_percentile: PercentileDistribution
    silhouette: SilhouetteDistribution
    feature_relations: Record<string, Record<'below_q1' | 'within_q1_q3' | 'above_q3', number>>
  }
  method: Record<string, string | boolean>
  limitations: string[]
  cluster_profiles: ClusterProfile[]
}

export type FeatureReference = {
  unit: string
  median: number
  q1: number
  q3: number
  iqr: number
}

export type ClusterProfile = {
  cluster_id: number
  planet_count: number
  physical_features: Record<string, FeatureReference>
}

export type OutlierObservation = {
  pl_name: string
  hostname: string
  assignment_status: 'assigned' | 'unassigned'
  cluster_id: number | null
  centroid_distance: number | null
  cluster_distance_percentile: number | null
  silhouette_score: number | null
  pl_rade: number | null
  pl_orbper: number | null
  pl_eqt: number | null
  pl_orbeccen: number | null
  pl_rade_relation: string | null
  pl_orbper_relation: string | null
  pl_eqt_relation: string | null
  pl_orbeccen_relation: string | null
}

export type OutlierListResponse = {
  pagination: { page: number; page_size: number; total_records: number; total_pages: number }
  filters: { percentile_min: number; cluster_id: string | null; search: string | null; sort_by: string }
  records: OutlierObservation[]
  ranking_note: string
}

export type FeatureComparison = {
  feature: string
  label: string
  value: number | null
  unit: string | null
  relation: string | null
  iqr_from_median: number | null
  reference: FeatureReference | null
}

export type OutlierDetail = {
  record: OutlierObservation
  diagnostics_available: boolean
  cluster_profile: ClusterProfile | null
  feature_comparisons: FeatureComparison[]
  unavailable_reason: string | null
}
