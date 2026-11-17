export default function BrandLogo({ size = "md", showSubtitle = false }) {
  const iconDim = size === "lg" ? "w-9 h-9" : size === "sm" ? "w-5 h-5" : "w-6 h-6";

  return (
    <div className="inline-flex items-center gap-2.5 select-none">
      {/* Isotipo Vektor: monograma "V" direccional con vértice de inflexión y vector ascendente */}
      <svg
        viewBox="0 0 36 36"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`${iconDim} shrink-0`}
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="vektorBgGrad" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#18181b" />
            <stop offset="100%" stopColor="#27272a" />
          </linearGradient>
          <linearGradient id="vektorStrokeGrad" x1="7" y1="10" x2="29" y2="10" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#fb923c" />
            <stop offset="100%" stopColor="#f97316" />
          </linearGradient>
        </defs>

        {/* Contenedor oscuro con borde sutil */}
        <rect
          x="1"
          y="1"
          width="34"
          height="34"
          rx="8"
          fill="url(#vektorBgGrad)"
          stroke="#3f3f46"
          strokeWidth="1"
        />

        {/* Trazo en V: descenso analítico + vector alcista */}
        <path
          d="M8.5 11.5L17.2 25.5L27.5 10"
          stroke="url(#vektorStrokeGrad)"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Punta de flecha vectorial superior derecha */}
        <path
          d="M23.2 9.8H27.8V14.4"
          stroke="#fb923c"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Nodo blanco en el vértice de inflexión */}
        <circle cx="17.2" cy="25.5" r="2.1" fill="#ffffff" />
      </svg>

      <div className="flex flex-col leading-tight">
        <span
          className={`font-extrabold tracking-tight ${
            size === "lg" ? "text-xl text-gray-900" : "text-[15px] text-white"
          }`}
        >
          Vekt<span className="text-orange-500">or</span>
        </span>
        {showSubtitle && (
          <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">
            Equity Research Terminal
          </span>
        )}
      </div>
    </div>
  );
}