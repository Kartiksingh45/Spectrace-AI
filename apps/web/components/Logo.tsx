const GRADIENT_ID = "spectrace-logo-gradient";

/** Icon + wordmark brand mark. The center dot is punched out in the page's own background color
 * (not a fixed dark shade) so the "hole" in the S-curve reads correctly on both light and dark
 * backgrounds - it only looks right when this sits directly on bg-background, not on a card or
 * the hero's own gradient. */
export function Logo({ size = "sm" }: { size?: "sm" | "lg" }) {
  const iconPx = size === "lg" ? 56 : 28;
  const textClass = size === "lg" ? "text-4xl" : "text-lg";
  const gapClass = size === "lg" ? "gap-4" : "gap-2";

  return (
    <span className={`inline-flex items-center ${gapClass}`}>
      <svg width={iconPx} height={iconPx} viewBox="0 0 100 100" fill="none" aria-hidden="true">
        <defs>
          <linearGradient id={GRADIENT_ID} gradientUnits="userSpaceOnUse" x1="78" y1="22" x2="22" y2="78">
            <stop offset="0" stopColor="#56d4e0" />
            <stop offset="1" stopColor="#ff9d4d" />
          </linearGradient>
        </defs>
        <path
          d="M70 22 L38 22 Q24 22 24 36 Q24 50 38 50 L62 50 Q76 50 76 64 Q76 78 62 78 L30 78"
          stroke={`url(#${GRADIENT_ID})`}
          strokeWidth="10"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="80" cy="22" r="7" fill="#56d4e0" />
        <circle cx="20" cy="78" r="7" fill="#ff9d4d" />
        <circle cx="50" cy="50" r="4" fill="rgb(var(--color-background))" stroke="#b9dbe0" strokeWidth="2.5" />
      </svg>
      <span
        className={`font-semibold ${textClass} tracking-tight text-ink`}
        style={{ fontFamily: "var(--font-logo)" }}
      >
        Spectrace<span className="ml-1 font-normal" style={{ color: "#56d4e0" }}>AI</span>
      </span>
    </span>
  );
}
