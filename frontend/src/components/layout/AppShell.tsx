import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, NavLink, Route, Routes, useLocation, Navigate } from 'react-router-dom'
import type { CSSProperties } from 'react'
import { atlasSections } from '../../config/sections'
import { DevelopmentPage } from '../../pages/DevelopmentPage'
import { WelcomePage } from '../../pages/WelcomePage'
import styles from './AppShell.module.css'

const UniversePage = lazy(() => import('../../features/universe/UniversePage').then((module) => ({ default: module.UniversePage })))
const PatternsPage = lazy(() => import('../../features/patterns/PatternsPage').then((module) => ({ default: module.PatternsPage })))
const ExplorerPage = lazy(() => import('../../features/explorer/ExplorerPage').then((module) => ({ default: module.ExplorerPage })))
const OutliersPage = lazy(() => import('../../features/outliers/OutliersPage').then((module) => ({ default: module.OutliersPage })))
const DiscoveryLensPage = lazy(() => import('../../features/discovery-lens/DiscoveryLensPage').then((module) => ({ default: module.DiscoveryLensPage })))

function RouteFocus({ children }: { children: ReactNode }) {
  const location = useLocation()

  useEffect(() => {
    document.getElementById('page-title')?.focus()
  }, [location.pathname])

  return children
}

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const location = useLocation()
  const lastPathRef = useRef(location.pathname)
  const selectedPlanet = new URLSearchParams(location.search).get('planet')
  const routeTarget = (path: string) => {
    if (!selectedPlanet) return path
    const query = new URLSearchParams({ planet: selectedPlanet })
    return `${path}?${query.toString()}`
  }

  useEffect(() => {
    const section = atlasSections.find((item) => item.path === location.pathname)
    document.title = section ? `${section.title} · ExoAtlas` : 'ExoAtlas · A scientific atlas'

    if (lastPathRef.current !== location.pathname) {
      document.getElementById('page-title')?.focus()
      lastPathRef.current = location.pathname
    }
    setMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!menuOpen) return

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setMenuOpen(false)
        menuButtonRef.current?.focus()
      }
    }

    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [menuOpen])

  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#main-content">
        Skip to main content
      </a>

      <header>
        <div className={styles.masthead}>
          <Link className={styles.brand} to="/" aria-label="ExoAtlas home">
            <svg className={styles.brandMark} viewBox="0 0 40 40" aria-hidden="true">
              <path d="M8 15V8h7M25 8h7v7M32 25v7h-7M15 32H8v-7" fill="none" stroke="currentColor" strokeWidth="1.5" />
              <path d="M20 11v18M11 20h18" fill="none" stroke="currentColor" strokeOpacity=".48" strokeWidth=".8" />
              <circle cx="20" cy="20" r="2.5" fill="currentColor" />
            </svg>
            <span className={styles.brandText}>
              <span className={styles.brandName}>ExoAtlas</span>
              <span className={styles.brandCaption}>Confirmed exoplanets</span>
            </span>
          </Link>

          <p className={styles.mastheadNote}>
            <span className={styles.noteRule} aria-hidden="true" />
              Confirmed planets · catalogue view
          </p>

          <button
            ref={menuButtonRef}
            aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
            aria-expanded={menuOpen}
            aria-controls="primary-navigation"
            className={styles.mobileToggle}
            onClick={() => setMenuOpen((open) => !open)}
            type="button"
          >
            <span
              className={`${styles.menuIcon} ${menuOpen ? styles.menuIconOpen : ''}`}
              aria-hidden="true"
            >
              <span className={styles.menuIconLine} />
              <span className={styles.menuIconLine} />
            </span>
            <span>{menuOpen ? 'Close' : 'Menu'}</span>
          </button>
        </div>

        <div className={styles.navigationShell}>
          <nav
            className={styles.navigation}
            id="primary-navigation"
            aria-label="Primary navigation"
          >
            <ul className={styles.navigationList} data-open={menuOpen}>
              {atlasSections.map((section, index) => (
                <li className={styles.navigationItem} key={section.id}>
                  <NavLink
                    to={routeTarget(section.path)}
                    onClick={() => setMenuOpen(false)}
                    className={styles.navigationLink}
                    style={{ '--section-accent': section.accent } as CSSProperties}
                  >
                    <span className={styles.navigationIndex} aria-hidden="true">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span className={styles.navigationCopy}>
                      <span className={styles.navigationTitle}>{section.title}</span>
                      <span className={styles.navigationDescription}>
                        {section.shortDescription}
                      </span>
                    </span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        {selectedPlanet && location.pathname !== '/explorer' && (
          <div className={styles.contextStrip}>
            <span>Record in context</span>
            <strong>{selectedPlanet}</strong>
            <Link to={routeTarget('/explorer')}>Open planet dossier <span aria-hidden="true">↗</span></Link>
          </div>
        )}
      </header>

      <main className={styles.main} id="main-content" tabIndex={-1}>
        <div className={styles.pageTransition} key={location.pathname}>
          <Suspense fallback={<div className={styles.routeLoading} role="status" aria-live="polite">Opening chapter…</div>}>
            <RouteFocus>
          <Routes>
            <Route path="/" element={<WelcomePage />} />
            <Route path="/universe" element={<UniversePage />} />
            <Route path="/patterns" element={<PatternsPage />} />
            <Route path="/explorer" element={<ExplorerPage />} />
            <Route path="/outliers" element={<OutliersPage />} />
            <Route path="/discovery-lens" element={<DiscoveryLensPage />} />
            {atlasSections.filter((section) => !['universe', 'patterns', 'explorer', 'outliers', 'discovery-lens'].includes(section.id)).map((section) => (
              <Route
                key={section.path}
                path={section.path}
                element={<DevelopmentPage section={section} />}
              />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
            </RouteFocus>
          </Suspense>
        </div>
      </main>

      <footer className={styles.footer}>
        <span className={styles.footerText}>An atlas for looking closer.</span>
        <span className={styles.footerLabel}>NASA Exoplanet Archive · PSCompPars · 2026-10-30</span>
      </footer>
    </div>
  )
}
