import { useEffect, useState } from "react";
import apiClient from "../api/client";
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
    desc: "Gestión de carteras en moneda base configurable con conversión FX automática, Precio Promedio Ponderado y TWR con cierres históricos.",
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
    image: "/landing/03_resumen_grafico_at.webp",
    caption:
      "Velas OHLCV con medias móviles, Bollinger, VWAP, osciladores (RSI/MACD/ATR) y lentes metodológicas automáticas validadas por volumen relativo (RVOL).",
  },
  {
    id: "valuation",
    label: "Valoración y DCF Inverso",
    image: "/landing/05_valoracion_dcf.webp",
    caption:
      "Auditoría contable de calidad, consenso Wall Street, múltiplos históricos 5Y y simulador interactivo de valor intrínseco.",
  },
  {
    id: "screener",
    label: "Screener Fundamental",
    image: "/landing/08_screener.webp",
    caption:
      "Filtrá el universo por ROIC, FCF Yield, múltiplos NTM/LTM, endeudamiento y potencial de consenso con actualización en segundo plano.",
  },
  {
    id: "home",
    label: "Inicio y Mercado Global",
    image: "/landing/02_inicio_mercado.webp",
    caption:
      "Radar fundamental diario, benchmarks principales (SPY, QQQ, ARGT, ^TNX) y titulares financieros relevantes.",
  },
];

