import { useEffect, useRef } from 'react'
import {
  axisBottom,
  axisLeft,
  extent,
  line,
  max,
  scaleBand,
  scaleLinear,
  scaleLog,
  select,
} from 'd3'
import type {
  DiscoveryDistributions,
  DiscoveryFacilities,
  DiscoveryOverview,
  DiscoveryTimeline,
} from './types'
import styles from './DiscoveryLensPage.module.css'

const palette = [
  '#76c8b8', '#d6ad6f', '#91b8e2', '#dd927e', '#b7a2d1', '#bad29a',
  '#cf91b4', '#9bc9d8', '#d6c984', '#e2a977', '#99b2a4',
]

export function CompositionChart({ overview, selectedMethods }: {
  overview: DiscoveryOverview
  selectedMethods: string[]
}) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    const svg = select(ref.current)
    svg.selectAll('*').remove()
    const rows = [...overview.methods].sort((a, b) => b.planet_count - a.planet_count)
    const width = 900
    const height = Math.max(315, rows.length * 31 + 70)
    const margin = { top: 14, right: 120, bottom: 48, left: 245 }
    const plotWidth = width - margin.left - margin.right
    const plotHeight = height - margin.top - margin.bottom
    const x = scaleLinear().domain([0, max(rows, (row) => row.planet_count) ?? 1]).nice().range([0, plotWidth])
    const y = scaleBand<string>().domain(rows.map((row) => row.discovery_method)).range([0, plotHeight]).padding(0.24)
    const plot = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    plot.append('g').attr('class', styles.chartGrid)
      .call(axisBottom(x).ticks(5).tickSize(plotHeight).tickFormat(() => ''))
      .attr('transform', 'translate(0,0)')
    plot.append('g').attr('class', styles.chartAxis).call(axisLeft(y).tickSize(0))
    plot.append('g').attr('class', styles.chartAxis)
      .attr('transform', `translate(0,${plotHeight})`)
      .call(axisBottom(x).ticks(5).tickFormat((value) => Number(value).toLocaleString()))
    plot.selectAll<SVGRectElement, (typeof rows)[number]>('rect')
      .data(rows)
      .join('rect')
      .attr('x', 0)
      .attr('y', (row) => y(row.discovery_method) ?? 0)
      .attr('width', (row) => x(row.planet_count))
      .attr('height', y.bandwidth())
      .attr('fill', (row) => selectedMethods.length === 0 || selectedMethods.includes(row.discovery_method)
        ? 'var(--accent-teal)' : 'var(--color-border-strong)')
      .attr('fill-opacity', 0.86)
      .append('title')
      .text((row) => `${row.discovery_method}: ${row.planet_count.toLocaleString()} planet records; ${row.catalogue_percentage.toFixed(2)}% of ${overview.total_planet_records.toLocaleString()} catalogue records`)
    plot.selectAll<SVGTextElement, (typeof rows)[number]>('.value-label')
      .data(rows)
      .join('text')
      .attr('class', 'value-label')
      .attr('x', (row) => x(row.planet_count) + 8)
      .attr('y', (row) => (y(row.discovery_method) ?? 0) + y.bandwidth() / 2 + 4)
      .attr('fill', 'var(--color-text)')
      .attr('font-size', 11)
      .attr('font-family', 'var(--font-mono)')
      .text((row) => `${row.planet_count.toLocaleString()} · ${row.catalogue_percentage.toFixed(2)}%`)
    svg.attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet')
  }, [overview, selectedMethods])
  return <svg ref={ref} className={styles.chart} role="img" aria-label="Horizontal bars show planet records by all eleven discovery methods and percentage of the full catalogue." />
}

