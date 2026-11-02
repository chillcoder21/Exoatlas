import {
  axisBottom,
  axisLeft,
  extent,
  pointer,
  scaleLinear,
  scaleLog,
  select,
  symbol,
  symbolCircle,
  symbolDiamond,
  symbolSquare,
  symbolTriangle,
  zoom,
  zoomIdentity,
  zoomTransform,
} from 'd3'
import type { ScaleContinuousNumeric, Selection, ZoomBehavior } from 'd3'
import { useEffect, useRef, useState } from 'react'
import { formatMeasurement, getFeature, getPlottablePlanets } from './features'
import type { FeatureKey, PlanetRecord } from './types'
import styles from './FeatureSpacePlot.module.css'

type PlotDatum = {
  planet: PlanetRecord
  x: number
  y: number
}

type PlotState = {
  xKey: FeatureKey
  yKey: FeatureKey
  xScale: ScaleContinuousNumeric<number, number>
  yScale: ScaleContinuousNumeric<number, number>
  xAxis: Selection<SVGGElement, unknown, null, undefined>
  yAxis: Selection<SVGGElement, unknown, null, undefined>
  points: Selection<SVGGElement, unknown, null, undefined>
  width: number
  height: number
  margin: { top: number; right: number; bottom: number; left: number }
}

type TooltipState = {
  planet: PlanetRecord
  left: number
  top: number
}

type FeatureSpacePlotProps = {
  planets: PlanetRecord[]
  xKey: FeatureKey
  yKey: FeatureKey
  selectedPlanetId: string | null
  hiddenClusters: Set<number>
  showUnassigned: boolean
  reducedMotion: boolean
  resetZoomKey: number
  onSelectPlanet: (planet: PlanetRecord) => void
}

const CLUSTER_SYMBOLS = [symbolCircle, symbolSquare, symbolTriangle, symbolDiamond]

function paddedDomain(
  values: number[],
  key: FeatureKey,
): [number, number] {
  const [rawMin, rawMax] = extent(values)
  if (rawMin === undefined || rawMax === undefined) {
    return getFeature(key).scale === 'logarithmic' ? [0.1, 10] : [0, 1]
  }
  if (getFeature(key).scale === 'logarithmic') {
    if (rawMin === rawMax) return [rawMin / 1.5, rawMax * 1.5]
    return [rawMin, rawMax]
  }

  if (rawMin === rawMax) {
    const padding = Math.abs(rawMin) * 0.05 || 1
    return [rawMin - padding, rawMax + padding]
  }
  const padding = (rawMax - rawMin) * 0.05
  const min = key === 'pl_orbeccen' && rawMin >= 0 ? 0 : rawMin - padding
  return [min, rawMax + padding]
}

function makeScale(key: FeatureKey, domain: [number, number], range: [number, number]) {
  return getFeature(key).scale === 'logarithmic'
    ? scaleLog().domain(domain).range(range).clamp(false)
    : scaleLinear().domain(domain).range(range).clamp(false)
}

function renderAxes(state: PlotState, xScale = state.xScale, yScale = state.yScale) {
  const innerWidth = state.width - state.margin.left - state.margin.right
  const innerHeight = state.height - state.margin.top - state.margin.bottom
  const tickCount = state.width < 520 ? 4 : 7
  state.xAxis.call(
    axisBottom(xScale)
      .ticks(tickCount)
      .tickSize(-innerHeight)
      .tickFormat((value) => formatMeasurement(Number(value), state.xKey)),
  )
  state.yAxis.call(
    axisLeft(yScale)
      .ticks(tickCount)
      .tickSize(-innerWidth)
      .tickFormat((value) => formatMeasurement(Number(value), state.yKey)),
  )
}

function updatePointPositions(state: PlotState, xScale = state.xScale, yScale = state.yScale) {
  state.points.selectAll<SVGPathElement, PlotDatum>('path.planet-point').attr(
    'transform',
    (datum) => `translate(${xScale(datum.x)},${yScale(datum.y)})`,
  )
}

