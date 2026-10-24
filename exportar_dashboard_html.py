from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.offline import get_plotlyjs


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "df_total.parquet"
OUTPUT_PATH = PROJECT_ROOT / "output" / "dashboard_climatico.html"
CITY_COLORS = {"Madrid": "#df704f", "Londres": "#4e8c91"}
MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"No se encontró el fichero de datos: {DATA_PATH}")

    dataframe = pd.read_parquet(DATA_PATH, engine="pyarrow")
    required_columns = {
        "city",
        "year",
        "month",
        "data_type",
        "metrics.temperature.max",
        "metrics.temperature.avg",
        "metrics.temperature.min",
        "metrics.precipitation.avg",
    }
    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        raise ValueError(
            f"Faltan columnas necesarias en el Parquet: {', '.join(sorted(missing_columns))}"
        )
    if not {"Madrid", "Londres"}.issubset(set(dataframe["city"].dropna())):
        raise ValueError("El fichero debe contener datos tanto de Madrid como de Londres.")
    return dataframe


def build_temperature_figure(
    historical: pd.DataFrame, estimated: pd.DataFrame
) -> go.Figure:
    figure = go.Figure()
    for city, color in CITY_COLORS.items():
        city_data = historical.loc[historical["city"].eq(city)].sort_values(
            ["year", "month"]
        )
        city_estimates = estimated.loc[estimated["city"].eq(city)].sort_values(
            ["year", "month"]
        )
        dates = pd.to_datetime(
            {"year": city_data["year"], "month": city_data["month"], "day": 1}
        )
        estimate_dates = pd.to_datetime(
            {"year": city_estimates["year"], "month": city_estimates["month"], "day": 1}
        )
        fill_color = (
            "rgba(223, 112, 79, .12)"
            if city == "Madrid"
            else "rgba(78, 140, 145, .13)"
        )

        figure.add_trace(
            go.Scatter(
                x=dates,
                y=city_data["metrics.temperature.min"],
                mode="lines",
                line={"width": 0},
                showlegend=False,
                hoverinfo="skip",
                name=f"{city} · mínima",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=dates,
                y=city_data["metrics.temperature.max"],
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                fillcolor=fill_color,
                showlegend=False,
                name=f"{city} · rango",
                hovertemplate="%{x|%b %Y}<br>Máxima: %{y:.1f} °C<extra>" + city + "</extra>",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=dates,
                y=city_data["metrics.temperature.avg"],
                mode="lines",
                name=city,
                line={"color": color, "width": 2.8},
                hovertemplate="%{x|%b %Y}<br>Media: %{y:.1f} °C<extra>" + city + "</extra>",
            )
        )
        if not city_estimates.empty:
            figure.add_trace(
                go.Scatter(
                    x=estimate_dates,
                    y=city_estimates["metrics.temperature.max"],
                    mode="lines",
                    name=f"{city} · máxima estimada",
                    line={"color": color, "width": 2, "dash": "dash"},
                    hovertemplate="%{x|%b %Y}<br>Máxima estimada: %{y:.1f} °C<extra>"
                    + city
                    + "</extra>",
                )
            )

    figure.update_layout(
        height=430,
        margin={"l": 16, "r": 16, "t": 28, "b": 12},
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.12, "x": 0, "xanchor": "left"},
        xaxis={"title": "Año", "showgrid": False, "linecolor": "#e4e8df"},
        yaxis={"title": "Temperatura (°C)", "gridcolor": "#e9ede6", "zeroline": False},
        font={"family": "DM Sans, sans-serif", "color": "#193332"},
    )
    return figure


