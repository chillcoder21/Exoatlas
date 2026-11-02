import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import type { PlanetRecord } from './types'
import styles from './UniversePage.module.css'

type PlanetSearchProps = {
  planets: PlanetRecord[]
  value: string
  onChange: (value: string) => void
  onSelect: (planet: PlanetRecord) => void
}

const MAX_RESULTS = 8

export function PlanetSearch({ planets, value, onChange, onSelect }: PlanetSearchProps) {
  const [focused, setFocused] = useState(false)
  const matches = useMemo(() => {
    const query = value.trim().toLocaleLowerCase()
    if (!query) return { total: 0, planets: [] as PlanetRecord[] }
    const found: PlanetRecord[] = []
    let total = 0
    for (const planet of planets) {
      if (
        planet.pl_name.toLocaleLowerCase().includes(query) ||
        (planet.hostname ?? '').toLocaleLowerCase().includes(query)
      ) {
        total += 1
        if (found.length < MAX_RESULTS) found.push(planet)
      }
    }
    return { total, planets: found }
  }, [planets, value])

  const showResults = focused && Boolean(value.trim())

  function selectFirstMatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (matches.planets[0]) {
      setFocused(false)
      onSelect(matches.planets[0])
    }
  }

  return (
    <form className={styles.search} onSubmit={selectFirstMatch} role="search">
      <label className={styles.controlLabel} htmlFor="planet-search">
        Find a planet
      </label>
      <div className={styles.searchInputRow}>
        <input
          autoComplete="off"
          id="planet-search"
          name="planet"
          onBlur={() => window.setTimeout(() => setFocused(false), 120)}
          onChange={(event) => onChange(event.target.value)}
          onFocus={() => setFocused(true)}
          placeholder="Search planet or host name"
          type="search"
          value={value}
          aria-describedby="planet-search-help"
        />
        {value && (
          <button className={styles.clearSearch} type="button" onClick={() => onChange('')}>
            Clear
          </button>
        )}
      </div>
      <span className={styles.srOnly} id="planet-search-help">
        Search covers every planet record loaded from the API. Press Enter to select the first match.
      </span>
      {showResults && (
        <div className={styles.searchResults} id="planet-search-results" role="region" aria-label="Planet search results">
          {matches.total === 0 ? (
            <p className={styles.searchEmpty}>No planet names or host stars match “{value.trim()}”.</p>
          ) : (
            <>
              <p className={styles.resultCount}>
                {matches.total} matching {matches.total === 1 ? 'record' : 'records'}
                {matches.total > MAX_RESULTS ? ` · showing ${MAX_RESULTS}` : ''}
              </p>
              <ul>
                {matches.planets.map((planet) => (
                  <li key={planet.pl_name}>
                    <button
                      className={styles.searchResult}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => {
                        setFocused(false)
                        onSelect(planet)
                      }}
                      type="button"
                    >
                      <span>
                        <span className={styles.resultName}>{planet.pl_name}</span>
                        <span className={styles.resultHost}>{planet.hostname ?? 'Host star not available'}</span>
                      </span>
                      <span className={styles.resultAssignment}>
                        {planet.cluster_id === null ? 'Unassigned' : `Cluster ${planet.cluster_id}`}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </form>
  )
}
