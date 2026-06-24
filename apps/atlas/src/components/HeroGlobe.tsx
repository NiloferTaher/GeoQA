export default function HeroGlobe() {
  return (
    <div className="hero-globe" aria-hidden="true">
      <svg viewBox="0 0 520 520" role="img">
        <defs>
          <radialGradient id="globeGlow" cx="50%" cy="45%" r="60%">
            <stop offset="0%" stopColor="#55e7f2" stopOpacity="0.24" />
            <stop offset="58%" stopColor="#0b2f3a" stopOpacity="0.34" />
            <stop offset="100%" stopColor="#071216" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="arcStroke" x1="0%" x2="100%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="#55e7f2" />
            <stop offset="55%" stopColor="#3ee6a4" />
            <stop offset="100%" stopColor="#ffd21f" />
          </linearGradient>
        </defs>
        <circle cx="260" cy="260" r="210" fill="url(#globeGlow)" />
        <circle className="globe-ring" cx="260" cy="260" r="205" />
        <circle className="globe-ring muted-ring" cx="260" cy="260" r="156" />
        <circle className="globe-ring muted-ring" cx="260" cy="260" r="108" />
        <path className="globe-lat" d="M72 260c58 42 318 42 376 0" />
        <path className="globe-lat" d="M98 188c78 32 246 32 324 0" />
        <path className="globe-lat" d="M98 332c78-32 246-32 324 0" />
        <path className="globe-lon" d="M260 56c-58 74-58 334 0 408" />
        <path className="globe-lon" d="M172 82c38 96 38 260 0 356" />
        <path className="globe-lon" d="M348 82c-38 96-38 260 0 356" />
        <path className="globe-arc arc-one" d="M128 326C196 184 320 164 410 236" />
        <path className="globe-arc arc-two" d="M108 214C190 122 314 114 424 196" />
        <path className="globe-arc arc-three" d="M178 398C246 286 342 278 438 336" />
        <circle className="globe-node node-one" cx="128" cy="326" r="5" />
        <circle className="globe-node node-two" cx="410" cy="236" r="5" />
        <circle className="globe-node node-three" cx="424" cy="196" r="4" />
        <circle className="globe-node node-four" cx="178" cy="398" r="4" />
      </svg>
    </div>
  )
}
