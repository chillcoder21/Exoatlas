export type AtlasSection = {
  id: string
  path: string
  title: string
  description: string
  shortDescription: string
  accent: string
}

export const atlasSections: AtlasSection[] = [
  {
    id: 'universe',
    path: '/universe',
    title: 'The Universe',
    description: 'Explore the confirmed exoplanet population.',
    shortDescription: 'The confirmed population',
    accent: 'var(--accent-teal)',
  },
  {
    id: 'patterns',
    path: '/patterns',
    title: 'The Patterns',
    description: 'Investigate exploratory clusters and their measured profiles.',
    shortDescription: 'Patterns in measured properties',
    accent: 'var(--accent-amber)',
  },
  {
    id: 'explorer',
    path: '/explorer',
    title: 'The Explorer',
    description: 'Examine individual planets and similar objects.',
    shortDescription: 'Planet by planet',
    accent: 'var(--accent-blue)',
  },
  {
    id: 'outliers',
    path: '/outliers',
    title: 'The Outliers',
    description: 'Investigate unusual observations against selected features.',
    shortDescription: 'Observations worth a closer look',
    accent: 'var(--accent-coral)',
  },
  {
    id: 'discovery-lens',
    path: '/discovery-lens',
    title: 'The Discovery Lens',
    description: 'Explore how discovery methods shape the population we observe.',
    shortDescription: 'How we find worlds',
    accent: 'var(--accent-blue-muted)',
  },
]
