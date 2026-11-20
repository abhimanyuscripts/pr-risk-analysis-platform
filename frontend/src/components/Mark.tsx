/** The logo: two signals on a diagonal; the ring is the hindsight label. */
export default function Mark({ className = 'size-5' }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden="true">
      <path d="M3 17 17 3" stroke="currentColor" strokeOpacity=".25" strokeWidth="1.5" />
      <circle cx="6" cy="14" r="3" fill="currentColor" />
      <circle cx="14" cy="6" r="3" fill="none" stroke="var(--color-fix)" strokeWidth="1.8" />
    </svg>
  )
}
