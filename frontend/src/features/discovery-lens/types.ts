export type DiscoveryProperty = 'pl_rade' | 'pl_orbper' | 'pl_eqt' | 'pl_orbeccen'

export type MethodSummary = {
  discovery_method: string
  planet_count: number
  catalogue_percentage: number
  unique_host_count: number
  facility_count: number
  first_discovery_year: number
  last_discovery_year: number
}

export type DiscoveryOverview = {
  source: {
    catalogue: string
    source_file: string
    prepared_application_dataset: string
    snapshot_date: string
    download_date: string
    download_timestamp: string
    raw_source_present: boolean
    raw_source_sha256: string | null
    note: string
  }
  snapshot_date: string
  total_planet_records: number
  number_of_discovery_methods: number
  number_of_discovery_years: number
  number_of_facilities: number
  number_of_unique_host_systems: number
  first_discovery_year: number
  last_discovery_year: number
  methods: MethodSummary[]
  limitations: string[]
}

export type TimelineMethodCount = {
  discovery_method: string
  planet_count: number
  within_year_percentage: number
}

export type TimelineYear = {
  year: number
  total_planet_records: number
  selected_method_planet_records: number
  methods: TimelineMethodCount[]
  is_partial_year: boolean
}

export type DiscoveryTimeline = {
  snapshot_date: string
  selected_methods: string[]
  partial_year: { year: number; is_partial: boolean; as_of_date: string; note: string }
  interpretation_note: string
  years: TimelineYear[]
}

export type PropertyObservation = {
  pl_name: string
  hostname: string
  value: number
  error_1: number | null
  error_2: number | null
  uncertainty_available: boolean
}

export type PropertyDistribution = {
  discovery_method: string
  total_planet_records: number
  error_1_field: string
  error_2_field: string
  measured_count: number
  missing_count: number
  zero_measurement_count: number
  measurement_availability_pct: number
  median: number | null
  q1: number | null
  q3: number | null
  minimum: number | null
  maximum: number | null
  unique_hosts_measured: number
  uncertainty_count: number
  error_1_count: number
  error_2_count: number
  uncertainty_availability_pct: number
  sample_size_warning: { is_small: boolean; message: string | null }
  observations: PropertyObservation[]
}

export type DiscoveryDistributions = {
  property: DiscoveryProperty
  label: string
  unit: string
  axis_scale: 'linear' | 'log'
  selected_methods: string[]
  host_independence_note: string
  uncertainty_note: string
  distributions: PropertyDistribution[]
}

export type FacilityCount = {
  facility: string
  planet_count: number
  percentage: number
}

export type DiscoveryFacilities = {
  scope: string | string[]
  denominator_planet_records: number
  records_without_facility: number
  facility_count: number
  facilities: FacilityCount[]
  interpretation_note: string
}
