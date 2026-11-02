export type FeatureKey = 'pl_rade' | 'pl_orbper' | 'pl_eqt' | 'pl_orbeccen'

export type FeatureSummary = {
  unit: string
  median: number
  q1: number
  q3: number
  iqr: number
}

export type ClusterProfile = {
  cluster_id: number
  planet_count: number
  percent_of_eligible_cohort: number
  physical_features: Record<FeatureKey, FeatureSummary>
  descriptive_summary: string
}

export type DistributionSummary = {
  cluster_id: number
  planet_count: number
  planet_percent: number
  feature: FeatureKey
  units: string
  q1: number
  median: number
  q3: number
  iqr: number
}

export type ValidationSummary = {
  model_id: string
  cohort_size: number
  silhouette: { metric: string; mean: number; median: number }
  stability: { metric: string; seed_count: number; comparison_seed_count: number; ari_mean: number; ari_sample_sd: number }
  negative_silhouette: { count: number; percent: number }
  cluster_silhouette: Array<{
    cluster_id: number
    planet_count: number
    mean_silhouette: number
    median_silhouette: number
    negative_silhouette_count: number
    negative_silhouette_percent: number
  }>
  cluster_separation: {
    centroid_distance_metric: string
    centroid_distances: Array<{ cluster_a: number; cluster_b: number; distance: number }>
    closest_centroid_pair: { cluster_a: number; cluster_b: number; distance: number }
    eccentricity_overlap: { cluster_a: number; cluster_b: number; coefficient: number; method: string; units: string }
  }
  feature_configuration_sensitivity: {
    comparison: string
    adjusted_rand_index: number
    changed_planet_count: number
    changed_planet_percent: number
    interpretation: string
    matched_clusters_by_maximum_membership_overlap: Record<string, number>
    without_temperature: {
      features: number
      k: number
      silhouette: number
      stability_ari_mean: number
      profiles: DistributionSummary[]
    }
  }
  scientific_caveats: string[]
}

export type ModelSummary = {
  model: {
    model_id: string
    k: number
    ordered_features: string[]
    cohort_size: number
    interpretation: string
  }
}