def build_monthly_figures(
    historical: pd.DataFrame,
) -> tuple[go.Figure, go.Figure, pd.DataFrame]:
    monthly = (
        historical.groupby(["city", "month"])
        .agg(
            temperature=("metrics.temperature.avg", "mean"),
            precipitation=("metrics.precipitation.avg", "mean"),
        )
        .reset_index()
    )
    temperature_figure = go.Figure()
    precipitation_figure = go.Figure()
    for city, color in CITY_COLORS.items():
        city_monthly = monthly.loc[monthly["city"].eq(city)].sort_values("month")
        labels = [MONTH_NAMES[int(month) - 1][:3] for month in city_monthly["month"]]
        temperature_figure.add_trace(
            go.Scatter(
                x=labels,
                y=city_monthly["temperature"],
                mode="lines+markers",
                name=city,
                line={"color": color, "width": 2.8},
                marker={"size": 7, "color": color},
                hovertemplate="%{x}<br>Media: %{y:.1f} °C<extra>" + city + "</extra>",
            )
        )
        precipitation_figure.add_trace(
            go.Bar(
                x=labels,
                y=city_monthly["precipitation"],
                name=city,
                marker={"color": color, "cornerradius": 5},
                opacity=0.88,
                hovertemplate="%{x}<br>Precipitación: %{y:.1f} mm<extra>" + city + "</extra>",
            )
        )

    for figure, axis_title in (
        (temperature_figure, "Temperatura media (°C)"),
        (precipitation_figure, "Precipitación media (mm)"),
    ):
        figure.update_layout(
            height=330,
            margin={"l": 16, "r": 16, "t": 28, "b": 12},
            paper_bgcolor="rgba(255,255,255,0)",
            plot_bgcolor="rgba(255,255,255,0)",
            hovermode="x unified",
            legend={"orientation": "h", "y": 1.15, "x": 0, "xanchor": "left"},
            xaxis={"showgrid": False, "linecolor": "#e4e8df"},
            yaxis={"title": axis_title, "gridcolor": "#e9ede6", "zeroline": False},
            font={"family": "DM Sans, sans-serif", "color": "#193332"},
        )
    precipitation_figure.update_layout(barmode="group", bargap=0.28)
    return temperature_figure, precipitation_figure, monthly


def figure_html(figure: go.Figure) -> str:
    return pio.to_html(
        figure,
        full_html=False,
        include_plotlyjs=False,
        config={"displaylogo": False, "responsive": True},
    )