export default function LandingPage({ onGoToLogin, onGoToRegister }) {
  const [activePreview, setActivePreview] = useState(SHOWCASE_VIEWS[0]);
  const [regMode, setRegMode] = useState("open");

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get("/auth/providers")
      .then((res) => {
        if (!cancelled && res.data?.registration_mode) {
          setRegMode(res.data.registration_mode);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const isRegistrationClosed = regMode === "closed";

  return (
    <div className="min-h-screen bg-white text-gray-900 flex flex-col">
      {/* Navbar superior claro */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <a href="#top" className="flex items-center">
            <BrandLogo size="md" tone="light" showSubtitle />
          </a>

          <nav className="hidden md:flex items-center gap-7 text-xs font-medium text-gray-600">
            <a href="#funciones" className="hover:text-orange-600 transition-colors">
              Funcionalidades
            </a>
            <a href="#modulos" className="hover:text-orange-600 transition-colors">
              Vistas de la Terminal
            </a>
            <a href="#flujo" className="hover:text-orange-600 transition-colors">
              Metodología
            </a>
            <a href="#seguridad" className="hover:text-orange-600 transition-colors">
              Seguridad
            </a>
          </nav>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={onGoToLogin}
              className="px-3.5 py-2 rounded-lg text-xs font-semibold text-gray-700 border border-gray-300 bg-white hover:bg-gray-50 hover:border-gray-400 transition-colors cursor-pointer"
            >
              Iniciar Sesión
            </button>
            {!isRegistrationClosed && (
              <button
                type="button"
                onClick={onGoToRegister}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-orange-500 hover:bg-orange-600 text-white shadow-sm transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <span>{regMode === "invite" ? "Tengo Invitación" : "Crear Cuenta"}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section
        id="top"
        className="relative overflow-hidden border-b border-gray-200 bg-gradient-to-b from-slate-50 via-white to-white"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-14 sm:py-20 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-5 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-50 border border-orange-200 text-orange-700 text-[11px] font-semibold">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Terminal de Equity Research & Carteras</span>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-[42px] font-bold tracking-tight text-gray-900 leading-tight">
              Análisis fundamental institucional en una sola terminal.
            </h1>

            <p className="text-sm sm:text-base text-gray-600 leading-relaxed">
              VektorTerminal integra datos oficiales de SEC EDGAR, mercado global, modelos DCF y Excess Return, análisis técnico validado por volumen y gestión de portafolios con TWR histórico.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <button
                type="button"
                onClick={onGoToLogin}
                className="px-5 py-2.5 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold shadow-md shadow-orange-500/20 transition-colors cursor-pointer flex items-center gap-2"
              >
                <span>Ingresar a la Terminal</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              {!isRegistrationClosed && (
                <button
                  type="button"
                  onClick={onGoToRegister}
                  className="px-5 py-2.5 rounded-lg border border-gray-300 hover:border-gray-400 bg-white hover:bg-gray-50 text-gray-800 text-sm font-semibold transition-colors cursor-pointer"
                >
                  {regMode === "invite" ? "Registrarme con código" : "Crear cuenta"}
                </button>
              )}
            </div>

            <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-200 text-xs">
              <div>
                <p className="text-lg font-bold text-gray-900">151+</p>
                <p className="text-gray-500">Emisores en Screener</p>
              </div>
              <div>
                <p className="text-lg font-bold text-gray-900">SEC XBRL</p>
                <p className="text-gray-500">10-K, 10-Q, 20-F, 13F</p>
              </div>
              <div>
                <p className="text-lg font-bold text-gray-900">Excel & PDF</p>
                <p className="text-gray-500">Exportación ejecutiva</p>
              </div>
            </div>
          </div>

          <div className="lg:col-span-7">
            <div className="rounded-xl border border-gray-200 bg-white shadow-xl overflow-hidden">
              <div className="h-8 bg-gray-100 border-b border-gray-200 px-3 flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                <span className="ml-2 text-[11px] text-gray-500 font-mono">
                  vektor-terminal · MSFT · Análisis Fundamental & Técnico
                </span>
              </div>
              <img
                src="/landing/03_resumen_grafico_at.webp"
                alt="Vista previa de VektorTerminal"
                className="w-full h-auto object-cover"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Sección Funcionalidades */}
      <section id="funciones" className="py-16 sm:py-20 bg-gray-50 border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mb-10">
            <p className="text-xs font-bold uppercase tracking-widest text-orange-600 mb-2">
              Capacidades de la Plataforma
            </p>
            <h2 className="text-2xl sm:text-3xl font-bold text-gray-900">
              Todo el flujo de investigación financiera, de punta a punta
            </h2>
            <p className="text-sm text-gray-600 mt-2">
              Diseñada para inversores fundamentales, analistas y asesores que necesitan rigor contable y velocidad operativa.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURE_CARDS.map((card) => {
              const Icon = card.icon;
              return (
                <div
                  key={card.title}
                  className="bg-white border border-gray-200 hover:border-orange-300 hover:shadow-sm rounded-xl p-5 transition-all"
                >
                  <div className="w-10 h-10 rounded-lg bg-orange-50 border border-orange-200 flex items-center justify-center text-orange-600 mb-4">
                    <Icon className="w-5 h-5" />
                  </div>
                  <h3 className="text-base font-bold text-gray-900 mb-2">{card.title}</h3>
                  <p className="text-xs text-gray-600 leading-relaxed">{card.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Sección Vistas Interactivas */}
      <section id="modulos" className="py-16 sm:py-20 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-orange-600 mb-2">
                Recorrido Visual
              </p>
              <h2 className="text-2xl sm:text-3xl font-bold text-gray-900">
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
                      ? "bg-orange-500 text-white shadow-xs"
                      : "bg-gray-100 text-gray-700 border border-gray-200 hover:bg-gray-200/70"
                  }`}
                >
                  {view.label}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-lg">
            <img
              src={activePreview.image}
              alt={activePreview.label}
              loading="lazy"
              className="w-full max-h-[540px] object-cover object-top"
            />
            <div className="px-5 py-4 bg-gray-50 border-t border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-gray-900">{activePreview.label}</h3>
                <p className="text-xs text-gray-600 mt-0.5">{activePreview.caption}</p>
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
      <section id="flujo" className="py-16 sm:py-20 bg-gray-50 border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 grid grid-cols-1 lg:grid-cols-2 gap-10">
          <div className="space-y-5">
            <p className="text-xs font-bold uppercase tracking-widest text-orange-600">
              Flujo de Trabajo
            </p>
            <h2 className="text-2xl font-bold text-gray-900">
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
                  className="flex items-start gap-4 p-4 rounded-xl bg-white border border-gray-200"
                >
                  <span className="text-sm font-bold text-orange-600 font-mono">{item.step}</span>
                  <div>
                    <h3 className="text-sm font-bold text-gray-900">{item.title}</h3>
                    <p className="text-xs text-gray-600 mt-1">{item.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div
            id="seguridad"
            className="bg-white border border-gray-200 rounded-xl p-6 sm:p-8 flex flex-col justify-between space-y-6 shadow-xs"
          >
            <div className="space-y-4">
              <div className="w-10 h-10 rounded-lg bg-orange-50 border border-orange-200 flex items-center justify-center text-orange-600">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900">
                Seguridad, aislamiento por rol y modo Claro/Oscuro
              </h2>
              <p className="text-xs text-gray-600 leading-relaxed">
                Cada sesión está protegida con JWT, contraseñas hasheadas con bcrypt, separación estricta entre clientes, asesores y administradores, y soporte nativo para Google y GitHub OAuth 2.0.
              </p>
              <ul className="space-y-2.5 text-xs text-gray-700">
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-orange-500 shrink-0" />
                  <span>Aislamiento de carteras y watchlists por usuario</span>
                </li>
                <li className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-orange-500 shrink-0" />
                  <span>Glosario interactivo con fórmulas y rangos saludables</span>
                </li>
                <li className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-orange-500 shrink-0" />
                  <span>Tema Claro y Oscuro adaptable a sesiones prolongadas</span>
                </li>
                <li className="flex items-center gap-2">
                  <Lock className="w-4 h-4 text-orange-500 shrink-0" />
                  <span>Acceso privado con registro controlado por entorno o invitación</span>
                </li>
              </ul>
            </div>

            <div className="pt-4 border-t border-gray-200 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onGoToLogin}
                className="px-4 py-2.5 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold cursor-pointer"
              >
                Iniciar Sesión
              </button>
              {!isRegistrationClosed && (
                <button
                  type="button"
                  onClick={onGoToRegister}
                  className="px-4 py-2.5 rounded-lg border border-gray-300 hover:border-gray-400 bg-white hover:bg-gray-50 text-gray-800 text-xs font-semibold cursor-pointer"
                >
                  {regMode === "invite" ? "Registrarme con código" : "Crear Cuenta"}
                </button>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Footer oscuro elegante */}
      <footer className="py-6 bg-[#18181b] text-xs text-gray-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>VektorTerminal · Equity Research & Portfolio Analytics</span>
          <span>
            Datos SEC EDGAR + Mercado Global · Fines informativos, no constituye asesoramiento financiero.
          </span>
        </div>
      </footer>
    </div>
  );
}
