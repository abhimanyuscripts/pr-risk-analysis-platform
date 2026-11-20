import { useState } from 'react'
import { useNavigate } from 'react-router'
import { MAP_SIZE as SIZE, PAD, PLOT_H as H, PLOT_W as W, diagonal, mx as x, my as y } from '../lib/mapGeometry'
import type { MapPoint } from '../lib/types'

// The risk map: every analysed PR placed by its two percentiles. The hybrid is their average,
// so PRs with the same hybrid score sit on the same diagonal (the faint lines).
// Filled dot = the model's view; red ring = a fix followed later (hindsight).

export default function ScoreMap({ points, repoPath }: { points: MapPoint[]; repoPath: string }) {
  const navigate = useNavigate()
  const [hover, setHover] = useState<MapPoint | null>(null)
  const fixes = points.filter((p) => p.hindsight === 'fix').length
  const ordered = [...points].sort((a, b) => Number(a.hindsight === 'fix') - Number(b.hindsight === 'fix'))

  return (
    <figure>
      <div className="relative">
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="w-full max-w-[560px]"
          role="img"
          aria-label={`Risk map of ${points.length} analysed pull requests; ${fixes} had a fix follow.`}
        >
          {/* hybrid score diagonals: size% + llm% = 2 x score */}
          {[25, 50, 75].map((s) => {
            const l = diagonal(s)
            return (
              <g key={s}>
                <line x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke="var(--color-ink)" strokeOpacity=".09" strokeWidth="1" />
                <text x={l.x2 - 6} y={l.y2 - 6} textAnchor="end" className="fill-graphite text-[10px]">hybrid {s}</text>
              </g>
            )
          })}
          <rect x={PAD.left} y={PAD.top} width={W} height={H} fill="none" stroke="var(--color-rule)" />
          {[0, 50, 100].map((t) => (
            <g key={t} className="fill-graphite text-[11px]">
              <text x={x(t)} y={SIZE - 18} textAnchor="middle">{t}</text>
              <text x={PAD.left - 8} y={y(t) + 4} textAnchor="end">{t}</text>
            </g>
          ))}
          <text x={PAD.left + W / 2} y={SIZE - 2} textAnchor="middle" className="fill-ink text-[12px] font-medium">
            Size percentile (lines changed)
          </text>
          <text transform={`translate(12 ${PAD.top + H / 2}) rotate(-90)`} textAnchor="middle" className="fill-ink text-[12px] font-medium">
            LLM + docs percentile
          </text>
          {ordered.map((p, i) => {
            const fix = p.hindsight === 'fix'
            return (
              <circle
                key={p.number}
                data-pr={p.number}
                cx={x(p.size_percentile)}
                cy={y(p.llm_percentile)}
                r={fix ? 5 : 3.2}
                fill={fix ? 'none' : 'var(--color-ink)'}
                fillOpacity={fix ? undefined : 0.42}
                stroke={fix ? 'var(--color-fix)' : 'none'}
                strokeWidth={fix ? 1.8 : 0}
                className="cursor-pointer motion-safe:animate-[plot-in_.5s_ease-out_both]"
                pointerEvents="all" // rings have no fill; without this only their thin outline reacts to the mouse
                style={{ animationDelay: `${Math.min(i, 400) * 2}ms`, transformOrigin: `${x(p.size_percentile)}px ${y(p.llm_percentile)}px` }}
                onMouseEnter={() => setHover(p)}
                onMouseLeave={() => setHover(null)}
                onClick={() => navigate(`${repoPath}/prs/${p.number}`)}
              />
            )
          })}
          {hover && (
            <circle cx={x(hover.size_percentile)} cy={y(hover.llm_percentile)} r="9" fill="none" stroke="var(--color-signal)" strokeWidth="2" />
          )}
        </svg>
        {hover && (
          <div
            className="pointer-events-none absolute z-10 w-64 rounded-xl bg-ink px-3.5 py-2.5 text-xs text-white shadow-lg"
            style={{ left: `min(calc(${(x(hover.size_percentile) / SIZE) * 100}% + 12px), calc(100% - 16rem))`, top: `${(y(hover.llm_percentile) / SIZE) * 100}%` }}
          >
            <p className="font-semibold">#{hover.number} {hover.title}</p>
            <p className="mt-1 text-white/75">
              Hybrid {Math.round(hover.score)} from size {Math.round(hover.size_percentile)} and LLM {Math.round(hover.llm_percentile)}
              {hover.hindsight === 'fix' && '. A fix followed.'}
            </p>
          </div>
        )}
      </div>
      <figcaption className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-graphite">
        <span className="flex items-center gap-2"><span className="size-2 rounded-full bg-ink/45" />Analysed PR</span>
        <span className="flex items-center gap-2"><span className="size-2.5 rounded-full ring-[1.8px] ring-fix" />A fix followed ({fixes})</span>
        <span>Click a dot to open the PR.</span>
      </figcaption>
    </figure>
  )
}
