export default function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 56" fill="none" aria-hidden="true">
      <path d="M24 55C24 55 2 34 2 23a22 22 0 1 1 44 0c0 11-22 32-22 32Z" fill="#2f6b3a" />
      <path d="M24 34V22" stroke="#f4ecd8" strokeWidth="3" strokeLinecap="round" />
      <path d="M24 26C14 26 11 20 11 15c9 0 13 4 13 11ZM24 22c0-9 5-13 13-13 0 8-5 13-13 13Z" fill="#f4ecd8" />
    </svg>
  );
}
