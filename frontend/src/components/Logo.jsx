export default function Logo({ size = 28 }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="8" className="fill-raised" />
        <path d="M4 19 L10 19 L13 9 L18 24 L21 15 L28 15" fill="none" stroke="rgb(var(--amber))" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="font-display text-lg font-semibold tracking-tight">Stima Insight</span>
    </span>
  );
}
