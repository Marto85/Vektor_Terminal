import { X, BookOpen, CheckCircle2, BarChart2, Lightbulb } from 'lucide-react';

export default function MetricInfoDrawer({ entry, currentValue, onClose }) {
  if (!entry) return null;

  return (
    <aside className="fixed top-12 right-0 bottom-0 w-96 max-w-full bg-white border-l border-gray-200 shadow-2xl z-40 flex flex-col animate-in slide-in-from-right duration-150">
      {/* Cabecera */}
      <div className="px-5 py-4 border-b border-gray-200 bg-[#fafafa] flex items-start justify-between">
        <div className="pr-3">
          <div className="flex items-center space-x-1.5 text-[11px] font-bold uppercase tracking-wider text-orange-500">
            <BookOpen className="w-3.5 h-3.5" />
            <span>Guía Analítica</span>
          </div>
          <h3 className="text-base font-bold text-gray-900 mt-1 leading-snug">
            {entry.title}
          </h3>
          {currentValue !== undefined && currentValue !== null && currentValue !== '-' && (
            <div className="mt-1.5 inline-flex items-center px-2 py-0.5 rounded bg-orange-50 border border-orange-200 text-xs">
              <span className="text-gray-600 mr-1.5">Valor actual del activo:</span>
              <span className="font-bold text-gray-900 tabular-nums">{currentValue}</span>
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          title="Cerrar panel"
          className="p-1.5 rounded text-gray-400 hover:text-gray-800 hover:bg-gray-200/60 cursor-pointer transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Cuerpo scrollable */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5 text-[13px] leading-relaxed">
        {/* Fórmula */}
        <div className="bg-gray-900 text-gray-100 rounded-md px-3.5 py-2.5 font-mono text-xs">
          <span className="text-[10px] uppercase tracking-wider text-orange-400 block mb-1 font-sans font-bold">
            Fórmula de cálculo
          </span>
          {entry.formula}
        </div>

        {/* Qué es */}
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">
            ¿Qué significa?
          </h4>
          <p className="text-gray-700">{entry.explanation}</p>
        </div>

        {/* Qué evalúa */}
        <div>
          <h4 className="flex items-center text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 mr-1.5" />
            ¿Qué evalúa en la tesis?
          </h4>
          <p className="text-gray-700">{entry.evaluates}</p>
        </div>

        {/* Rangos de referencia */}
        <div>
          <h4 className="flex items-center text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">
            <BarChart2 className="w-3.5 h-3.5 text-orange-500 mr-1.5" />
            Valores de referencia por perfil
          </h4>
          <ul className="space-y-1.5">
            {entry.benchmarks.map((item, idx) => (
              <li
                key={idx}
                className="bg-gray-50 border border-gray-200/80 rounded px-3 py-2 text-xs text-gray-700"
              >
                {item}
              </li>
            ))}
          </ul>
        </div>

        {/* Ejemplo práctico */}
        <div className="bg-blue-50/70 border border-blue-200/80 rounded-md p-3.5">
          <h4 className="flex items-center text-xs font-bold uppercase tracking-wider text-blue-800 mb-1">
            <Lightbulb className="w-3.5 h-3.5 text-blue-600 mr-1.5" />
            Ejemplo práctico
          </h4>
          <p className="text-xs text-blue-950 leading-relaxed">{entry.example}</p>
        </div>
      </div>
    </aside>
  );
}