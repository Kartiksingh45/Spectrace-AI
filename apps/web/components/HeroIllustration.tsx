/** Original illustration (not a photo) for the landing page hero - a person at a laptop with
 * floating "evidence" cards, echoing the actual grounded-evidence workflow rather than generic
 * stock/AI imagery. Colors match the existing brand tokens (trace teal / accent blue). */
export function HeroIllustration() {
  return (
    <svg viewBox="0 0 1200 800" width="100%" height="100%" role="img" aria-label="Illustration of a developer at a laptop, with evidence and plan cards traced from the screen">
      <defs>
        <radialGradient id="glowTeal" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#2DBFBA" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#2DBFBA" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="glowBlue" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#3E6FA6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#3E6FA6" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="screenGlow" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2DBFBA" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#163150" stopOpacity="0.9" />
        </linearGradient>
      </defs>

      <circle cx="220" cy="160" r="260" fill="url(#glowBlue)" />
      <circle cx="980" cy="620" r="320" fill="url(#glowTeal)" />
      <circle cx="900" cy="140" r="180" fill="url(#glowTeal)" />

      <rect x="120" y="560" width="620" height="26" rx="8" fill="#0b1220" />
      <rect x="120" y="586" width="620" height="10" rx="4" fill="#0a0f1a" />

      <path d="M300 560 L300 470 Q300 440 335 440 L360 440 Q395 440 395 470 L395 560" fill="#101a2c" />

      <g>
        <path d="M295 560 L295 430 Q295 385 345 380 Q400 385 400 430 L405 560 Z" fill="#16233a" />
        <path
          d="M295 430 Q295 385 345 380 Q400 385 400 430"
          fill="none"
          stroke="#2DBFBA"
          strokeOpacity="0.35"
          strokeWidth="3"
        />
        <circle cx="348" cy="335" r="46" fill="#16233a" />
        <circle cx="348" cy="335" r="46" fill="none" stroke="#2DBFBA" strokeOpacity="0.35" strokeWidth="3" />
        <path d="M304 330 Q348 290 392 330 L392 320 Q348 278 304 320 Z" fill="#0e1727" />
        <path d="M300 470 Q360 500 430 512" fill="none" stroke="#16233a" strokeWidth="26" strokeLinecap="round" />
        <path d="M400 465 Q460 495 520 508" fill="none" stroke="#16233a" strokeWidth="26" strokeLinecap="round" />
      </g>

      <g>
        <rect x="420" y="500" width="230" height="14" rx="4" fill="#0a0f1a" />
        <path d="M410 500 L660 500 L648 560 L422 560 Z" fill="#101a2c" />
        <rect x="440" y="360" width="190" height="140" rx="10" fill="#0b1220" stroke="#213758" strokeWidth="4" />
        <rect x="452" y="372" width="166" height="116" rx="4" fill="url(#screenGlow)" />
        <g stroke="#e7fbfa" strokeOpacity="0.85" strokeWidth="3" strokeLinecap="round">
          <line x1="464" y1="390" x2="520" y2="390" />
          <line x1="464" y1="404" x2="560" y2="404" />
          <line x1="464" y1="418" x2="540" y2="418" />
          <line x1="480" y1="432" x2="600" y2="432" />
          <line x1="480" y1="446" x2="570" y2="446" />
          <line x1="464" y1="460" x2="530" y2="460" />
        </g>
      </g>

      <g fill="none" stroke="#2DBFBA" strokeOpacity="0.55" strokeWidth="2" strokeDasharray="4 6">
        <path d="M630 400 C 760 360, 820 300, 900 250" />
        <path d="M630 440 C 770 470, 840 500, 930 500" />
        <path d="M615 470 C 740 560, 800 610, 880 660" />
      </g>
      <circle cx="630" cy="400" r="4" fill="#2DBFBA" />
      <circle cx="630" cy="440" r="4" fill="#2DBFBA" />
      <circle cx="615" cy="470" r="4" fill="#2DBFBA" />

      <g transform="translate(900,190)">
        <rect x="0" y="0" width="230" height="76" rx="12" fill="#0f1c30" stroke="#2DBFBA" strokeOpacity="0.4" strokeWidth="1.5" />
        <circle cx="26" cy="26" r="12" fill="#2DBFBA" fillOpacity="0.2" />
        <path d="M20 26 l4 5 l9 -11" fill="none" stroke="#2DBFBA" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <text x="46" y="22" fill="#e7ecf3" fontFamily="Georgia, serif" fontSize="14" fontWeight="600">
          Evidence found
        </text>
        <text x="46" y="42" fill="#9fb3c8" fontFamily="Georgia, serif" fontSize="12">
          auth/router.py · score 0.87
        </text>
        <rect x="18" y="54" width="196" height="6" rx="3" fill="#1b2c47" />
        <rect x="18" y="54" width="150" height="6" rx="3" fill="#2DBFBA" />
      </g>

      <g transform="translate(940,455)">
        <rect x="0" y="0" width="230" height="76" rx="12" fill="#0f1c30" stroke="#3E6FA6" strokeOpacity="0.5" strokeWidth="1.5" />
        <rect x="16" y="16" width="24" height="24" rx="6" fill="#3E6FA6" fillOpacity="0.25" />
        <path d="M22 28 l6 6 l12 -14" fill="none" stroke="#7fb0ea" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <text x="52" y="24" fill="#e7ecf3" fontFamily="Georgia, serif" fontSize="14" fontWeight="600">
          Plan generated
        </text>
        <text x="52" y="44" fill="#9fb3c8" fontFamily="Georgia, serif" fontSize="12">
          4 affected files · 6 tasks
        </text>
        <text x="16" y="66" fill="#7fb0ea" fontFamily="Georgia, serif" fontSize="12" fontWeight="600">
          Awaiting review
        </text>
      </g>

      <g transform="translate(890,610)">
        <rect x="0" y="0" width="210" height="70" rx="12" fill="#0f1c30" stroke="#2DBFBA" strokeOpacity="0.4" strokeWidth="1.5" />
        <text x="18" y="26" fill="#e7ecf3" fontFamily="Georgia, serif" fontSize="13" fontWeight="600">
          Confidence
        </text>
        <rect x="18" y="38" width="70" height="18" rx="9" fill="#123a2e" />
        <text x="34" y="51" fill="#4fe3c0" fontFamily="Georgia, serif" fontSize="12" fontWeight="700">
          High
        </text>
        <g transform="translate(150,32)">
          <rect x="0" y="14" width="8" height="16" fill="#2DBFBA" opacity="0.9" />
          <rect x="12" y="6" width="8" height="24" fill="#2DBFBA" opacity="0.9" />
          <rect x="24" y="0" width="8" height="30" fill="#2DBFBA" opacity="0.9" />
        </g>
      </g>
    </svg>
  );
}