export function FeatureSpacePlot({
  planets,
  xKey,
  yKey,
  selectedPlanetId,
  hiddenClusters,
  showUnassigned,
  reducedMotion,
  resetZoomKey,
  onSelectPlanet,
}: FeatureSpacePlotProps) {
  const frameRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const plotStateRef = useRef<PlotState | null>(null)
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const previousAxesRef = useRef(`${xKey}:${yKey}`)
  const [size, setSize] = useState({ width: 960, height: 540 })
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  useEffect(() => {
    const frame = frameRef.current
    if (!frame) return

    const measure = () => {
      const width = Math.max(frame.clientWidth, 320)
      const height = Math.max(frame.clientHeight, width < 520 ? 410 : 470)
      setSize((current) =>
        current.width === width && current.height === height ? current : { width, height },
      )
    }

    measure()
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(measure)
      observer.observe(frame)
      return () => observer.disconnect()
    }
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  useEffect(() => {
    const svgElement = svgRef.current
    if (!svgElement) return
    const svg = select(svgElement)
    svg.selectAll('*').remove()

    const width = size.width
    const height = size.height
    const margin = {
      top: 22,
      right: 18,
      bottom: width < 520 ? 68 : 72,
      left: width < 520 ? 58 : 88,
    }
    const xAxis = svg
      .append('g')
      .attr('class', styles.axis)
      .attr('transform', `translate(0,${height - margin.bottom})`)
    const yAxis = svg
      .append('g')
      .attr('class', styles.axis)
      .attr('transform', `translate(${margin.left},0)`)
    const points = svg
      .append('g')
      .attr('class', styles.points)
      .attr('clip-path', 'url(#universe-plot-clip)')

    svg
      .append('defs')
      .append('clipPath')
      .attr('id', 'universe-plot-clip')
      .append('rect')
      .attr('x', margin.left)
      .attr('y', margin.top)
      .attr('width', width - margin.left - margin.right)
      .attr('height', height - margin.top - margin.bottom)

    svg
      .append('text')
      .attr('class', styles.axisLabel)
      .attr('x', margin.left + (width - margin.left - margin.right) / 2)
      .attr('y', height - 12)
      .attr('text-anchor', 'middle')
      .text('')
    svg
      .append('text')
      .attr('class', styles.yAxisLabel)
      .attr('transform', `translate(17,${margin.top + (height - margin.top - margin.bottom) / 2}) rotate(-90)`)
      .attr('text-anchor', 'middle')
      .text('')

    const initialX = scaleLinear().domain([0, 1]).range([margin.left, width - margin.right])
    const initialY = scaleLinear().domain([0, 1]).range([height - margin.bottom, margin.top])
    const state: PlotState = {
      xKey,
      yKey,
      xScale: initialX,
      yScale: initialY,
      xAxis,
      yAxis,
      points,
      width,
      height,
      margin,
    }
    plotStateRef.current = state

    const zoomBehavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 32])
      .extent([
        [margin.left, margin.top],
        [width - margin.right, height - margin.bottom],
      ])
      .translateExtent([
        [margin.left - width, margin.top - height],
        [width - margin.right + width, height - margin.bottom + height],
      ])
      .on('zoom', (event) => {
        const current = plotStateRef.current
        if (!current) return
        const zoomedX = event.transform.rescaleX(current.xScale)
        const zoomedY = event.transform.rescaleY(current.yScale)
        renderAxes(current, zoomedX, zoomedY)
        updatePointPositions(current, zoomedX, zoomedY)
      })
    zoomRef.current = zoomBehavior
    svg.call(zoomBehavior).on('dblclick.zoom', null)

    return () => {
      svg.on('.zoom', null)
      svg.selectAll('*').remove()
      plotStateRef.current = null
      zoomRef.current = null
    }
    // The SVG structure is rebuilt only when its measured dimensions change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size.width, size.height])

  useEffect(() => {
    const svgElement = svgRef.current
    const state = plotStateRef.current
    if (!svgElement || !state) return

    const allPoints = getPlottablePlanets(planets, xKey, yKey)
    const visiblePoints = allPoints.filter(({ planet }) =>
      planet.cluster_id === null ? showUnassigned : !hiddenClusters.has(planet.cluster_id),
    )
    const xFeature = getFeature(xKey)
    const yFeature = getFeature(yKey)
    const xScale = makeScale(
      xKey,
      paddedDomain(allPoints.map((datum) => datum.x), xKey),
      [state.margin.left, state.width - state.margin.right],
    )
    const yScale = makeScale(
      yKey,
      paddedDomain(allPoints.map((datum) => datum.y), yKey),
      [state.height - state.margin.bottom, state.margin.top],
    )

    state.xKey = xKey
    state.yKey = yKey
    state.xScale = xScale
    state.yScale = yScale

    const axesChanged = previousAxesRef.current !== `${xKey}:${yKey}`
    previousAxesRef.current = `${xKey}:${yKey}`
    if (axesChanged && zoomRef.current) {
      select(svgElement).call(zoomRef.current.transform, zoomIdentity)
    }

    const transform = zoomTransform(svgElement)
    const zoomedX = transform.rescaleX(xScale)
    const zoomedY = transform.rescaleY(yScale)
    const axisTransitionDuration = reducedMotion ? 0 : 180
    const xAxis = axisBottom(zoomedX)
      .ticks(size.width < 520 ? 4 : 7)
      .tickSize(-(state.height - state.margin.top - state.margin.bottom))
      .tickFormat((value) => formatMeasurement(Number(value), xKey))
    const yAxis = axisLeft(zoomedY)
      .ticks(size.width < 520 ? 4 : 7)
      .tickSize(-(state.width - state.margin.left - state.margin.right))
      .tickFormat((value) => formatMeasurement(Number(value), yKey))
    if (reducedMotion) {
      state.xAxis.call(xAxis)
      state.yAxis.call(yAxis)
    } else {
      state.xAxis.transition().duration(axisTransitionDuration).call(xAxis)
      state.yAxis.transition().duration(axisTransitionDuration).call(yAxis)
    }

    state.xAxis
      .selectAll('.domain')
      .attr('stroke', 'var(--color-border-strong)')
    state.xAxis.selectAll('.tick line').attr('stroke', 'var(--color-border)')
    state.xAxis.selectAll('.tick text').attr('fill', 'var(--color-muted)')
    state.yAxis
      .selectAll('.domain')
      .attr('stroke', 'var(--color-border-strong)')
    state.yAxis.selectAll('.tick line').attr('stroke', 'var(--color-border)')
    state.yAxis.selectAll('.tick text').attr('fill', 'var(--color-muted)')

    const svg = select(svgElement)
    svg
      .select<SVGTextElement>(`.${styles.axisLabel}`)
      .text(`${xFeature.label} (${xFeature.unit}) · ${xFeature.scale} scale`)
    svg
      .select<SVGTextElement>(`.${styles.yAxisLabel}`)
      .text(`${yFeature.label} (${yFeature.unit}) · ${yFeature.scale} scale`)

    const join = state.points
      .selectAll<SVGPathElement, PlotDatum>('path.planet-point')
      .data(visiblePoints, (datum) => datum.planet.pl_name)
    const duration = reducedMotion ? 0 : 210
    if (reducedMotion) {
      join.exit().remove()
    } else {
      join.exit().transition().duration(150).attr('opacity', 0).remove()
    }

    const entering = join
      .enter()
      .append('path')
      .attr('class', 'planet-point')
      .attr('aria-hidden', 'true')
      .attr('opacity', 0)
    const merged = entering.merge(join)
    merged
      .attr('data-planet-id', (datum) => datum.planet.pl_name)
      .attr('d', (datum) => {
        const clusterId = datum.planet.cluster_id
        const shape = clusterId === null ? symbolCircle : CLUSTER_SYMBOLS[clusterId] ?? symbolDiamond
        return symbol().type(shape).size(clusterId === null ? 16 : 25)()
      })
      .attr('fill', (datum) =>
        datum.planet.cluster_id === null
          ? 'var(--color-canvas)'
          : `var(--cluster-${datum.planet.cluster_id})`,
      )
      .attr('fill-opacity', (datum) => (datum.planet.cluster_id === null ? 0.22 : 0.88))
      .attr('stroke', (datum) =>
        datum.planet.cluster_id === null ? 'var(--color-muted)' : 'var(--color-canvas)',
      )
      .attr('stroke-width', (datum) => (datum.planet.cluster_id === null ? 1.1 : 0.55))
      .attr('stroke-dasharray', (datum) => (datum.planet.cluster_id === null ? '2.2 1.8' : null))
      .classed('is-selected', (datum) => datum.planet.pl_name === selectedPlanetId)
      .on('pointerenter', (event: PointerEvent, datum) => {
        const frame = frameRef.current
        if (!frame) return
        const [x, y] = pointer(event, frame)
        setTooltip({
          planet: datum.planet,
          left: Math.min(x + 14, Math.max(frame.clientWidth - 260, 8)),
          top: Math.min(y + 14, Math.max(frame.clientHeight - 196, 8)),
        })
      })
      .on('pointermove', (event: PointerEvent, datum) => {
        const frame = frameRef.current
        if (!frame) return
        const [x, y] = pointer(event, frame)
        setTooltip({
          planet: datum.planet,
          left: Math.min(x + 14, Math.max(frame.clientWidth - 260, 8)),
          top: Math.min(y + 14, Math.max(frame.clientHeight - 196, 8)),
        })
      })
      .on('pointerleave', () => setTooltip(null))
      .on('click', (_event: MouseEvent, datum) => onSelectPlanet(datum.planet))

    const finalPoints = reducedMotion
      ? merged.attr('opacity', 1)
      : merged.transition().duration(duration).attr('opacity', 1)
    finalPoints.attr('transform', (datum) => `translate(${zoomedX(datum.x)},${zoomedY(datum.y)})`)

    svg
      .select<SVGTextElement>(`.${styles.emptyPlot}`)
      .remove()
    if (visiblePoints.length === 0) {
      svg
        .append('text')
        .attr('class', styles.emptyPlot)
        .attr('x', state.margin.left + (state.width - state.margin.left - state.margin.right) / 2)
        .attr('y', state.margin.top + (state.height - state.margin.top - state.margin.bottom) / 2)
        .attr('text-anchor', 'middle')
        .text('No planets are visible with the current population controls.')
    }
  }, [
    planets,
    xKey,
    yKey,
    selectedPlanetId,
    hiddenClusters,
    showUnassigned,
    reducedMotion,
    size.width,
    size.height,
    onSelectPlanet,
  ])

  useEffect(() => {
    const svg = svgRef.current
    const zoomBehavior = zoomRef.current
    if (!svg || !zoomBehavior) return
    select(svg).call(zoomBehavior.transform, zoomIdentity)
  }, [resetZoomKey])

  const hoveredPlanet = tooltip?.planet ?? null

  return (
    <figure className={styles.figure}>
      <div className={styles.plotFrame} ref={frameRef}>
        <svg
          ref={svgRef}
          className={styles.svg}
          role="img"
          aria-label="Interactive planetary feature-space map"
          aria-describedby="universe-plot-description"
          viewBox={`0 0 ${size.width} ${size.height}`}
          preserveAspectRatio="none"
        />
        {tooltip && hoveredPlanet && (
          <div className={styles.tooltip} role="tooltip" style={{ left: tooltip.left, top: tooltip.top }}>
            <p className={styles.tooltipTitle}>{hoveredPlanet.pl_name}</p>
            <p className={styles.tooltipHost}>{hoveredPlanet.hostname ?? 'Host star not available'}</p>
            <dl className={styles.tooltipMeasurements}>
              <div>
                <dt>Radius</dt>
                <dd>{formatMeasurement(hoveredPlanet.pl_rade, 'pl_rade')} R⊕</dd>
              </div>
              <div>
                <dt>Period</dt>
                <dd>{formatMeasurement(hoveredPlanet.pl_orbper, 'pl_orbper')} days</dd>
              </div>
              <div>
                <dt>Temperature</dt>
                <dd>{formatMeasurement(hoveredPlanet.pl_eqt, 'pl_eqt')} K</dd>
              </div>
              <div>
                <dt>Eccentricity</dt>
                <dd>{formatMeasurement(hoveredPlanet.pl_orbeccen, 'pl_orbeccen')}</dd>
              </div>
            </dl>
            <p className={styles.tooltipAssignment}>
              {hoveredPlanet.cluster_id === null
                ? 'Unassigned in the exploratory K=4 model'
                : `Exploratory cluster ${hoveredPlanet.cluster_id}`}
            </p>
          </div>
        )}
      </div>
      <figcaption className={styles.caption} id="universe-plot-description">
        Each mark represents one confirmed planet with valid values for both selected axes. Points
        are interactive; search offers a keyboard-accessible way to select any loaded record. This
        feature-space map does not show celestial coordinates.
      </figcaption>
      <span className={styles.srOnly} aria-live="polite">
        {hoveredPlanet ? `Point under pointer: ${hoveredPlanet.pl_name}.` : ''}
      </span>
    </figure>
  )
}
