import { useLayoutEffect, useMemo, useRef, type ReactNode } from 'react'
import { Link } from 'react-router'
import ResultsChart from '../components/ResultsChart'
import SiteFooter from '../components/SiteFooter'
import SiteHeader from '../components/SiteHeader'
import StoryMap from '../components/StoryMap'
import { Skeleton } from '../components/states'
import { startLogin } from '../lib/api'
import { DEMO_PATH, DEMO_REPO } from '../lib/config'
import { gsap, prefersReducedMotion, useSmoothScroll } from '../lib/motion'
import { RESULTS, TEST_PRS } from '../lib/research'
import { storyStats } from '../lib/storyStats'
import type { MapPoint, Repo, ScoreMap } from '../lib/types'
import { useApi } from '../lib/useApi'
import { useDocumentTitle } from '../lib/useDocumentTitle'

const auc = (name: string) => RESULTS.find((r) => r.name === name)?.auc.toFixed(3) ?? ''

export default function Landing() {
  useDocumentTitle(null)
  useSmoothScroll()
  const map = useApi<ScoreMap>(`/repos/${DEMO_REPO}/score-map`)
  const repos = useApi<Repo[]>('/repos')
  const demo = repos.data?.find((r) => r.full_name === DEMO_REPO)
  const hero = useRef<HTMLElement>(null)

  // The one orchestrated moment on load: the headline rises line by line.
  useLayoutEffect(() => {
    if (!hero.current || prefersReducedMotion()) return
    const ctx = gsap.context(() => {
      gsap.timeline({ defaults: { ease: 'power4.out' } })
        .from('[data-line]', { yPercent: 110, duration: 1.1, stagger: 0.09 })
        .from('[data-fade]', { opacity: 0, y: 16, duration: 0.8, stagger: 0.08 }, '-=0.6')
    }, hero)
    return () => ctx.revert()
  }, [])

  return (
    <div className="min-h-screen">
      <SiteHeader overlay />
      <main>
        <section ref={hero} className="mx-auto flex min-h-[92svh] max-w-6xl flex-col justify-center px-6 pt-28 pb-16">
          <h1 className="max-w-5xl text-[clamp(2.75rem,8vw,6.5rem)] leading-[0.98] font-semibold tracking-[-0.045em] text-ink">
            {['Which pull requests', 'deserve a second look?'].map((line, i) => (
              <span key={line} className="block overflow-hidden pb-[0.06em]">
                <span data-line="" className="block">
                  {line}
                  {i === 0 && ' '}
                </span>
              </span>
            ))}
          </h1>
          <p data-fade="" className="mt-8 max-w-xl text-lg leading-relaxed text-graphite sm:text-xl">
            PR Risk ranks pull requests two ways, by their size and by an LLM that reads the diff alongside the
            project's own documentation, then checks both against the fixes that actually followed.
          </p>
          <div data-fade="" className="mt-10 flex flex-wrap items-center gap-3">
            <Link to={DEMO_PATH} className="rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-signal">
              Open the {DEMO_REPO} demo
            </Link>
            <button onClick={() => startLogin('/repos')} className="rounded-full px-6 py-3 text-sm font-semibold text-ink ring-1 ring-ink/20 transition-colors hover:bg-surface">
              Log in with GitHub
            </button>
          </div>
          <dl data-fade="" className="mt-16 grid max-w-2xl grid-cols-3 gap-6 border-t border-rule pt-6 text-sm">
            <Fact label="Pull requests collected" value={demo ? demo.pr_count.toLocaleString() : '1,805'} />
            <Fact label="Read by the LLM" value={demo ? demo.llm_analyzed_count.toLocaleString() : '390'} />
            <Fact label="Best ROC-AUC" value={auc('Hybrid')} />
          </dl>
        </section>

        <Story points={map.data?.points ?? null} failed={!!map.error} />

        <section className="border-t border-rule bg-surface">
          <div className="mx-auto grid max-w-6xl gap-14 px-6 py-24 lg:grid-cols-[0.8fr_1.2fr] lg:items-start">
            <div>
              <h2 className="text-4xl leading-tight font-semibold tracking-[-0.03em] text-ink">Six ways to rank the same pull requests</h2>
              <p className="mt-5 max-w-md leading-relaxed text-graphite">
                Every method scored the same {TEST_PRS} unseen PRs. Machine learning on seven metrics did no better than counting
                lines; the LLM only caught up once it could read the docs; combining size with the LLM came out on top.
              </p>
            </div>
            <ResultsChart animate />
          </div>
        </section>

        <Pipeline />

        <section className="mx-auto max-w-6xl px-6 py-24">
          <h2 className="text-4xl font-semibold tracking-[-0.03em] text-ink">What the score is not</h2>
          <div className="mt-10 grid gap-10 md:grid-cols-3">
            <Limit title="Not a bug detector">
              The label counts later fixes to the same files within 60 days. It shows corrective work followed a PR, not
              that the PR caused it.
            </Limit>
            <Limit title="One repository">
              Every number here comes from encode/httpx, an HTTP library: 1,805 pull requests, 1,295 of them merged.
              Other projects may behave differently.
            </Limit>
            <Limit title="A small gain">
              The hybrid beats size alone by 0.039 ROC-AUC, and the low end of its 95% range is close to zero. Treat it as
              a second opinion, not a verdict.
            </Limit>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 pb-24">
          <div className="flex flex-col items-start justify-between gap-8 rounded-[2rem] bg-ink px-8 py-12 text-white sm:px-12 md:flex-row md:items-center">
            <div>
              <h2 className="text-3xl font-semibold tracking-[-0.02em]">See every pull request, ranked</h2>
              <p className="mt-2 max-w-lg text-white/70">Open the demo to sort {demo ? demo.pr_count.toLocaleString() : '1,805'} pull requests, explore the risk map and read why the model flagged each one.</p>
            </div>
            <Link to={DEMO_PATH} className="shrink-0 rounded-full bg-white px-6 py-3 text-sm font-semibold text-ink transition-colors hover:bg-paper">
              Open the demo
            </Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  )
}

