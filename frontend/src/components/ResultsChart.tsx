import { useLayoutEffect, useRef } from 'react'
import { gsap, prefersReducedMotion } from '../lib/motion'
import { HYBRID_GAIN, RESULTS, TEST_PRS } from '../lib/research'

// ROC-AUC of every method on the same test PRs, as a dot plot from 0.5 (coin toss) to 0.9.
const MIN = 0.5
const MAX = 0.9
const pct = (v: number) => ((v - MIN) / (MAX - MIN)) * 100

export default function ResultsChart({ animate = false }: { animate?: boolean }) {
  const root = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    if (!animate || !root.current || prefersReducedMotion()) return
    const ctx = gsap.context(() => {
      gsap.from('[data-auc-line]', {
        width: 0, duration: 1.1, ease: 'power3.out', stagger: 0.07,
        scrollTrigger: { trigger: root.current, start: 'top 75%', once: true },
      })
      gsap.from('[data-auc-dot], [data-auc-value]', {
        left: '0%', duration: 1.1, ease: 'power3.out', stagger: 0.07,
        scrollTrigger: { trigger: root.current, start: 'top 75%', once: true },
      })
    }, root)
    return () => ctx.revert()
  }, [animate])

  return (
    <figure ref={root} className="w-full">
      <ol className="space-y-3.5">
        {RESULTS.map((r) => {
          const lead = r.kind === 'hybrid'
          return (
            <li key={r.name} className="grid grid-cols-[8.5rem_1fr] items-center gap-4 sm:grid-cols-[11rem_1fr]">
              <div className="text-right leading-tight">
                <div className={lead ? 'font-semibold text-ink' : 'text-ink'}>{r.name}</div>
                <div className="text-xs text-graphite">{r.detail}</div>
              </div>
              <div className="relative h-7">
                <div className="absolute top-1/2 right-0 left-0 h-px bg-rule" />
                <div data-auc-line="" className={`absolute top-1/2 left-0 h-px ${lead ? 'bg-ink' : 'bg-graphite/50'}`} style={{ width: `${pct(r.auc)}%` }} />
                <div
                  data-auc-dot=""
                  className={`absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ${lead ? 'bg-ink ring-4 ring-ink/15' : 'bg-graphite'}`}
                  style={{ left: `${pct(r.auc)}%` }}
                />
                <span
                  data-auc-value=""
                  className={`absolute top-1/2 -translate-y-1/2 pl-3 text-sm ${lead ? 'font-semibold text-ink' : 'text-graphite'}`}
                  style={{ left: `${pct(r.auc)}%` }}
                >
                  {r.auc.toFixed(3)}
                </span>
              </div>
            </li>
          )
        })}
      </ol>
      <div className="mt-2 grid grid-cols-[8.5rem_1fr] gap-4 sm:grid-cols-[11rem_1fr]">
        <div />
        <div className="relative h-5 text-xs text-graphite">
          <span className="absolute left-0">0.5, a coin toss</span>
          <span className="absolute right-0">0.9</span>
        </div>
      </div>
      <figcaption className="mt-5 max-w-lg text-sm leading-relaxed text-graphite">
        ROC-AUC on {TEST_PRS} pull requests the models never saw during training: the chance that a PR which later
        needed a fix is ranked above one that did not. The hybrid beats size alone by {HYBRID_GAIN.mean.toFixed(3)}
        {' '}(95% range {HYBRID_GAIN.low.toFixed(3)} to {HYBRID_GAIN.high.toFixed(3)}): a real gain, but a small one.
      </figcaption>
    </figure>
  )
}
