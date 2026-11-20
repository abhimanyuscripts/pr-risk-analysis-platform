import type { Hybrid, Label, LLMScore } from '../lib/types'

// Predictions are filled; hindsight (what happened later) is only ever outlined.

const LEVEL: Record<string, string> = {
  low: 'bg-calm/10 text-calm',
  medium: 'bg-amber/12 text-amber',
  high: 'bg-fix/10 text-fix',
}

export function LLMBadge({ llm }: { llm: LLMScore | null }) {
  if (!llm) return <span className="text-graphite/60">—</span>
  return (
    <span className={`inline-flex items-baseline gap-1.5 rounded-full px-2.5 py-0.5 text-xs ${LEVEL[llm.risk_level] ?? 'bg-ink/5 text-ink'}`}>
      <span className="font-semibold">{llm.risk_score}</span>
      <span>{llm.risk_level}</span>
    </span>
  )
}

/** The label is hindsight (did a fix touch the same files within 60 days?), never a prediction. */
export function LabelBadge({ label }: { label: Label | null }) {
  if (!label) return <span className="text-graphite/60">—</span>
  if (!label.window_complete)
    return (
      <span className="text-xs text-graphite" title="Fewer than 60 days of later history, so not known yet">
        pending
      </span>
    )
  return label.is_risky ? (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap text-fix ring-1 ring-fix/60 ring-inset">
      <span className="size-1.5 rounded-full ring-[1.5px] ring-fix" aria-hidden="true" />
      fix followed
    </span>
  ) : (
    <span className="rounded-full px-2.5 py-0.5 text-xs whitespace-nowrap text-graphite ring-1 ring-rule ring-inset">no fix</span>
  )
}

export function HybridBar({ hybrid }: { hybrid: Hybrid | null }) {
  if (!hybrid) return <span className="text-xs text-graphite/70" title="Needs an LLM answer and metrics">not scored</span>
  const tip = `Size percentile ${hybrid.size_percentile}, LLM percentile ${hybrid.llm_percentile}, against ${hybrid.reference_prs} analysed PRs`
  return (
    <div className="flex items-center gap-3" title={tip}>
      <div className="relative h-1.5 w-24 rounded-full bg-ink/8">
        <div className="absolute inset-y-0 left-0 rounded-full bg-ink" style={{ width: `${hybrid.score}%` }} />
      </div>
      <span className="w-7 text-right text-sm font-semibold text-ink">{Math.round(hybrid.score)}</span>
    </div>
  )
}
