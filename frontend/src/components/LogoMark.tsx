/** Small-size adaptation of the leaf-and-circuit mark in logo-reference.png. */
export default function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="agrisense-leaf" x1="12" y1="8" x2="45" y2="36" gradientUnits="userSpaceOnUse"><stop stopColor="#c2ed59" /><stop offset="1" stopColor="#4b9708" /></linearGradient>
        <linearGradient id="agrisense-stem" x1="31" y1="26" x2="31" y2="61" gradientUnits="userSpaceOnUse"><stop stopColor="#69aa1b" /><stop offset="1" stopColor="#a9631e" /></linearGradient>
      </defs>
      <g strokeLinecap="round" strokeLinejoin="round">
        <path d="M29 39 18 35 10 29M35 39l9-7 9-2 6-8M35 19l-5-5 6-9M11 30 6 38" stroke="#639b16" strokeWidth="3" />
        <path d="m53 30 6-8M30 13l6-8M10 29l-4 9" stroke="#85501b" strokeWidth="3" />
        <path d="M31 31C10 30 8 18 7 8c17 9 25 10 24 23ZM33 31c1-16 12-18 24-26-1 15-6 26-24 26Z" fill="url(#agrisense-leaf)" stroke="#0c1708" strokeWidth="1.8" />
        <path d="M16 17c8 7 14 12 16 20M47 15c-8 8-13 13-15 22" stroke="#1f4d13" strokeWidth="2.2" />
        <path d="M30 32c1 9 0 17-2 22-3 5-9 3-16 7 8-1 12-1 20-6 7 5 12 5 20 6-8-5-14-3-16-8-2-6-2-14-2-21" fill="url(#agrisense-stem)" stroke="#0c1708" strokeWidth="1.6" />
        <circle cx="36" cy="5" r="3.5" fill="#f4ecd8" stroke="#85501b" strokeWidth="2.5" />
        <circle cx="30" cy="14" r="3.5" fill="#f4ecd8" stroke="#76b329" strokeWidth="2.5" />
        <circle cx="10" cy="29" r="3.5" fill="#f4ecd8" stroke="#76b329" strokeWidth="2.5" />
        <circle cx="6" cy="38" r="3.5" fill="#f4ecd8" stroke="#85501b" strokeWidth="2.5" />
        <circle cx="59" cy="22" r="3.5" fill="#f4ecd8" stroke="#85501b" strokeWidth="2.5" />
        <circle cx="44" cy="33" r="2.8" fill="#2f6b3a" stroke="none" />
      </g>
    </svg>
  );
}
