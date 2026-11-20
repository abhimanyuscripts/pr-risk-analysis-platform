import type { Hybrid, Label, LLMScore } from '../lib/types'

const LEVEL_STYLE: Record<string, string> = {
  low: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  medium: 'bg-amber-50 text-amber-800 ring-amber-200',
  high: 'bg-rose-50 text-rose-700 ring-rose-200',
}

export function LLMBadge({ llm }: { llm: LLMScore | null }) {
  if (!llm) return <span className="text-slate-400">—</span>
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs ring-1 ring-inset ${LEVEL_STYLE[llm.risk_level] ?? 'bg-slate-50 text-slate-700 ring-slate-200'}`}>
      <span className="font-medium tabular-nums">{llm.risk_score}</span>
      <span>{llm.risk_level}</span>
    </span>
  )
}

/** The label is hindsight (was there a fix within 60 days?), never a prediction. */
export function LabelBadge({ label }: { label: Label | null }) {
  if (!label) return <span className="text-slate-400">—</span>
  if (!label.window_complete)
    return <span className="text-xs text-slate-500" title="Fewer than 60 days of later history: not known yet">pending</span>
  return label.is_risky ? (
    <span className="rounded-md bg-rose-600 px-1.5 py-0.5 text-xs font-medium text-white">fix followed</span>
  ) : (
    <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">no fix</span>
  )
}

export function HybridBar({ hybrid }: { hybrid: Hybrid | null }) {
  if (!hybrid) return <span className="text-xs text-slate-400" title="Needs an LLM answer and metrics">not scored</span>
  const tip = `Size percentile ${hybrid.size_percentile} · LLM percentile ${hybrid.llm_percentile} · vs ${hybrid.reference_prs} analysed PRs`
  return (
    <div className="flex items-center gap-2" title={tip}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200">
        <div className="h-full rounded-full bg-slate-800" style={{ width: `${hybrid.score}%` }} />
      </div>
      <span className="w-8 text-right text-xs font-medium tabular-nums text-slate-900">{Math.round(hybrid.score)}</span>
    </div>
  )
}