export function TimelineChart({ timeline, selectedMethods }: {
  timeline: DiscoveryTimeline
  selectedMethods: string[]
}) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    const svg = select(ref.current)
    svg.selectAll('*').remove()
    const width = 900
    const height = 350
    const margin = { top: 24, right: 30, bottom: 52, left: 62 }
    const plotWidth = width - margin.left - margin.right
    const plotHeight = height - margin.top - margin.bottom
    const x = scaleLinear().domain([1992, 2026]).range([0, plotWidth])
    const aggregate = selectedMethods.length === 0
    const lineMaximum = aggregate
      ? max(timeline.years, (year) => year.total_planet_records) ?? 1
      : max(timeline.years, (year) => max(year.methods, (method) => method.planet_count) ?? 0) ?? 1
    const y = scaleLinear().domain([0, lineMaximum]).nice().range([plotHeight, 0])
    const plot = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    plot.append('g').attr('class', styles.chartGrid)
      .call(axisLeft(y).ticks(5).tickSize(-plotWidth).tickFormat((value) => Number(value).toLocaleString()))
    plot.append('g').attr('class', styles.chartAxis)
      .attr('transform', `translate(0,${plotHeight})`)
      .call(axisBottom(x).tickValues([1992, 1995, 2000, 2005, 2010, 2015, 2020, 2026]).tickFormat((value) => String(value)))
    plot.append('g').attr('class', styles.chartAxis).call(axisLeft(y).ticks(5).tickFormat((value) => Number(value).toLocaleString()))

    const lineData = aggregate
      ? [{ name: 'All catalogue records', color: 'var(--accent-teal)', values: timeline.years.map((year) => ({ year: year.year, count: year.total_planet_records })) }]
      : selectedMethods.map((method) => ({
          name: method,
          color: palette[Math.max(0, timeline.years[0]?.methods.findIndex((item) => item.discovery_method === method) ?? 0) % palette.length],
          values: timeline.years.map((year) => ({
            year: year.year,
            count: year.methods.find((item) => item.discovery_method === method)?.planet_count ?? 0,
          })),
        }))
    const path = line<{ year: number; count: number }>().x((point) => x(point.year)).y((point) => y(point.count))
    for (const series of lineData) {
      plot.append('path')
        .datum(series.values)
        .attr('fill', 'none')
        .attr('stroke', series.color)
        .attr('stroke-width', aggregate ? 2.8 : 2.1)
        .attr('d', path)
      plot.selectAll<SVGCircleElement, (typeof series.values)[number]>(`.point-${lineData.indexOf(series)}`)
        .data(series.values)
        .join('circle')
        .attr('class', `point-${lineData.indexOf(series)}`)
        .attr('cx', (point) => x(point.year))
        .attr('cy', (point) => y(point.count))
        .attr('r', 2.3)
        .attr('fill', series.color)
        .append('title')
        .text((point) => `${point.year}${point.year === 2026 ? ' · partial year' : ''}: ${point.count.toLocaleString()} ${series.name.toLowerCase()} planet records`)
    }
    plot.append('line').attr('x1', x(2026)).attr('x2', x(2026)).attr('y1', 0).attr('y2', plotHeight)
      .attr('stroke', 'var(--accent-amber)').attr('stroke-dasharray', '4 5').attr('stroke-width', 1.3)
    plot.append('text').attr('x', x(2026) - 4).attr('y', 13).attr('text-anchor', 'end')
      .attr('fill', 'var(--accent-amber)').attr('font-size', 10).attr('font-family', 'var(--font-mono)').text('2026 partial')
    svg.attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet')
  }, [timeline, selectedMethods])
  const title = selectedMethods.length ? `Yearly catalogue counts for ${selectedMethods.join(', ')}` : 'Total yearly confirmed-planet catalogue records'
  return <svg ref={ref} className={styles.chart} role="img" aria-label={`${title}, 1992 through 2026. 1993 has zero catalogue records. 2026 is marked as a partial year.`} />
}