function Story({ points, failed }: { points: MapPoint[] | null; failed: boolean }) {
  const track = useRef<HTMLOListElement>(null)
  const stats = useMemo(() => {
    if (!points) return null
    const known = points.filter((p) => p.hindsight === 'fix' || p.hindsight === 'no_fix')
    const { topIds } = storyStats(points)
    const rate = (list: MapPoint[]) => (list.length ? Math.round((list.filter((p) => p.hindsight === 'fix').length / list.length) * 100) : 0)
    return { all: rate(known), top: rate(known.filter((p) => topIds.has(p.number))), fixes: known.filter((p) => p.hindsight === 'fix').length, known: known.length }
  }, [points])

  const steps = [
    { title: 'Start with size', body: `Each dot is a pull request, placed left to right by how many lines it changed. Size alone ranks risky PRs well: ROC-AUC ${auc('Size rule')}.` },
    { title: 'Let an LLM read the diff', body: `Gemini reads each diff with the four sections of the project's documentation closest in meaning to it, and rates the risk. The dots rise by its score. On its own it reaches ${auc('LLM with docs')}.` },
    { title: 'Average the two', body: 'The hybrid is the mean of both percentiles. PRs with equal hybrid scores sit on the same diagonal, so the top-right corner is where both signals are worried.' },
    { title: 'Check against what happened', body: `Red rings are the ${stats?.fixes ?? ''} pull requests where a later fix changed the same files within 60 days. The models never see this; it is only used to grade their scores.` },
    { title: 'Rank by the hybrid', body: stats ? `In the top tenth by hybrid score, ${stats.top}% were followed by a fix, against ${stats.all}% of all ${stats.known} with a known outcome.` : 'The top tenth by hybrid score holds far more of the pull requests that were followed by a fix.' },
  ]

  return (
    <section aria-labelledby="story-title" className="border-t border-rule">
      <div className="mx-auto max-w-6xl px-6 pt-24">
        <h2 id="story-title" className="max-w-2xl text-4xl leading-tight font-semibold tracking-[-0.03em] text-ink">
          How {DEMO_REPO}'s pull requests get their score
        </h2>
      </div>
      <div className="mx-auto grid max-w-6xl gap-x-16 px-6 pb-24 lg:grid-cols-[1fr_minmax(0,540px)]">
        <div className="sticky top-0 z-10 -mx-6 border-b border-rule bg-paper px-6 py-3 lg:static lg:order-2 lg:m-0 lg:border-0 lg:bg-transparent lg:p-0">
          <div className="lg:sticky lg:top-[12vh]">
            {points ? (
              <StoryMap points={points} track={track} steps={steps.length} />
            ) : failed ? (
              <p className="py-16 text-sm text-graphite">The map could not be loaded. The demo has the same data.</p>
            ) : (
              <Skeleton className="aspect-square w-full" />
            )}
          </div>
        </div>
        <ol ref={track} className="lg:order-1">
          {steps.map((s, i) => (
            <li key={s.title} className="flex min-h-[70vh] flex-col justify-center py-10 lg:min-h-[85vh]">
              <span className="text-sm font-medium text-graphite">Step {i + 1} of {steps.length}</span>
              <h3 className="mt-3 text-3xl font-semibold tracking-[-0.02em] text-ink">{s.title}</h3>
              <p className="mt-4 max-w-md text-lg leading-relaxed text-graphite">{s.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

function Pipeline() {
  const root = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    if (!root.current || prefersReducedMotion()) return
    const ctx = gsap.context(() => {
      gsap.from('[data-rail]', { scaleX: 0, transformOrigin: 'left center', ease: 'none', scrollTrigger: { trigger: root.current, start: 'top 70%', end: 'center 50%', scrub: 0.5 } })
    }, root)
    return () => ctx.revert()
  }, [])

  const stages = [
    { title: 'Collect', body: 'Pull requests, commits and changed files from the GitHub API, stored in PostgreSQL.' },
    { title: 'Measure', body: 'Seven numbers per PR: files and lines changed, commits, test files, sensitive files.' },
    { title: 'Read', body: 'Gemini reads the diff with the closest documentation sections, found with pgvector.' },
    { title: 'Combine', body: 'The size and LLM percentiles are averaged into one hybrid score, fixed in advance.' },
    { title: 'Grade', body: 'Scores are compared with the fixes that followed, on PRs the models never saw.' },
  ]
  return (
    <section ref={root} className="mx-auto max-w-6xl px-6 py-24">
      <h2 className="text-4xl font-semibold tracking-[-0.03em] text-ink">From a GitHub repository to a ranked list</h2>
      <div className="relative mt-14">
        <div className="absolute top-[0.6rem] right-0 left-0 hidden h-px bg-rule md:block" />
        <div data-rail="" className="absolute top-[0.6rem] right-0 left-0 hidden h-px bg-ink md:block" />
        <ol className="relative grid gap-10 md:grid-cols-5 md:gap-6">
          {stages.map((s, i) => (
            <li key={s.title}>
              <span className="relative z-10 flex size-5 items-center justify-center rounded-full bg-paper ring-2 ring-ink">
                <span className="size-1.5 rounded-full bg-ink" />
              </span>
              <p className="mt-5 text-sm text-graphite">{i + 1}</p>
              <h3 className="text-lg font-semibold text-ink">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-graphite">{s.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-graphite">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tracking-tight text-ink">{value}</dd>
    </div>
  )
}

function Limit({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="border-t-2 border-ink pt-5">
      <h3 className="text-lg font-semibold text-ink">{title}</h3>
      <p className="mt-2 leading-relaxed text-graphite">{children}</p>
    </div>
  )
}
