import { useEffect, useState } from "react";
import { Clock, Loader2 } from "lucide-react";
import { subscribeServerWakeup } from "../api/client";

export default function ServerWakeupBanner() {
  const [waking, setWaking] = useState(false);

  useEffect(() => {
    return subscribeServerWakeup(setWaking);
  }, []);

  if (!waking) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] w-[calc(100%-2rem)] max-w-md pointer-events-none"
    >
      <div className="bg-white/95 border border-orange-300 shadow-lg rounded-xl px-4 py-3 flex items-center gap-3 backdrop-blur-xs">
        <div className="w-9 h-9 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center shrink-0">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-bold text-gray-900 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-orange-600 shrink-0" />
            Despertando el servidor... Aguarde un momento por favor
          </p>
          <p className="text-[11px] text-gray-600 mt-0.5 leading-snug">
            Iniciando servicios en la nube. Esto puede demorar unos segundos la primera vez.
          </p>
        </div>
      </div>
    </div>
  );
}
