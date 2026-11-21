import { useEffect, useState } from "react";
import apiClient from "../api/client";
import {
  Building2,
  UserCheck,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Loader2,
  ShieldAlert,
  Landmark,
  Briefcase,
} from "lucide-react";

function fmtPct(val) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  return `${Number(val).toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function fmtMM(val) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  return `US$ ${Number(val).toLocaleString("es-AR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} MM`;
}

function fmtInt(val) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  return Number(val).toLocaleString("es-AR");
}

function fmtUsd(val) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  return `US$ ${Number(val).toLocaleString("es-AR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

export default function OwnershipInsidersTab({ ticker }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [txFilter, setTxFilter] = useState("all"); // all | buy | sell

  useEffect(() => {
    if (!ticker) return;
    let active = true;

    Promise.resolve().then(() => {
      if (!active) return;
      setLoading(true);
      setError(null);
    });

    apiClient
      .get(`/company/${ticker}/ownership`)
      .then((res) => {
        if (active) setData(res.data);
      })
      .catch((err) => {
        if (active) {
          setError(
            err.response?.data?.detail ||
              "No se pudieron cargar los datos institucionales y de insiders.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [ticker]);

  if (loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-sm py-20 flex flex-col items-center justify-center text-orange-500">
        <Loader2 className="w-9 h-9 animate-spin mb-3" />
        <p className="text-sm font-medium">
          Consultando reportes 13F y Form 4 para {ticker}...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white border border-red-200 rounded-lg shadow-sm p-8 text-center text-red-600">
        <ShieldAlert className="w-8 h-8 mx-auto mb-2" />
        <p className="text-sm font-bold">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const major = data.major_holders || {};
  const instList = data.institutional_holders || [];
  const mfList = data.mutualfund_holders || [];
  const allTxs = data.insider_transactions || [];
  const summary = data.insider_summary || {};

  const filteredTxs = allTxs.filter((tx) => {
    if (txFilter === "buy") return tx.kind === "buy";
    if (txFilter === "sell") return tx.kind === "sell";
    return true;
  });

  const topHolder = instList[0];

  return (
    <div className="space-y-6">
      {/* KPI CARDS SUPERIORES */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-gray-500 text-xs font-medium mb-1">
            <span>Propiedad Institucional (13F)</span>
            <Building2 className="w-4 h-4 text-blue-600" />
          </div>
          <p className="text-2xl font-bold text-gray-900">
            {fmtPct(major.institutions_pct)}
          </p>
          <p className="text-[11px] text-gray-500 mt-1">
            {major.institutions_count
              ? `${fmtInt(major.institutions_count)} fondos reportantes`
              : major.institutions_float_pct !== null
                ? `${fmtPct(major.institutions_float_pct)} del float`
                : "Tenencia institucional agregada"}
          </p>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-gray-500 text-xs font-medium mb-1">
            <span>Propiedad de Insiders</span>
            <UserCheck className="w-4 h-4 text-orange-500" />
          </div>
          <p className="text-2xl font-bold text-gray-900">
            {fmtPct(major.insiders_pct)}
          </p>
          <p className="text-[11px] text-gray-500 mt-1">
            Directivos, ejecutivos y accionistas &gt;10%
          </p>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-gray-500 text-xs font-medium mb-1">
            <span>Principal Tenedor 13F</span>
            <Landmark className="w-4 h-4 text-emerald-600" />
          </div>
          <p
            className="text-sm font-bold text-gray-900 truncate mt-1"
            title={topHolder?.holder || "Sin datos"}
          >
            {topHolder ? topHolder.holder : "Sin datos 13F"}
          </p>
          <p className="text-[11px] text-gray-500 mt-1.5">
            {topHolder
              ? `${fmtPct(topHolder.pct_out)} (${fmtMM(topHolder.value_mm)})`
              : "No reportado"}
          </p>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-gray-500 text-xs font-medium mb-1">
            <span>Actividad Reciente Form 4</span>
            <Briefcase className="w-4 h-4 text-purple-600" />
          </div>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className="text-sm font-bold text-emerald-600">
              {summary.buy_count || 0} compras
            </span>
            <span className="text-gray-300">·</span>
            <span className="text-sm font-bold text-red-600">
              {summary.sell_count || 0} ventas
            </span>
          </div>
          <p className="text-[11px] text-gray-500 mt-1">
            Neto mercado abierto:{" "}
            <span
              className={`font-semibold ${
                (summary.net_value_mm || 0) > 0
                  ? "text-emerald-600"
                  : (summary.net_value_mm || 0) < 0
                    ? "text-red-600"
                    : "text-gray-600"
              }`}
            >
              {fmtMM(summary.net_value_mm || 0)}
            </span>
          </p>
        </div>
      </div>

      {/* BARRA DE COMPOSICIÓN ACCIONARIA */}
      {major.institutions_pct !== null && major.insiders_pct !== null && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="font-bold text-gray-800">
              Estructura de Capital en Circulación
            </span>
            <span className="text-[11px] text-gray-400">
              Actualizado: {data.as_of}
            </span>
          </div>
          <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden flex">
            <div
              style={{ width: `${Math.min(100, major.institutions_pct)}%` }}
              className="bg-blue-600 h-full"
              title={`Institucionales: ${fmtPct(major.institutions_pct)}`}
            />
            <div
              style={{ width: `${Math.min(100, major.insiders_pct)}%` }}
              className="bg-orange-500 h-full"
              title={`Insiders: ${fmtPct(major.insiders_pct)}`}
            />
          </div>
          <div className="flex flex-wrap items-center gap-5 mt-2.5 text-[11px] text-gray-600">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-blue-600" />
              Institucionales: <strong>{fmtPct(major.institutions_pct)}</strong>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-orange-500" />
              Insiders: <strong>{fmtPct(major.insiders_pct)}</strong>
            </span>
            {major.public_other_pct !== null && (
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-gray-300" />
                Retail / Otros:{" "}
                <strong>{fmtPct(major.public_other_pct)}</strong>
              </span>
            )}
          </div>
        </div>
      )}

      {/* TABLA: TOP TENEDORES INSTITUCIONALES (13F) */}
      <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-gray-900">
              Principales Inversores Institucionales (Formularios SEC 13F)
            </h3>
            <p className="text-[11px] text-gray-500">
              Posiciones trimestrales reportadas por gestoras con &gt;US$ 100 MM
              bajo administración
            </p>
          </div>
          <span className="text-xs font-medium text-gray-500">
            Top {instList.length} fondos
          </span>
        </div>

        {instList.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-500">
            No hay registros 13F disponibles para {ticker}.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left whitespace-nowrap">
              <thead>
                <tr className="bg-[#333333] text-white">
                  <th className="py-2.5 px-4 font-bold">Institución / Gestora</th>
                  <th className="py-2.5 px-4 font-bold text-right">
                    Fecha 13F
                  </th>
                  <th className="py-2.5 px-4 font-bold text-right">Acciones</th>
                  <th className="py-2.5 px-4 font-bold text-right">% Capital</th>
                  <th className="py-2.5 px-4 font-bold text-right">
                    Valor Posición
                  </th>
                  <th className="py-2.5 px-4 font-bold text-right">
                    Var. Trimestral
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {instList.map((row, idx) => {
                  const chg = row.pct_change;
                  const isPos = typeof chg === "number" && chg > 0;
                  const isNeg = typeof chg === "number" && chg < 0;

                  return (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="py-2.5 px-4 font-medium text-gray-900">
                        {row.holder}
                      </td>
                      <td className="py-2.5 px-4 text-right text-gray-500">
                        {row.date_reported || "—"}
                      </td>
                      <td className="py-2.5 px-4 text-right text-gray-800">
                        {fmtInt(row.shares)}
                      </td>
                      <td className="py-2.5 px-4 text-right font-semibold text-gray-900">
                        {fmtPct(row.pct_out)}
                      </td>
                      <td className="py-2.5 px-4 text-right text-gray-800">
                        {fmtMM(row.value_mm)}
                      </td>
                      <td
                        className={`py-2.5 px-4 text-right font-semibold ${
                          isPos
                            ? "text-emerald-600"
                            : isNeg
                              ? "text-red-600"
                              : "text-gray-400"
                        }`}
                      >
                        {chg === null || chg === undefined ? (
                          "—"
                        ) : (
                          <span className="inline-flex items-center justify-end gap-0.5">
                            {isPos && <ArrowUpRight className="w-3.5 h-3.5" />}
                            {isNeg && (
                              <ArrowDownRight className="w-3.5 h-3.5" />
                            )}
                            {!isPos && !isNeg && <Minus className="w-3 h-3" />}
                            {isPos ? "+" : ""}
                            {fmtPct(chg)}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* TABLA: OPERACIONES DE INSIDERS (FORM 4) */}
      <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-gray-900">
              Operaciones de Directivos y Ejecutivos (SEC Form 4)
            </h3>
            <p className="text-[11px] text-gray-500">
              Compras, ventas en mercado abierto y adjudicaciones reportadas
              ante la SEC
            </p>
          </div>

          <div className="flex items-center border border-gray-300 rounded overflow-hidden text-xs">
            {[
              { id: "all", label: `Todas (${allTxs.length})` },
              { id: "buy", label: `Compras (${summary.buy_count || 0})` },
              { id: "sell", label: `Ventas (${summary.sell_count || 0})` },
            ].map((btn) => (
              <button
                key={btn.id}
                type="button"
                onClick={() => setTxFilter(btn.id)}
                className={`px-3 py-1 font-medium transition-colors cursor-pointer ${
                  txFilter === btn.id
                    ? "bg-orange-500 text-white"
                    : "bg-white text-gray-600 hover:bg-gray-100"
                }`}
              >
                {btn.label}
              </button>
            ))}
          </div>
        </div>

        {filteredTxs.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-500">
            No se registran operaciones Form 4 para el filtro seleccionado.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left whitespace-nowrap">
              <thead>
                <tr className="bg-[#333333] text-white">
                  <th className="py-2.5 px-4 font-bold">Fecha</th>
                  <th className="py-2.5 px-4 font-bold">Insider</th>
                  <th className="py-2.5 px-4 font-bold">Cargo</th>
                  <th className="py-2.5 px-4 font-bold">Tipo</th>
                  <th className="py-2.5 px-4 font-bold text-right">Acciones</th>
                  <th className="py-2.5 px-4 font-bold text-right">
                    Monto Estimado
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredTxs.map((tx, idx) => {
                  const badgeStyle =
                    tx.kind === "buy"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : tx.kind === "sell"
                        ? "bg-red-50 text-red-700 border-red-200"
                        : "bg-gray-100 text-gray-700 border-gray-200";
                  const badgeLabel =
                    tx.kind === "buy"
                      ? "Compra"
                      : tx.kind === "sell"
                        ? "Venta"
                        : "Opción / Otro";

                  return (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="py-2.5 px-4 text-gray-600">
                        {tx.date || "—"}
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-gray-900">
                        {tx.insider}
                      </td>
                      <td className="py-2.5 px-4 text-gray-600 max-w-56 truncate">
                        {tx.position}
                      </td>
                      <td className="py-2.5 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded border text-[11px] font-semibold ${badgeStyle}`}
                          title={tx.transaction}
                        >
                          {badgeLabel}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right text-gray-800">
                        {fmtInt(tx.shares)}
                      </td>
                      <td className="py-2.5 px-4 text-right font-medium text-gray-900">
                        {fmtUsd(tx.value_usd)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* TABLA COMPLEMENTARIA: FONDOS MUTUOS */}
      {mfList.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
            <h3 className="text-sm font-bold text-gray-900">
              Principales Fondos Mutuos
            </h3>
            <span className="text-xs text-gray-500">
              Top {mfList.length} fondos mutuos
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left whitespace-nowrap">
              <thead>
                <tr className="bg-gray-800 text-white">
                  <th className="py-2 px-4 font-bold">Fondo Mutuo</th>
                  <th className="py-2 px-4 font-bold text-right">Fecha</th>
                  <th className="py-2 px-4 font-bold text-right">Acciones</th>
                  <th className="py-2 px-4 font-bold text-right">% Capital</th>
                  <th className="py-2 px-4 font-bold text-right">Valor</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {mfList.map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="py-2 px-4 font-medium text-gray-900">
                      {row.holder}
                    </td>
                    <td className="py-2 px-4 text-right text-gray-500">
                      {row.date_reported || "—"}
                    </td>
                    <td className="py-2 px-4 text-right text-gray-800">
                      {fmtInt(row.shares)}
                    </td>
                    <td className="py-2 px-4 text-right font-semibold text-gray-900">
                      {fmtPct(row.pct_out)}
                    </td>
                    <td className="py-2 px-4 text-right text-gray-800">
                      {fmtMM(row.value_mm)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}