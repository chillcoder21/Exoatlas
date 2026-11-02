import { Link } from 'react-router-dom'
import type { CSSProperties } from 'react'
import { atlasSections, type AtlasSection } from '../config/sections'
import styles from './DevelopmentPage.module.css'

type DevelopmentPageProps = {
  section: AtlasSection
}

export function DevelopmentPage({ section }: DevelopmentPageProps) {
  const sectionNumber = atlasSections.findIndex((item) => item.id === section.id) + 1

  return (
    <section className={styles.page} aria-labelledby="page-title">
      <p className={styles.eyebrow}>
        <span
          className={styles.sectionIndex}
          style={{ '--section-accent': section.accent } as CSSProperties}
        >
          {String(sectionNumber).padStart(2, '0')}
        </span>
        ExoAtlas chapter
      </p>
      <h1 className={styles.title} id="page-title" tabIndex={-1}>
        {section.title}
      </h1>
      <p className={styles.description}>{section.description}</p>

      <div className={styles.status} role="status">
        <span
          className={styles.statusMark}
          style={{ '--section-accent': section.accent } as CSSProperties}
          aria-hidden="true"
        />
        <div>
          <p className={styles.statusTitle}>In development</p>
          <p className={styles.statusCopy}>
            This chapter is being designed around the verified NASA archive and
            the prepared ExoAtlas data layer.
          </p>
        </div>
      </div>

      <Link className={styles.backLink} to="/">
        Return to the atlas introduction
        <svg viewBox="0 0 20 20" aria-hidden="true">
          <path d="M3.5 10h12m-5-5 5 5-5 5" />
        </svg>
      </Link>
    </section>
  )
}
