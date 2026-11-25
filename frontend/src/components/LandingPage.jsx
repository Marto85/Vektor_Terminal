import { useState } from "react";
import {
  ArrowRight,
  BarChart3,
  Bell,
  Briefcase,
  Calculator,
  CheckCircle2,
  FileSpreadsheet,
  Filter,
  Globe,
  Layers,
  Lock,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import BrandLogo from "./BrandLogo";

const FEATURE_CARDS = [
  {
    icon: FileSpreadsheet,
    title: "Estados Contables SEC EDGAR",
    desc: "Extracción y normalización XBRL de formularios 10-K, 10-Q, 20-F y 6-K con aislamiento estricto de trimestres y exportación a Excel (.xlsx).",
  },
  {
    icon: Calculator,
    title: "Modelos de Valoración Intrínseca",
    desc: "DCF en 2 etapas con WACC dinámico, DCF Inverso (Expectations Investing), DDM, Excess Return para bancos y comparables sectoriales.",
  },
  {
    icon: Filter,
    title: "Screener Fundamental Curado",
    desc: "Universo de 151 emisores globales y ADRs con 5 estrategias predefinidas, 14 filtros paramétricos en cascada y exportación CSV.",
  },
  {
    icon: Briefcase,
    title: "Carteras CRM, PPP y TWR",
    desc: "Gestión multi-moneda de clientes y portafolios con Precio Promedio Ponderado, flujo de caja y TWR valuado con cierres históricos diarios.",
  },
  {
    icon: Globe,
    title: "Macro Lab y Pulso de Mercado",
    desc: "Curva del Tesoro EE. UU., tasas reales, spreads de crédito, valuación relativa de índices globales y prima de riesgo implícita (ERP).",
  },
  {
    icon: Bell,
    title: "Watchlists, Alertas SEC y Tesis",
    desc: "Seguimiento con precios objetivo, detección automática de nuevos filings SEC, tenedores 13F, operaciones Form 4 y One-Pager PDF.",
  },
];

const SHOWCASE_VIEWS = [
  {
    id: "chart",
    label: "Gráfico y Análisis Técnico",
    image: "/landing/03_resumen_grafico_at.png",
    caption:
      "Velas OHLCV con medias móviles, Bollinger, VWAP, osciladores (RSI/MACD/ATR) y lentes metodológicas automáticas validadas por volumen relativo (RVOL).",
  },
  {
    id: "valuation",
    label: "Valoración y DCF Inverso",
    image: "/landing/05_valoracion_dcf.png",
    caption:
      "Auditoría contable de calidad, consenso Wall Street, múltiplos históricos 5Y y simulador interactivo de valor intrínseco.",
  },
  {
    id: "screener",
    label: "Screener Fundamental",
    image: "/landing/08_screener.png",
    caption:
      "Filtrá el universo por ROIC, FCF Yield, múltiplos NTM/LTM, endeudamiento y potencial de consenso con actualización en segundo plano.",
  },
  {
    id: "home",
    label: "Inicio y Mercado Global",
    image: "/landing/02_inicio_mercado.png",
    caption:
      "Radar fundamental diario, benchmarks principales (SPY, QQQ, ARGT, ^TNX) y titulares financieros relevantes.",
  },
];

export default function LandingPage({ onGoToLogin, onGoToRegister }) {
  const [activePreview, setActivePreview] = useState(SHOWCASE_VIEWS[0]);

  return (
    <div className="min-h-screen bg-[#141416] text-gray-100 flex flex-col">
      {/* Navbar superior */}
      <header className="sticky top-0 z-40 bg-[#1e1e1e]/95 backdrop-blur border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <a href="#top" className="flex items-center">
            <BrandLogo size="md" showSubtitle />
          </a>

          <nav className="hidden md:flex items-center gap-7 text-xs font-medium text-gray-300">
            <a href="#funciones" className="hover:text-orange-400 transition-colors">
              Funcionalidades
            </a>
            <a href="#modulos" className="hover:text-orange-400 transition-colors">
              Vistas de la Terminal
            </a>
            <a href="#flujo" className="hover:text-orange-400 transition-colors">
              Metodología
            </a>
            <a href="#seguridad" className="hover:text-orange-400 transition-colors">
              Seguridad
            </a>
          </nav>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={onGoToLogin}
              className="px-3.5 py-2 rounded-lg text-xs font-semibold text-gray-200 border border-gray-700 hover:border-gray-500 hover:bg-[#252526] transition-colors cursor-pointer"
            >
              Iniciar Sesión
            </button>
            <button
              type="button"
              onClick={onGoToRegister}
              className="px-4 py-2 rounded-lg text-xs font-semibold bg-orange-500 hover:bg-orange-600 text-white shadow-sm transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <span>Crear Cuenta</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section
        id="top"
        className="relative overflow-hidden border-b border-gray-800/80 bg-gradient-to-b from-[#1e1e1e] via-[#17171a] to-[#141416]"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-14 sm:py-20 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-5 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/30 text-orange-400 text-[11px] font-semibold">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Terminal de Equity Research & Carteras</span>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-[42px] font-bold tracking-tight text-white leading-tight">
              Análisis fundamental institucional en una sola terminal.
            </h1>

            <p className="text-sm sm:text-base text-gray-400 leading-relaxed">
              VektorTerminal integra datos oficiales de SEC EDGAR, mercado global, modelos DCF y Excess Return, análisis técnico validado por volumen y gestión de portafolios con TWR histórico.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <button
                type="button"
                onClick={onGoToLogin}
                className="px-5 py-2.5 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold shadow-lg shadow-orange-500/20 transition-colors cursor-pointer flex items-center gap-2"
              >
                <span>Ingresar a la Terminal</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={onGoToRegister}
                className="px-5 py-2.5 rounded-lg border border-gray-700 hover:border-gray-500 bg-[#252526] text-gray-200 text-sm font-semibold transition-colors cursor-pointer"
              >
                Crear cuenta / Acceso
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-800 text-xs">
              <div>
                <p className="text-lg font-bold text-white">151+</p>
                <p className="text-gray-400">Emisores en Screener</p>
              </div>
              <div>
                <p className="text-lg font-bold text-white">SEC XBRL</p>
                <p className="text-gray-400">10-K, 10-Q, 20-F, 13F</p>
              </div>
              <div>
                <p className="text-lg font-bold text-white">Excel & PDF</p>
                <p className="text-gray-400">Exportación ejecutiva</p>
              </div>
            </div>
          </div>

          <div className="lg:col-span-7">
            <div className="rounded-xl border border-gray-700/80 bg-[#252526] shadow-2xl overflow-hidden">
              <div className="h-8 bg-[#1e1e1e] border-b border-gray-800 px-3 flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400/80" />
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
                <span className="ml-2 text-[11px] text-gray-400 font-mono">
                  vektor-terminal · MSFT · Análisis Fundamental & Técnico
                </span>
              </div>
              <img
                src="/landing/03_resumen_grafico_at.png"
                alt="Vista previa de VektorTerminal"
                className="w-full h-auto object-cover"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Sección Funcionalidades */}
      <section id="funciones" className="py-16 sm:py-20 bg-[#141416] border-b border-gray-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mb-10">
            <p className="text-xs font-bold uppercase tracking-widest text-orange-400 mb-2">
              Capacidades de la Plataforma
            </p>
            <h2 className="text-2xl sm:text-3xl font-bold text-white">
              Todo el flujo de investigación financiera, de punta a punta
            </h2>
            <p className="text-sm text-gray-400 mt-2">
              Diseñada para inversores fundamentales, analistas y asesores que necesitan rigor contable y velocidad operativa.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURE_CARDS.map((card) => {
              const Icon = card.icon;
              return (
                <div
                  key={card.title}
                  className="bg-[#1e1e22] border border-gray-800 hover:border-orange-500/40 rounded-xl p-5 transition-colors"
                >
                  <div className="w-10 h-10 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-orange-400 mb-4">
                    <Icon className="w-5 h-5" />
                  </div>
                  <h3 className="text-base font-bold text-white mb-2">{card.title}</h3>
                  <p className="text-xs text-gray-400 leading-relaxed">{card.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Sección Vistas Interactivas */}
      <section id="modulos" className="py-16 sm:py-20 bg-[#18181b] border-b border-gray-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-orange-400 mb-2">
                Recorrido Visual
              </p>
              <h2 className="text-2xl sm:text-3xl font-bold text-white">
                Explorá los módulos principales
              </h2>
            </div>

            <div className="flex flex-wrap gap-2">
              {SHOWCASE_VIEWS.map((view) => (
                <button
                  key={view.id}
                  type="button"
                  onClick={() => setActivePreview(view)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                    activePreview.id === view.id
                      ? "bg-orange-500 text-white"
                      : "bg-[#252526] text-gray-300 border border-gray-700 hover:border-gray-500"
                  }`}
                >
                  {view.label}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-gray-700 bg-[#252526] overflow-hidden shadow-2xl">
            <img
              src={activePreview.image}
              alt={activePreview.label}
              className="w-full max-h-[540px] object-cover object-top"
            />
            <div className="px-5 py-4 bg-[#1e1e1e] border-t border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-white">{activePreview.label}</h3>
                <p className="text-xs text-gray-400 mt-0.5">{activePreview.caption}</p>
              </div>
              <button
                type="button"
                onClick={onGoToLogin}
                className="px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold shrink-0 cursor-pointer"
              >
                Probar ahora
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Sección Metodología y Seguridad */}
      <section id="flujo" className="py-16 sm:py-20 bg-[#141416] border-b border-gray-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 grid grid-cols-1 lg:grid-cols-2 gap-10">
          <div className="space-y-5">
            <p className="text-xs font-bold uppercase tracking-widest text-orange-400">
              Flujo de Trabajo
            </p>
            <h2 className="text-2xl font-bold text-white">
              Del universo de mercado a la decisión de inversión
            </h2>
            <div className="space-y-4">
              {[
                {
                  step: "01",
                  title: "Descubrí oportunidades",
                  text: "Filtrá en el Screener Fundamental o detectá ideas en el Radar del portal inicial.",
                },
                {
                  step: "02",
                  title: "Auditá calidad y valor intrínseco",
                  text: "Revisá Piotroski F-Score, Altman Z-Score, ROIC/ROIIC, FCF Post-SBC y modelá escenarios DCF o Excess Return.",
                },
                {
                  step: "03",
                  title: "Monitoreá tesis y carteras",
                  text: "Configurá alertas por precio o filings SEC y seguí el rendimiento TWR real de tus portafolios.",
                },
              ].map((item) => (
                <div
                  key={item.step}
                  className="flex items-start gap-4 p-4 rounded-xl bg-[#1e1e22] border border-gray-800"
                >
                  <span className="text-sm font-bold text-orange-400 font-mono">{item.step}</span>
                  <div>
                    <h3 className="text-sm font-bold text-white">{item.title}</h3>
                    <p className="text-xs text-gray-400 mt-1">{item.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div
            id="seguridad"
            className="bg-[#1e1e22] border border-gray-800 rounded-xl p-6 sm:p-8 flex flex-col justify-between space-y-6"
          >
            <div className="space-y-4">
              <div className="w-10 h-10 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-orange-400">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h2 className="text-2xl font-bold text-white">
                Seguridad, aislamiento por rol y modo Claro/Oscuro
              </h2>
              <p className="text-xs text-gray-400 leading-relaxed">
                Cada sesión está protegida con JWT, contraseñas hasheadas con bcrypt, separación estricta entre clientes, asesores y administradores, y soporte nativo para Google y GitHub OAuth 2.0.
              </p>
              <ul className="space-y-2.5 text-xs text-gray-300">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-orange-400 shrink-0" />
                  <span>Aislamiento de carteras y watchlists por usuario</span>
                </li>
                <li className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-orange-400 shrink-0" />
                  <span>Glosario interactivo con fórmulas y rangos saludables</span>
                </li>
                <li className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-orange-400 shrink-0" />
                  <span>Tema Claro y Oscuro adaptable a sesiones prolongadas</span>
                </li>
                <li className="flex items-center gap-2">
                  <Lock className="w-4 h-4 text-orange-400 shrink-0" />
                  <span>Acceso privado con registro controlado por entorno o invitación</span>
                </li>
              </ul>
            </div>

            <div className="pt-4 border-t border-gray-800 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onGoToLogin}
                className="px-4 py-2.5 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold cursor-pointer"
              >
                Iniciar Sesión
              </button>
              <button
                type="button"
                onClick={onGoToRegister}
                className="px-4 py-2.5 rounded-lg border border-gray-700 hover:border-gray-500 text-gray-200 text-xs font-semibold cursor-pointer"
              >
                Crear Cuenta
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-6 bg-[#111113] text-xs text-gray-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>VektorTerminal · Equity Research & Portfolio Analytics</span>
          <span>Datos oficiales SEC EDGAR + Mercado Global · Uso informativo</span>
        </div>
      </footer>
    </div>
  );
}
