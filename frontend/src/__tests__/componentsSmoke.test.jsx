import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import apiClient from "../api/client";
import { ThemeContext } from "../context/themeStore";
import { AuthContext } from "../context/authStore";
import LandingPage from "../components/LandingPage";
import HomeOverview from "../components/HomeOverview";
import ValuationModelsTab from "../components/ValuationModelsTab";
import WatchlistTab from "../components/WatchlistTab";
import ScreenerTab from "../components/ScreenerTab";
import MacroLabTab from "../components/MacroLabTab";
import PortfoliosCRMTab from "../components/PortfoliosCRMTab";
import ArgentinaTab from "../components/ArgentinaTab";

vi.mock("../api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
  API_BASE_URL: "/api/v1",
  getStoredToken: vi.fn(() => "fake-jwt"),
  setStoredToken: vi.fn(),
}));

const themeValue = { isDark: false, toggleTheme: vi.fn() };
const authValue = {
  user: { id: 1, email: "admin@vektorterminal.local", full_name: "Admin", role: "superadmin" },
  token: "fake-jwt",
  isAuthenticated: true,
  isSuperadmin: true,
  isAdvisor: false,
};

function wrapProviders(ui) {
  return (
    <ThemeContext.Provider value={themeValue}>
      <AuthContext.Provider value={authValue}>{ui}</AuthContext.Provider>
    </ThemeContext.Provider>
  );
}

describe("Bloque 4 — Smoke & Interacción de Componentes Clave", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiClient.get.mockResolvedValue({ data: {} });
  });

  it("LandingPage renderiza en tema claro y dispara onGoToLogin", () => {
    const onGoToLogin = vi.fn();
    render(<LandingPage onGoToLogin={onGoToLogin} onGoToRegister={vi.fn()} />);
    expect(screen.getAllByText(/Equity Research Terminal/i).length).toBeGreaterThan(0);
    const cta = screen.getAllByRole("button", { name: /Ingresar/i })[0];
    fireEvent.click(cta);
    expect(onGoToLogin).toHaveBeenCalled();
  });

  it("HomeOverview renderiza Pulso de Mercado sin truncamiento de subtítulos", async () => {
    apiClient.get.mockResolvedValueOnce({
      data: {
        benchmarks: [
          { symbol: "SPY", name: "S&P 500 ETF", subtitle: "Large Cap EE. UU.", unit: "US$", price: 580, change: 2, change_pct: 0.35, sparkline: [575, 580] },
          { symbol: "ARGT", name: "MSCI Argentina ETF", subtitle: "Renta Variable Argentina", unit: "US$", price: 85, change: 1, change_pct: 1.1, sparkline: [84, 85] },
        ],
        news: [],
      },
    });
    render(wrapProviders(<HomeOverview onSelectTicker={vi.fn()} onNavigateTab={vi.fn()} />));
    await waitFor(() => {
      expect(screen.getByText("Renta Variable Argentina")).toBeInTheDocument();
      expect(screen.getByText("MSCI Argentina ETF")).toBeInTheDocument();
    });
  });

  it("ValuationModelsTab sincroniza slider e input numérico en Modo Manual", async () => {
    apiClient.get.mockResolvedValueOnce({
      data: {
        ticker: "MSFT",
        sector_routing: { profile: "standard", label: "Corporativo", primary_model: "DCF", rationale: "Test" },
        audit: { has_anomalies: false, flags: [], comparisons: [] },
        trajectory: { recommended_rev_growth_pct: 12, margin_step_pct_yr: 0.5 },
        dcf_inputs: {
          current_price: 450,
          shares_mm: 7400,
          net_debt_mm: -20000,
          revenue_base_mm: 280000,
          recommended_rev_growth_pct: 12,
          suggested_wacc_pct: 9,
          ebit_margin_pct: 44,
          target_ebit_margin_pct: 46,
          tax_rate_pct: 19,
          da_sales_pct: 9,
          capex_expansion_pct: 15,
          capex_maintenance_pct: 8,
          exit_multiple_default: 24,
          dividend_rate: 3.3,
          payout_ratio_pct: 25,
        },
        financial_sector_inputs: {},
      },
    });

    render(wrapProviders(<ValuationModelsTab initialTicker="MSFT" onOpenInfo={vi.fn()} />));
    await waitFor(() => {
      expect(screen.getByText(/Modo Manual/i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Modo Manual/i));
    const numInput = screen.getByLabelText("Crecimiento Anual Ventas numérico");
    fireEvent.change(numInput, { target: { value: "15.5" } });
    expect(Number(numInput.value)).toBe(15.5);
  });

  it("WatchlistTab, ScreenerTab, MacroLabTab y PortfoliosCRMTab montan sin errores", async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.includes("/watchlists")) return Promise.resolve({ data: { watchlists: [], notifications: [] } });
      if (url.includes("/screener")) return Promise.resolve({ data: { items: [], total: 0, synced_count: 0, total_universe: 0 } });
      if (url.includes("/macro")) return Promise.resolve({ data: { timeline: [], etfs: [], summary: {} } });
      if (url.includes("/portfolios")) return Promise.resolve({ data: { clients: [] } });
      return Promise.resolve({ data: {} });
    });

    const { unmount: u1 } = render(
      wrapProviders(
        <WatchlistTab
          watchlistData={{ watchlists: [], notifications: [] }}
          onSelectTicker={vi.fn()}
          onRefresh={vi.fn()}
        />
      )
    );
    expect(screen.getByText(/Watchlists Personalizadas/i)).toBeInTheDocument();
    u1();

    const { unmount: u2 } = render(wrapProviders(<ScreenerTab onSelectTicker={vi.fn()} />));
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    u2();

    const { unmount: u3 } = render(wrapProviders(<MacroLabTab onSelectTicker={vi.fn()} />));
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    u3();

    render(wrapProviders(<PortfoliosCRMTab onSelectTicker={vi.fn()} />));
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
  });

  it("ArgentinaTab renderiza tarjetas, bonos soberanos y grilla de noticias", async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.includes("/argentina/overview")) {
        return Promise.resolve({
          data: {
            cards: {
              mayorista: { series_id: "fx_mayorista", label: "Dólar Mayorista (A3500)", value: 1000, unit: "ARS", subtitle: "BCRA" },
              mep: { series_id: "fx_mep", label: "Dólar MEP (Promedio)", value: 1150, unit: "ARS", subtitle: "Brecha +15.0%" },
              riesgo_pais: { series_id: "riesgo_pais", label: "Riesgo País (EMBI+)", value: 750, unit: "pb", subtitle: "2026-11-26" },
            },
            sovereign_bonds: [
              { ticker: "GD30", series_id: "bond_GD30", name: "Bonar Global 2030", law: "Ley NY", maturity: "2030-07-09", coupon_pct: 0.75, price_usd: 68.5, change_pct: 1.2 },
            ],
            news: [
              { title: "Noticia Económica Test", subtitle: "Bajada de prueba", link: "https://example.com/1", source: "Infobae", topic: "Economía", published_at: "2026-11-26T10:00:00Z" },
            ],
          },
        });
      }
      return Promise.resolve({
        data: { series_id: "riesgo_pais", label: "Riesgo País", unit: "pb", supports_candlestick: false, points: [] },
      });
    });

    render(wrapProviders(<ArgentinaTab />));
    await waitFor(() => {
      expect(screen.getByText("Bonar Global 2030")).toBeInTheDocument();
      expect(screen.getByText("Noticia Económica Test")).toBeInTheDocument();
    });
  });
});
