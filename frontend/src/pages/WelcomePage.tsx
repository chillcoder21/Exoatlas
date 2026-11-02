import { Link } from 'react-router-dom'
import type { CSSProperties } from 'react'
import { atlasSections } from '../config/sections'
import styles from './WelcomePage.module.css'

export function WelcomePage() {
  return (
    <div className={styles.page}>
      <section className={styles.hero} aria-labelledby="page-title">
        <div className={styles.heroIntro}>
          <p className={styles.eyebrow}>An atlas for confirmed exoplanets</p>
          <h1 className={styles.title} id="page-title" tabIndex={-1}>
            What can confirmed worlds tell us?
          </h1>
          <p className={styles.lead}>
            ExoAtlas is a scientific atlas for exploring planetary measurements
            and the methods that bring distant worlds into view.
          </p>
          <Link className={styles.primaryLink} to="/universe">
            <span>Begin with The Universe</span>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M3.5 10h12m-5-5 5 5-5 5" />
            </svg>
          </Link>
        </div>

        <aside className={styles.questionPanel} aria-labelledby="question-title">
          <div className={styles.panelHeading}>
            <span className={styles.panelIndex} aria-hidden="true">01</span>
            <h2 className={styles.panelLabel} id="question-title">The guiding question</h2>
          </div>
          <p className={styles.question}>
            Can confirmed exoplanets be grouped by their physical and orbital
            characteristics—and how do our discovery methods shape the
            population we observe?
          </p>
          <div className={styles.questionTopics} aria-label="Research themes">
            <span>Measured properties</span>
            <span>Discovery methods</span>
          </div>
        </aside>
      </section>

      <section className={styles.chapters} id="chapters" aria-labelledby="chapters-title">
        <div className={styles.sectionHeading}>
          <div>
            <p className={styles.eyebrow}>Five connected chapters</p>
            <h2 className={styles.chaptersTitle} id="chapters-title">
              One population, different points of view.
            </h2>
          </div>
          <p className={styles.sectionIntro}>
            Follow the questions from the archive as each view of the atlas is
            brought into focus.
          </p>
        </div>

        <ol className={styles.chapterList}>
          {atlasSections.map((section, index) => (
            <li key={section.id} className={styles.chapterItem}>
              <Link className={styles.chapterLink} to={section.path}>
                <span
                  className={styles.chapterIndex}
                  style={{ '--section-accent': section.accent } as CSSProperties}
                  aria-hidden="true"
                >
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span className={styles.chapterBody}>
                  <span className={styles.chapterTitle}>{section.title}</span>
                  <span className={styles.chapterDescription}>{section.description}</span>
                </span>
                <svg className={styles.chapterArrow} viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M3.5 10h12m-5-5 5 5-5 5" />
                </svg>
              </Link>
            </li>
          ))}
        </ol>
        <p className={styles.chapterNote}>
          Each chapter is being built around the verified archive and prepared
          ExoAtlas data layer.
        </p>
      </section>
    </div>
  )
}
