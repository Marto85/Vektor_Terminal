import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FinancialsQuickCards from "../components/FinancialsQuickCards";

const SAMPLE_FINANCIAL_DATA = [
  {
    Categoría: "Cuenta de Resultados",
    Métrica: "Ingresos Totales",
    2023: 200000.0,
    2024: 240000.0,
  },
  {
    Categoría: "Cuenta de Resultados",
    Métrica: "Beneficio Bruto",
    2023: 140000.0,
    2024: 168000.0,
  },
  {
    Categoría: "Cuenta de Resultados",
    Métrica: "Beneficio Operativo",
    2023: 80000.0,
    2024: 108000.0,
  },
  {
    Categoría: "Cuenta de Resultados",
    Métrica: "Beneficio Neto",
    2023: 65000.0,
    2024: 84000.0,
  },
  {
    Categoría: "Balance de Situación",
    Métrica: "Efectivo y equivalentes",
    2023: 30000.0,
    2024: 45000.0,
  },
  {
    Categoría: "Balance de Situación",
    Métrica: "Inversiones a corto plazo",
    2023: 40000.0,
    2024: 55000.0,
  },
  {
    Categoría: "Balance de Situación",
    Métrica: "Deuda a corto plazo",
    2023: 5000.0,
    2024: 5000.0,
  },
  {
    Categoría: "Balance de Situación",
    Métrica: "Deuda a largo plazo",
    2023: 45000.0,
    2024: 40000.0,
  },
  {
    Categoría: "Balance de Situación",
    Métrica: "Patrimonio neto",
    2023: 200000.0,
    2024: 250000.0,
  },
  {
    Categoría: "Balance de Situación",
    Métrica: "Total activo corriente",
    2023: 150000.0,
    2024: 180000.0,
  },
  {
    Categoría: "Balance de Situación",
    Métrica: "Total pasivo corriente",
    2023: 90000.0,
    2024: 100000.0,
  },
  {
    Categoría: "Estado de Flujo de Efectivo",
    Métrica: "Efectivo de Operaciones (CFO)",
    2023: 90000.0,
    2024: 115000.0,
  },
  {
    Categoría: "Estado de Flujo de Efectivo",
    Métrica: "Gastos de capital (CapEx)",
    2023: -25000.0,
    2024: -35000.0,
  },
  {
    Categoría: "Estado de Flujo de Efectivo",
    Métrica: "Flujo de caja libre (FCF)",
    2023: 65000.0,
    2024: 80000.0,
  },
  {
    Categoría: "Ratios",
    Métrica: "Rentabilidad sobre capital (ROE) %",
    is_pct: true,
    2023: 32.5,
    2024: 33.6,
  },
  {
    Categoría: "Ratios",
    Métrica: "Rentabilidad sobre activos (ROA) %",
    is_pct: true,
    2023: 16.0,
    2024: 17.5,
  },
  {
    Categoría: "Ratios",
    Métrica: "Ciclo de conversión de efectivo (CCC) días",
    2023: -12,
    2024: -15,
  },
  {
    Categoría: "Ratios",
    Métrica: "Ratio de liquidez (x)",
    2023: 1.67,
    2024: 1.8,
  },
  {
    Categoría: "Ratios",
    Métrica: "Ratio de disponibilidad (Quick Ratio) (x)",
    2023: 1.5,
    2024: 1.65,
  },
  {
    Categoría: "Ratios",
    Métrica: "Deuda total / EBITDA (x)",
    2023: 0.55,
    2024: 0.38,
  },
  {
    Categoría: "Ratios",
    Métrica: "EBIT / Gastos por intereses (x)",
    2023: 45.0,
    2024: 54.0,
  },
];

describe("FinancialsQuickCards", () => {
  it("renderiza tarjetas de Cuenta de Resultados y dispara glosario", () => {
    const onOpenInfo = vi.fn();
    render(
      <FinancialsQuickCards
        financialData={SAMPLE_FINANCIAL_DATA}
        activeContentTab="Cuenta de Resultados"
        period="annual"
        onOpenInfo={onOpenInfo}
      />,
    );

    expect(screen.getByText("Ingresos Totales (2024)")).toBeInTheDocument();
    expect(screen.getByText("+20.0% vs 2023")).toBeInTheDocument();
    expect(screen.getByText("Margen Bruto")).toBeInTheDocument();
    expect(screen.getByText("Margen Operativo (EBIT)")).toBeInTheDocument();

    const infoButtons = screen.getAllByTitle(
      "Ver definición y criterios de lectura",
    );
    fireEvent.click(infoButtons[0]);
    expect(onOpenInfo).toHaveBeenCalledWith(
      "Ingresos Totales",
      expect.any(String),
    );
  });

  it("detecta posición de caja neta en Balance de Situación", () => {
    render(
      <FinancialsQuickCards
        financialData={SAMPLE_FINANCIAL_DATA}
        activeContentTab="Balance de Situación"
        period="annual"
      />,
    );

    expect(screen.getByText("Posición de Caja Neta")).toBeInTheDocument();
    expect(screen.getByText("Patrimonio Neto (2024)")).toBeInTheDocument();
    expect(screen.getByText("Capital de Trabajo Neto")).toBeInTheDocument();
  });

  it("calcula flujo de caja libre y conversión en Estado de Flujo de Efectivo", () => {
    render(
      <FinancialsQuickCards
        financialData={SAMPLE_FINANCIAL_DATA}
        activeContentTab="Estado de Flujo de Efectivo"
        period="annual"
      />,
    );

    expect(screen.getByText("Flujo Operativo CFO (2024)")).toBeInTheDocument();
    expect(screen.getByText("Flujo de Caja Libre (2024)")).toBeInTheDocument();
    expect(
      screen.getByText("Conversión FCF / Beneficio Neto"),
    ).toBeInTheDocument();
  });

  it("renderiza síntesis de retornos, liquidez y solvencia en Ratios", () => {
    render(
      <FinancialsQuickCards
        financialData={SAMPLE_FINANCIAL_DATA}
        activeContentTab="Ratios"
        period="annual"
      />,
    );

    expect(screen.getByText("Rentabilidad ROE (2024)")).toBeInTheDocument();
    expect(
      screen.getByText("Ciclo Conversión Efectivo (CCC)"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Apalancamiento Deuda / EBITDA"),
    ).toBeInTheDocument();
  });
});