def render_html(dataframe: pd.DataFrame) -> str:
    historical = dataframe.loc[dataframe["data_type"].eq("real")].copy()
    estimated = dataframe.loc[dataframe["data_type"].eq("estimado")].copy()
    if historical.empty:
        raise ValueError("No hay observaciones históricas para mostrar.")

    years = historical["year"].dropna().astype(int)
    start_year, end_year = int(years.min()), int(years.max())
    coverage = historical.groupby(["year", "month"])["city"].nunique()
    shared_periods = coverage.loc[coverage.eq(2)]
    if shared_periods.empty:
        raise ValueError("No hay meses compartidos por ambas ciudades.")

    latest_year, latest_month = max(shared_periods.index)
    latest = historical.loc[
        historical["year"].eq(latest_year) & historical["month"].eq(latest_month)
    ].set_index("city")
    peak = historical.loc[historical["metrics.temperature.max"].idxmax()]
    mean_ranges = historical.groupby("city")["thermal_range"].mean() if "thermal_range" in historical else (
        historical["metrics.temperature.max"] - historical["metrics.temperature.min"]
    ).groupby(historical["city"]).mean()
    range_difference = mean_ranges["Madrid"] - mean_ranges["Londres"]
    if range_difference > 0:
        range_sentence = f"Madrid presenta una oscilación media {abs(range_difference):.1f} °C mayor."
    elif range_difference < 0:
        range_sentence = f"Londres presenta una oscilación media {abs(range_difference):.1f} °C mayor."
    else:
        range_sentence = "La oscilación térmica media es similar en ambas ciudades."

    temperature_monthly, precipitation_monthly, monthly = build_monthly_figures(historical)
    hottest = monthly.loc[monthly.groupby("city")["temperature"].idxmax()].set_index("city")
    wettest = monthly.loc[monthly.groupby("city")["precipitation"].idxmax()].set_index("city")
    monthly_summary = " ".join(
        f"En {city}, el mes más cálido es {MONTH_NAMES[int(hottest.loc[city, 'month']) - 1]} "
        f"({hottest.loc[city, 'temperature']:.1f} °C) y el más lluvioso es "
        f"{MONTH_NAMES[int(wettest.loc[city, 'month']) - 1]} "
        f"({wettest.loc[city, 'precipitation']:.1f} mm)."
        for city in CITY_COLORS
    )

    template = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pulso climático · Madrid y Londres</title>
  <style>
    :root { --ink:#193332; --muted:#657875; --paper:#f5f6f1; --line:#e4e8df; }
    * { box-sizing:border-box; }
    body {
      margin:0; color:var(--ink); background-color:var(--paper);
      background-image:radial-gradient(ellipse at 93% 3%,rgba(226,167,113,.13),transparent 27rem),
        radial-gradient(ellipse at 2% 28%,rgba(78,140,145,.09),transparent 29rem);
      font-family:'DM Sans',Arial,sans-serif;
    }
    .app-shell { display:flex; min-height:100vh; }
    aside {
      position:sticky; top:0; width:258px; height:100vh; flex:0 0 258px;
      padding:28px 20px; border-right:1px solid #dfe5db; background:rgba(237,240,233,.94);
      color:#193332;
    }
    .side-brand { display:flex; align-items:center; gap:10px; color:#234947; font-weight:700; font-size:.9rem; }
    .side-mark { display:grid; place-items:center; width:34px; height:34px; border-radius:11px; color:white; background:#234947; font-size:1rem; }
    .side-label { margin:32px 0 10px; color:#657875; font-size:.68rem; font-weight:700; letter-spacing:.13em; text-transform:uppercase; }
    .side-nav { display:grid; gap:5px; }
    .side-nav a { display:block; padding:10px 11px; border-radius:9px; color:#294541; text-decoration:none; font-size:.84rem; font-weight:600; }
    .side-nav a:hover,.side-nav a:focus { outline:none; background:#e1e9df; color:#193332; }
    .side-divider { height:1px; margin:22px 0; background:#dce4da; }
    .side-city { display:flex; align-items:center; gap:9px; margin:12px 0; color:#294541; font-size:.84rem; font-weight:600; }
    .side-dot { width:9px; height:9px; flex:0 0 9px; border-radius:50%; background:#df704f; }
    .side-dot.london { background:#4e8c91; }
    .side-note { padding:12px; border:1px solid #dce4da; border-radius:12px; background:rgba(255,255,255,.72); color:#405b55; font-size:.78rem; line-height:1.6; }
    .side-footer { position:absolute; bottom:24px; color:#657875; font-size:.72rem; line-height:1.6; }
    main { width:min(100%,1440px); margin:0 auto; padding:32px 34px 52px; }
    h1,h2,h3 { margin:0; font-family:'Manrope',Arial,sans-serif; }
    h1 { margin:10px 0 10px; font-size:clamp(2.5rem,5vw,4rem); letter-spacing:-.065em; line-height:1.06; }
    h2 { font-size:1.3rem; letter-spacing:-.035em; }
    .masthead { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding-bottom:18px; margin-bottom:30px; border-bottom:1px solid var(--line); color:#234947; font-weight:700; letter-spacing:.02em; }
    .edition { color:var(--muted); font-size:.75rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase; }
    .hero { position:relative; overflow:hidden; padding:38px 42px; border-radius:24px; color:#f7f5ee; background:linear-gradient(116deg,#1e4140,#285653 63%,#386967); box-shadow:0 18px 48px rgba(31,68,63,.16); }
    .hero:after { content:""; position:absolute; width:320px; height:320px; right:3%; top:-56%; border:1px solid rgba(255,255,255,.14); border-radius:50%; box-shadow:0 0 0 34px rgba(255,255,255,.035),0 0 0 70px rgba(255,255,255,.025); }
    .eyebrow { color:#e7b994; font-size:.74rem; font-weight:700; letter-spacing:.17em; text-transform:uppercase; }
    .hero h1 { color:#f7f5ee; }
    .hero-copy { max-width:670px; color:rgba(247,245,238,.77); font-size:1rem; line-height:1.7; }
    .city-pills { display:flex; gap:.6rem; margin-top:20px; }
    .city-pill { padding:8px 13px; border:1px solid rgba(255,255,255,.2); border-radius:99px; background:rgba(255,255,255,.07); font-size:.8rem; font-weight:600; }
    section { margin-top:36px; }
    .section-head { display:flex; align-items:center; gap:12px; margin-bottom:5px; }
    .section-number { display:grid; place-items:center; width:30px; height:30px; border:1px solid #d6e0d6; border-radius:10px; color:#234947; background:#e9eee6; font-size:.76rem; font-weight:700; }
    .metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-top:22px; }
    .metric,.chart { background:rgba(255,255,255,.88); border:1px solid var(--line); border-radius:15px; box-shadow:0 8px 28px rgba(29,56,48,.035); }
    .metric { border-top:3px solid #7fa89a; padding:18px; }
    .metric-label { color:var(--muted); font-size:.9rem; }
    .metric-value { margin-top:8px; font-size:1.6rem; font-weight:700; }
    .chart { padding:9px; overflow:hidden; }
    .interpretation { color:#3e5652; line-height:1.7; border:1px solid #dfe7dc; border-left:3px solid #7fa89a; border-radius:0 12px 12px 0; background:rgba(255,255,255,.66); padding:12px 16px; margin-top:18px; }
    .chart-pair { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }
    .profile { margin:0 0 9px; color:var(--muted); font-size:.84rem; line-height:1.5; }
    footer { margin-top:45px; padding-top:16px; border-top:1px solid var(--line); color:var(--muted); font-size:.78rem; line-height:1.7; }
    @media (max-width:760px) {
      .app-shell { display:block; }
      aside { position:relative; width:auto; height:auto; padding:14px 16px; border-right:0; border-bottom:1px solid #dfe5db; }
      .side-label,.side-city,.side-divider,.side-note,.side-footer { display:none; }
      .side-nav { display:flex; overflow-x:auto; gap:4px; margin-top:10px; }
      .side-nav a { flex:0 0 auto; padding:8px 10px; }
      main { padding:24px 14px 36px; }
      .hero { padding:28px 22px; border-radius:18px; }
      .chart-pair { grid-template-columns:1fr; gap:14px; }
      .metrics { grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
      .metric { padding:12px; }
      .metric-value { font-size:1.3rem; }
    }
  </style>
  <script>__PLOTLY_JS__</script>
</head>
<body>
  <div class="app-shell">
  <aside>
    <div class="side-brand"><span class="side-mark">◒</span><span>OBSERVATORIO<br>DEL CLIMA</span></div>
    <div class="side-label">Navegación</div>
    <nav class="side-nav" aria-label="Navegación del dashboard">
      <a href="#resumen">01 &nbsp; Resumen</a>
      <a href="#temperatura">02 &nbsp; Temperatura</a>
      <a href="#estaciones">03 &nbsp; Estaciones</a>
    </nav>
    <div class="side-divider"></div>
    <div class="side-label">Ciudades</div>
    <div class="side-city"><span class="side-dot"></span>Madrid</div>
    <div class="side-city"><span class="side-dot london"></span>Londres</div>
    <div class="side-divider"></div>
    <div class="side-label">Cómo leerlo</div>
    <div class="side-note">El área sombreada muestra el rango entre mínimas y máximas. Las líneas discontinuas indican máximas estimadas. Pasa el cursor por los gráficos para consultar los valores.</div>
    <div class="side-footer">Vista local interactiva<br>Datos mensuales · __HISTORICAL_START__–__END_YEAR__</div>
  </aside>
  <main>
    <div class="masthead"><span>◒ &nbsp; OBSERVATORIO DEL CLIMA</span><span class="edition">Madrid · Londres / Serie mensual</span></div>
    <header class="hero">
      <div class="eyebrow">Una mirada al clima urbano</div>
      <h1>Pulso climático</h1>
      <div class="hero-copy">Dos ciudades, dos maneras de vivir las estaciones. Explora la evolución de la temperatura y la lluvia entre __START_YEAR__ y __END_YEAR__, y consulta la tendencia estimada para la próxima década.</div>
      <div class="city-pills"><span class="city-pill">● &nbsp; Madrid</span><span class="city-pill">● &nbsp; Londres</span></div>
    </header>
    <section id="resumen">
      <div class="section-head"><span class="section-number">01</span><h2>El último dato compartido</h2></div>
      <p class="caption">Último periodo compartido: __LATEST_MONTH__ de __LATEST_YEAR__</p>
      <div class="metrics">
        <div class="metric"><div class="metric-label">Temperatura media · Madrid</div><div class="metric-value">__MADRID_TEMP__ °C</div></div>
        <div class="metric"><div class="metric-label">Temperatura media · Londres</div><div class="metric-value">__LONDON_TEMP__ °C</div></div>
        <div class="metric"><div class="metric-label">Precipitación · Madrid</div><div class="metric-value">__MADRID_RAIN__ mm</div></div>
        <div class="metric"><div class="metric-label">Precipitación · Londres</div><div class="metric-value">__LONDON_RAIN__ mm</div></div>
      </div>
    </section>
    <section id="temperatura">
      <div class="section-head"><span class="section-number">02</span><h2>El ritmo de la temperatura</h2></div>
      <p class="caption">Banda y línea continua: observaciones reales. Línea discontinua: máxima estimada según la tendencia histórica.</p>
      <div class="chart">__TEMPERATURE_CHART__</div>
      <div class="interpretation"><strong>Lectura.</strong> El máximo del periodo fue __PEAK_TEMP__ °C en __PEAK_CITY__, __PEAK_MONTH__ de __PEAK_YEAR__. __RANGE_SENTENCE__</div>
    </section>
    <section id="estaciones">
      <div class="section-head"><span class="section-number">03</span><h2>Un año, dos climas</h2></div>
      <p class="caption">Promedio de todos los años disponibles. Cada gráfico conserva sus unidades para que las comparaciones sean claras.</p>
      <div class="chart-pair">
        <div><h3>Temperatura media</h3><p class="profile">El ciclo estacional a lo largo del año · °C</p><div class="chart">__TEMPERATURE_PROFILE__</div></div>
        <div><h3>Calendario de lluvia</h3><p class="profile">Promedio mensual de precipitación · mm</p><div class="chart">__PRECIPITATION_PROFILE__</div></div>
      </div>
      <div class="interpretation"><strong>La estación también cuenta.</strong> __MONTHLY_SUMMARY__</div>
    </section>
    <footer><strong>Sobre estos datos</strong><br>Observaciones meteorológicas mensuales de __HISTORICAL_START__–__HISTORICAL_END__. Las máximas futuras son estimaciones lineales basadas en la tendencia histórica por ciudad y mes; no son predicciones meteorológicas diarias.</footer>
  </main>
  </div>
</body>
</html>
"""
    replacements = {
        "__START_YEAR__": str(start_year),
        "__END_YEAR__": str(end_year),
        "__HISTORICAL_START__": str(int(historical["year"].min())),
        "__HISTORICAL_END__": str(int(historical["year"].max())),
        "__LATEST_MONTH__": MONTH_NAMES[int(latest_month) - 1],
        "__LATEST_YEAR__": str(int(latest_year)),
        "__MADRID_TEMP__": f"{latest.loc['Madrid', 'metrics.temperature.avg']:.1f}",
        "__LONDON_TEMP__": f"{latest.loc['Londres', 'metrics.temperature.avg']:.1f}",
        "__MADRID_RAIN__": f"{latest.loc['Madrid', 'metrics.precipitation.avg']:.1f}",
        "__LONDON_RAIN__": f"{latest.loc['Londres', 'metrics.precipitation.avg']:.1f}",
        "__TEMPERATURE_CHART__": figure_html(build_temperature_figure(historical, estimated)),
        "__TEMPERATURE_PROFILE__": figure_html(temperature_monthly),
        "__PRECIPITATION_PROFILE__": figure_html(precipitation_monthly),
        "__PEAK_TEMP__": f"{peak['metrics.temperature.max']:.1f}",
        "__PEAK_CITY__": str(peak["city"]),
        "__PEAK_MONTH__": MONTH_NAMES[int(peak["month"]) - 1],
        "__PEAK_YEAR__": str(int(peak["year"])),
        "__RANGE_SENTENCE__": range_sentence,
        "__MONTHLY_SUMMARY__": monthly_summary,
        "__PLOTLY_JS__": get_plotlyjs(),
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template


def main() -> None:
    html = render_html(load_data())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard HTML generado: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
