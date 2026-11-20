import { useLayoutEffect, useMemo, useRef, type RefObject } from 'react'
import { MAP_SIZE, PAD, PLOT_H, PLOT_W, diagonal, mx, my, regionAbove } from '../lib/mapGeometry'
import { gsap, prefersReducedMotion } from '../lib/motion'
import { storyStats } from '../lib/storyStats'
import type { MapPoint } from '../lib/types'

/**
 * The risk map that builds itself as the visitor scrolls through the five story steps.
 * The JSX below is the FINAL picture; when motion is allowed, GSAP first winds it back to
 * "size only" and then plays it forward, scrubbed by the scroll position of `track`.
 */
export default function StoryMap({ points, track, steps }: {
  points: MapPoint[]
  track: RefObject<HTMLElement | null>
  steps: number
}) {
  const svg = useRef<SVGSVGElement>(null)
  const { topCut, topIds } = useMemo(() => storyStats(points), [points])
  const d = [25, 50, 75].map((s) => ({ s, ...diagonal(s) }))

  useLayoutEffect(() => {
    if (!svg.current || !track.current || prefersReducedMotion()) return
    const root = svg.current
    const ctx = gsap.context(() => {
      const dots = gsap.utils.toArray<SVGCircleElement>('[data-dot]', root)
      const rings = dots.filter((c) => c.dataset.fix === '1')
      const quiet = dots.filter((c) => c.dataset.fix !== '1' && c.dataset.top !== '1')

      // Step 1 state: every PR on the middle line, placed by size only
      gsap.set(dots, { attr: { cy: my(50), r: 3.2 }, fillOpacity: 0.42, strokeOpacity: 0 })
      gsap.set('[data-layer="yaxis"], [data-layer="diag"], [data-layer="region"]', { opacity: 0 })

      const tl = gsap.timeline({
        defaults: { ease: 'power2.inOut' },
        scrollTrigger: { trigger: track.current, start: 'top 55%', end: 'bottom 75%', scrub: 0.6 },
      })
      const u = 1 / steps // one step of the story
      tl.to(dots, { attr: { cy: (_i: number, el: SVGCircleElement) => Number(el.dataset.cy) }, duration: u * 0.8, stagger: { amount: u * 0.4, from: 'random' } }, u * 0.6)
        .to('[data-layer="yaxis"]', { opacity: 1, duration: u * 0.4 }, u * 0.8)
        .to('[data-layer="diag"]', { opacity: 1, duration: u * 0.6, stagger: u * 0.15 }, u * 2)
        .to(rings, { attr: { r: 5 }, fillOpacity: 0, strokeOpacity: 1, duration: u * 0.6, stagger: { amount: u * 0.3 } }, u * 3)
        .to('[data-layer="region"]', { opacity: 1, duration: u * 0.5 }, u * 4)
        .to(quiet, { fillOpacity: 0.16, duration: u * 0.5 }, u * 4)
    }, root)
    return () => ctx.revert()
  }, [points, track, steps])

  return (
    <svg
      ref={svg}
      viewBox={`0 0 ${MAP_SIZE} ${MAP_SIZE}`}
      className="h-auto w-full"
      role="img"
      aria-label={`Risk map of ${points.length} pull requests read by the LLM, placed by size and by the LLM's score.`}
    >
      <polygon data-layer="region" points={regionAbove(topCut)} fill="var(--color-signal)" fillOpacity=".07" />
      {d.map(({ s, x1, y1, x2, y2 }) => (
        <g key={s} data-layer="diag">
          <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--color-ink)" strokeOpacity=".12" />
          <text x={x2 - 6} y={y2 - 6} textAnchor="end" className="fill-graphite text-[10px]">hybrid {s}</text>
        </g>
      ))}
      <rect x={PAD.left} y={PAD.top} width={PLOT_W} height={PLOT_H} fill="none" stroke="var(--color-rule)" />
      {[0, 50, 100].map((t) => (
        <text key={t} x={mx(t)} y={MAP_SIZE - 18} textAnchor="middle" className="fill-graphite text-[11px]">{t}</text>
      ))}
      <text x={PAD.left + PLOT_W / 2} y={MAP_SIZE - 2} textAnchor="middle" className="fill-ink text-[12px] font-medium">
        Size percentile
      </text>
      <g data-layer="yaxis">
        {[0, 50, 100].map((t) => (
          <text key={t} x={PAD.left - 8} y={my(t) + 4} textAnchor="end" className="fill-graphite text-[11px]">{t}</text>
        ))}
        <text transform={`translate(12 ${PAD.top + PLOT_H / 2}) rotate(-90)`} textAnchor="middle" className="fill-ink text-[12px] font-medium">
          LLM percentile
        </text>
      </g>
      {[...points]
        .sort((a, b) => Number(a.hindsight === 'fix') - Number(b.hindsight === 'fix'))
        .map((p) => {
          const fix = p.hindsight === 'fix'
          const top = topIds.has(p.number)
          return (
            <circle
              key={p.number}
              data-dot=""
              data-fix={fix ? '1' : '0'}
              data-top={top ? '1' : '0'}
              data-cy={my(p.llm_percentile)}
              cx={mx(p.size_percentile)}
              cy={my(p.llm_percentile)}
              r={fix ? 5 : 3.2}
              fill="var(--color-ink)"
              fillOpacity={fix ? 0 : top ? 0.55 : 0.16}
              stroke="var(--color-fix)"
              strokeWidth={1.8}
              strokeOpacity={fix ? 1 : 0}
            />
          )
        })}
    </svg>
  )
}
