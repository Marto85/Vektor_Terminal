def calculate_ratios(financial_data: list, years_range: list) -> list:
    lookup = {}
    for row_data in financial_data:
        metric = row_data["Métrica"]
        lookup[metric] = {}
        for y in years_range:
            lookup[metric][y] = row_data.get(y, 0.0)

    def get_val(metric, y):
        return lookup.get(metric, {}).get(y, 0.0)

    def safe_div(num, den):
        if den == 0.0 or den is None:
            return 0.0
        return num / den

    ratios = []
    
    for y in years_range:
        margen_bruto = safe_div(get_val("Beneficio Bruto", y), get_val("Ingresos Totales", y)) * 100
        margen_operativo = safe_div(get_val("Beneficio Operativo", y), get_val("Ingresos Totales", y)) * 100
        margen_neto = safe_div(get_val("Beneficio Neto", y), get_val("Ingresos Totales", y)) * 100
        
        roa = safe_div(get_val("Beneficio Neto", y), get_val("Total activo", y)) * 100
        roe = safe_div(get_val("Beneficio Neto", y), get_val("Patrimonio neto", y)) * 100
        
        rotacion_activos = safe_div(get_val("Ingresos Totales", y), get_val("Total activo", y))
        
        current_ratio = safe_div(get_val("Total activo corriente", y), get_val("Total pasivo corriente", y))
        quick_ratio = safe_div(get_val("Total activo corriente", y) - get_val("Inventario", y), get_val("Total pasivo corriente", y))
        cfo_a_pasivo = safe_div(get_val("Efectivo de Operaciones (CFO)", y), get_val("Total pasivo corriente", y))
        
        deuda_total = get_val("Deuda a corto plazo", y) + get_val("Deuda a largo plazo", y)
        deuda_capital = safe_div(deuda_total, get_val("Patrimonio neto", y)) * 100
        pasivo_activo = safe_div(get_val("Total pasivo", y), get_val("Total activo", y)) * 100
        
        ebitda = get_val("Beneficio Operativo", y) + get_val("Depreciación y Amortización", y)
        cobertura_intereses = safe_div(get_val("Beneficio Operativo", y), get_val("Gastos por Intereses", y))
        deuda_ebitda = safe_div(deuda_total, ebitda)
        
        ratios.append({
            "Año": y,
            "Rentabilidad sobre activos (ROA) %": {"val": roa, "pct": True},
            "Rentabilidad sobre capital (ROE) %": {"val": roe, "pct": True},
            "Margen de beneficio bruto %": {"val": margen_bruto, "pct": True},
            "Margen de beneficio operativo (EBIT) %": {"val": margen_operativo, "pct": True},
            "Margen neto %": {"val": margen_neto, "pct": True},
            "Rotación de activos (x)": {"val": rotacion_activos, "pct": False},
            "Ratio de liquidez (x)": {"val": current_ratio, "pct": False},
            "Ratio de disponibilidad (Quick Ratio) (x)": {"val": quick_ratio, "pct": False},
            "Flujo de caja operativo a pasivo corriente (x)": {"val": cfo_a_pasivo, "pct": False},
            "Deuda total / Fondos propios %": {"val": deuda_capital, "pct": True},
            "Pasivo total / Activo total %": {"val": pasivo_activo, "pct": True},
            "EBIT / Gastos por intereses (x)": {"val": cobertura_intereses, "pct": False},
            "Deuda total / EBITDA (x)": {"val": deuda_ebitda, "pct": False}
        })

    # Estructura calcada de TIKR
    secciones_tikr = [
        ("Ratios de rentabilidad:", [
            "Rentabilidad sobre activos (ROA) %", 
            "Rentabilidad sobre capital (ROE) %"
        ]),
        ("Análisis de los márgenes:", [
            "Margen de beneficio bruto %", 
            "Margen de beneficio operativo (EBIT) %", 
            "Margen neto %"
        ]),
        ("Rotación de activos:", [
            "Rotación de activos (x)"
        ]),
        ("Liquidez a corto plazo:", [
            "Ratio de liquidez (x)", 
            "Ratio de disponibilidad (Quick Ratio) (x)", 
            "Flujo de caja operativo a pasivo corriente (x)"
        ]),
        ("Solvencia a largo plazo:", [
            "Deuda total / Fondos propios %", 
            "Pasivo total / Activo total %", 
            "EBIT / Gastos por intereses (x)", 
            "Deuda total / EBITDA (x)"
        ])
    ]
    
    for titulo, metricas in secciones_tikr:
        # Fila de encabezado visual
        header_row: dict = {"Categoría": "Ratios", "Métrica": titulo, "is_header": True}
        for y in years_range:
            header_row[y] = None
        financial_data.append(header_row)
        
        # Filas de datos
        for met in metricas:
            row: dict = {"Categoría": "Ratios", "Métrica": met}
            for r in ratios:
                y = r["Año"]
                val_obj = r[met]
                row[y] = round(val_obj["val"], 2)
                if val_obj["pct"]:
                    row["is_pct"] = True 
            financial_data.append(row)

    return financial_data