export function DistributionChart({ data }: { data: DiscoveryDistributions }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    const svg = select(ref.current)
    svg.selectAll('*').remove()
    const rows = data.distributions
    const width = 900
    const height = Math.max(245, rows.length * 46 + 82)
    const margin = { top: 15, right: 92, bottom: 52, left: 238 }
    const plotWidth = width - margin.left - margin.right
    const plotHeight = height - margin.top - margin.bottom
    const available = rows.flatMap((row) => [row.minimum, row.maximum]).filter((value): value is number => value !== null && Number.isFinite(value))
    let domain = extent(available) as [number | undefined, number | undefined]
    if (data.axis_scale === 'log') {
      const positive = available.filter((value) => value > 0)
      domain = extent(positive) as [number | undefined, number | undefined]
    }
    let minValue = domain[0] ?? 0
    let maxValue = domain[1] ?? (data.axis_scale === 'log' ? 1 : 1)
    if (data.axis_scale === 'log') {
      minValue = Math.max(Number.MIN_VALUE, minValue)
      if (minValue === maxValue) { minValue /= 1.3; maxValue *= 1.3 }
      else { minValue /= 1.12; maxValue *= 1.12 }
    } else if (minValue === maxValue) {
      const pad = Math.abs(minValue) * 0.12 || 0.1
      minValue -= pad
      maxValue += pad
    } else {
      const pad = (maxValue - minValue) * 0.08
      minValue -= pad
      maxValue += pad
    }
    const x = data.axis_scale === 'log'
      ? scaleLog<number, number>().domain([minValue, maxValue]).range([0, plotWidth]).clamp(true)
      : scaleLinear<number, number>().domain([minValue, maxValue]).range([0, plotWidth]).nice()
    const y = scaleBand<string>().domain(rows.map((row) => row.discovery_method)).range([0, plotHeight]).padding(0.35)
    const plot = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    plot.append('g').attr('class', styles.chartGrid).call(axisBottom(x).ticks(5).tickSize(plotHeight).tickFormat(() => ''))
    plot.append('g').attr('class', styles.chartAxis).call(axisLeft(y).tickSize(0))
    plot.append('g').attr('class', styles.chartAxis).attr('transform', `translate(0,${plotHeight})`)
      .call(axisBottom(x).ticks(5).tickFormat((value) => Number(value).toLocaleString(undefined, { maximumSignificantDigits: 3 })))
    rows.forEach((row, index) => {
      const center = (y(row.discovery_method) ?? 0) + y.bandwidth() / 2
      if (row.measured_count < 5) {
        const offsets = [-5, 0, 5]
        plot.selectAll<SVGCircleElement, (typeof row.observations)[number]>(`.raw-${index}`)
          .data(row.observations)
          .join('circle')
          .attr('class', `raw-${index}`)
          .attr('cx', (item) => x(data.axis_scale === 'log' ? Math.max(item.value, minValue) : item.value))
          .attr('cy', (_item, pointIndex) => center + offsets[pointIndex % offsets.length])
          .attr('r', 4)
          .attr('fill', palette[index % palette.length])
          .append('title')
          .text((item) => `${row.discovery_method}: ${item.pl_name}, ${data.label.toLowerCase()} ${item.value} ${data.unit}`)
      } else if (row.minimum !== null && row.maximum !== null && row.q1 !== null && row.q3 !== null && row.median !== null) {
        const color = palette[index % palette.length]
        plot.append('line').attr('x1', x(row.minimum)).attr('x2', x(row.maximum)).attr('y1', center).attr('y2', center)
          .attr('stroke', color).attr('stroke-width', 1.5)
        plot.append('line').attr('x1', x(row.minimum)).attr('x2', x(row.minimum)).attr('y1', center - 5).attr('y2', center + 5)
          .attr('stroke', color).attr('stroke-width', 1.5)
        plot.append('line').attr('x1', x(row.maximum)).attr('x2', x(row.maximum)).attr('y1', center - 5).attr('y2', center + 5)
          .attr('stroke', color).attr('stroke-width', 1.5)
        plot.append('rect').attr('x', x(row.q1)).attr('y', center - 8).attr('width', Math.max(1, x(row.q3) - x(row.q1))).attr('height', 16)
          .attr('fill', color).attr('fill-opacity', 0.26).attr('stroke', color)
        plot.append('line').attr('x1', x(row.median)).attr('x2', x(row.median)).attr('y1', center - 9).attr('y2', center + 9)
          .attr('stroke', color).attr('stroke-width', 2)
        plot.append('title').text(`${row.discovery_method}: n=${row.measured_count.toLocaleString()}, median ${row.median} ${data.unit}, Q1–Q3 ${row.q1}–${row.q3}`)
      }
      plot.append('text').attr('x', plotWidth + 12).attr('y', center + 4).attr('fill', row.measured_count < 5 ? 'var(--accent-amber)' : 'var(--color-muted)')
        .attr('font-size', 10).attr('font-family', 'var(--font-mono)').text(`n=${row.measured_count}`)
    })
    plot.append('text')
      .attr('class', styles.chartAxisLabel)
      .attr('x', plotWidth / 2)
      .attr('y', plotHeight + 43)
      .attr('text-anchor', 'middle')
      .text(`${data.label} (${data.unit}) · ${data.axis_scale === 'log' ? 'logarithmic' : 'linear'} scale`)
    svg.attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet')
  }, [data])
  return <svg ref={ref} className={styles.chart} role="img" aria-label={`${data.label} distribution by discovery method in ${data.unit} on a ${data.axis_scale === 'log' ? 'logarithmic' : 'linear'} scale. Boxes show Q1, median, Q3, and range when at least five measurements are available; smaller groups show raw observations.`} />
}

