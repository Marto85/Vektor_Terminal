import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRoot } from "react-dom/client";
import { act } from "react";
import axios from "axios";
import OwnershipInsidersTab from "../components/OwnershipInsidersTab";

vi.mock("axios");

describe("OwnershipInsidersTab", () => {
  let container;
  let root;

  beforeEach(() => {
    vi.clearAllMocks();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  it("renderiza indicadores 13F y filtra transacciones Form 4 por compra/venta", async () => {
    axios.get.mockResolvedValueOnce({
      data: {
        ticker: "MSFT",
        as_of: "2026-11-19 18:00 UTC",
        major_holders: {
          institutions_pct: 75.5,
          insiders_pct: 0.15,
          institutions_count: 8200,
          public_other_pct: 24.35,
        },
        institutional_holders: [
          {
            holder: "Blackrock Inc.",
            date_reported: "2026-09-30",
            shares: 600000000,
            pct_out: 8.1,
            value_mm: 300000.0,
            pct_change: 0.25,
          },
        ],
        mutualfund_holders: [],
        insider_summary: {
          total_transactions: 2,
          buy_count: 1,
          sell_count: 1,
          other_count: 0,
          buy_value_mm: 2.0,
          sell_value_mm: 1.0,
          net_value_mm: 1.0,
          sentiment: "bullish",
        },
        insider_transactions: [
          {
            date: "2026-11-10",
            insider: "INSIDER COMPRADOR",
            position: "Director",
            transaction: "Purchase",
            kind: "buy",
            shares: 4000,
            value_usd: 2000000,
          },
          {
            date: "2026-11-05",
            insider: "INSIDER VENDEDOR",
            position: "Officer",
            transaction: "Sale",
            kind: "sell",
            shares: 2000,
            value_usd: 1000000,
          },
        ],
      },
    });

    await act(async () => {
      root.render(<OwnershipInsidersTab ticker="MSFT" />);
    });

    expect(container.textContent).toContain("Blackrock Inc.");
    expect(container.textContent).toContain("INSIDER COMPRADOR");
    expect(container.textContent).toContain("INSIDER VENDEDOR");

    const buyBtn = Array.from(container.querySelectorAll("button")).find((b) =>
      b.textContent.includes("Compras (1)")
    );
    expect(buyBtn).toBeTruthy();

    await act(async () => {
      buyBtn.click();
    });

    expect(container.textContent).toContain("INSIDER COMPRADOR");
    expect(container.textContent).not.toContain("INSIDER VENDEDOR");
  });
});