export function MissingnessChart({ data }: { data: DiscoveryDistributions }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    const svg = select(ref.current)
    svg.selectAll('*').remove()
    const rows = data.distributions
    const width = 900
    const height = Math.max(300, rows.length * 29 + 66)
    const margin = { top: 15, right: 115, bottom: 40, left: 238 }
    const plotWidth = width - margin.left - margin.right
    const plotHeight = height - margin.top - margin.bottom
    const x = scaleLinear().domain([0, 100]).range([0, plotWidth])
    const y = scaleBand<string>().domain(rows.map((row) => row.discovery_method)).range([0, plotHeight]).padding(0.22)
    const plot = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    plot.append('g').attr('class', styles.chartAxis).call(axisLeft(y).tickSize(0))
    plot.append('g').attr('class', styles.chartGrid).attr('transform', `translate(0,${plotHeight})`)
      .call(axisBottom(x).tickValues([0, 25, 50, 75, 100]).tickFormat((value) => `${value}%`))
    rows.forEach((row) => {
      const total = row.total_planet_records || 1
      const measured = row.measured_count / total * 100
      const top = y(row.discovery_method) ?? 0
      plot.append('rect').attr('x', 0).attr('y', top).attr('width', x(measured)).attr('height', y.bandwidth())
        .attr('fill', 'var(--accent-teal)').attr('fill-opacity', 0.8)
        .append('title').text(`${row.discovery_method}: ${row.measured_count.toLocaleString()} measured out of ${row.total_planet_records.toLocaleString()} records`)
      plot.append('rect').attr('x', x(measured)).attr('y', top).attr('width', x(row.missing_count / total * 100)).attr('height', y.bandwidth())
        .attr('fill', 'var(--accent-coral)').attr('fill-opacity', 0.86)
        .append('title').text(`${row.discovery_method}: ${row.missing_count.toLocaleString()} missing out of ${row.total_planet_records.toLocaleString()} records`)
      plot.append('text').attr('x', plotWidth + 10).attr('y', top + y.bandwidth() / 2 + 4)
        .attr('fill', 'var(--color-muted)').attr('font-size', 10).attr('font-family', 'var(--font-mono)')
        .text(`${row.measured_count}/${row.total_planet_records}`)
    })
    svg.attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet')
  }, [data])
  return <svg ref={ref} className={styles.chart} role="img" aria-label={`${data.label} measurement availability by discovery method. Teal is measured and coral is missing, with counts shown as measured over all planet records in each method.`} />
}

export function FacilitiesChart({ data }: { data: DiscoveryFacilities }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    const svg = select(ref.current)
    svg.selectAll('*').remove()
    const rows = data.facilities.slice(0, 12)
    const width = 760
    const height = Math.max(260, rows.length * 27 + 58)
    const margin = { top: 8, right: 112, bottom: 42, left: 215 }
    const plotWidth = width - margin.left - margin.right
    const plotHeight = height - margin.top - margin.bottom
    const x = scaleLinear().domain([0, max(rows, (row) => row.planet_count) ?? 1]).nice().range([0, plotWidth])
    const y = scaleBand<string>().domain(rows.map((row) => row.facility)).range([0, plotHeight]).padding(0.25)
    const plot = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    plot.append('g').attr('class', styles.chartAxis).call(axisLeft(y).tickSize(0))
    plot.append('g').attr('class', styles.chartGrid).attr('transform', `translate(0,${plotHeight})`)
      .call(axisBottom(x).ticks(4).tickFormat((value) => Number(value).toLocaleString()))
    plot.selectAll<SVGRectElement, (typeof rows)[number]>('rect').data(rows).join('rect')
      .attr('x', 0).attr('y', (row) => y(row.facility) ?? 0).attr('height', y.bandwidth())
      .attr('width', (row) => x(row.planet_count)).attr('fill', 'var(--accent-blue-muted)')
      .append('title').text((row) => `${row.facility}: ${row.planet_count.toLocaleString()} records, ${row.percentage.toFixed(2)}% of denominator ${data.denominator_planet_records.toLocaleString()}`)
    plot.selectAll<SVGTextElement, (typeof rows)[number]>('.facility-value').data(rows).join('text')
      .attr('class', 'facility-value').attr('x', (row) => x(row.planet_count) + 7)
      .attr('y', (row) => (y(row.facility) ?? 0) + y.bandwidth() / 2 + 4)
      .attr('fill', 'var(--color-muted)').attr('font-size', 10).attr('font-family', 'var(--font-mono)')
      .text((row) => `${row.planet_count.toLocaleString()} · ${row.percentage.toFixed(1)}%`)
    svg.attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio', 'xMidYMid meet')
  }, [data])
  return <svg ref={ref} className={styles.chart} role="img" aria-label={`Planet-record counts for the twelve most represented catalogue facilities out of ${data.facility_count} facilities.`} />
}

