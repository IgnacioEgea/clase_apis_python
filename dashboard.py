from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


DATA_PATH = Path(__file__).parent / "data" / "df_total.parquet"
CITY_COLORS = {"Madrid": "#df704f", "Londres": "#4e8c91"}
MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
PLOT_FONT = "DM Sans, sans-serif"

st.set_page_config(
    page_title="Pulso climático | Madrid y Londres",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root {
        --ink: #193332;
        --muted: #657875;
        --paper: #f5f6f1;
        --line: #e4e8df;
        --coral: #df704f;
        --teal: #4e8c91;
        --forest: #234947;
    }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp {
        color: var(--ink);
        background:
            radial-gradient(ellipse at 93% 3%, rgba(226, 167, 113, .13), transparent 27rem),
            radial-gradient(ellipse at 2% 28%, rgba(78, 140, 145, .09), transparent 29rem),
            var(--paper);
    }
    .block-container { max-width: 1440px; padding: 2.2rem 3rem 4rem; }
    [data-testid="stSidebar"] {
        background: #edf0e9;
        border-right: 1px solid var(--line);
        color: var(--ink);
        color-scheme: light;
    }
    [data-testid="stSidebar"] > div { padding-top: 2rem; }
    [data-testid="stSidebar"] * { color: var(--ink); }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] label p,
    [data-testid="stSidebar"] [data-testid="stTickBar"] span {
        color: var(--ink);
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        color: var(--ink);
        background-color: #fff;
        border-color: #d5ded4;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] input {
        color: var(--ink);
        -webkit-text-fill-color: var(--ink);
    }
    [data-testid="stSidebar"] [data-testid="stSlider"] [role="slider"] {
        border-color: var(--forest);
    }
    [data-testid="stSidebar"] [data-testid="stToggle"] {
        color: var(--ink);
    }
    .sidebar-intro {
        padding:.9rem 1rem; margin:.25rem 0 1rem;
        border:1px solid #dce4da; border-radius:13px;
        background:rgba(255,255,255,.72);
        color:#3e5652; font-size:.84rem; line-height:1.6;
    }
    .sidebar-help {
        color:#536a65; font-size:.78rem; line-height:1.6;
    }
    h1, h2, h3 { color: var(--ink); font-family: 'Manrope', sans-serif !important; }
    h1 { font-size: clamp(2.65rem, 5vw, 4.15rem) !important; font-weight: 800 !important; letter-spacing: -.065em !important; line-height: 1.06 !important; }
    h2 { font-size: 1.38rem !important; font-weight: 750 !important; letter-spacing: -.035em; }
    h3 { font-size: 1.04rem !important; font-weight: 700 !important; }
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, .88);
        border: 1px solid var(--line);
        border-radius: 15px;
        padding: 1.2rem 1.25rem;
        box-shadow: 0 8px 28px rgba(29, 56, 48, .035);
        min-height: 128px;
    }
    [data-testid="stMetricLabel"] { color: var(--muted); font-size: .88rem; }
    [data-testid="stMetricValue"] {
        color: var(--ink);
        font-family: 'Manrope', sans-serif;
        font-size: clamp(1.4rem, 2vw, 2rem);
        font-weight: 750;
    }
    [data-testid="stPlotlyChart"] {
        background: rgba(255, 255, 255, .88);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: .6rem;
        box-shadow: 0 8px 28px rgba(29, 56, 48, .035);
    }
    [data-testid="stCaptionContainer"] p { color: var(--muted); }
    .masthead {
        display:flex; justify-content:space-between; align-items:center; gap:1rem;
        padding-bottom:1.1rem; margin-bottom:2rem; border-bottom:1px solid var(--line);
    }
    .brand { display:flex; align-items:center; gap:.7rem; color:var(--forest); font-weight:700; letter-spacing:-.02em; }
    .brand-mark {
        display:grid; place-items:center; width:34px; height:34px; border-radius:11px;
        color:white; background:var(--forest); font-size:1.05rem;
    }
    .edition { color:var(--muted); font-size:.78rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase; }
    .hero {
        position:relative; overflow:hidden; padding:2.4rem 2.6rem; border-radius:24px;
        color:#f7f5ee; background:linear-gradient(116deg,#1e4140 0%,#285653 63%,#386967 100%);
        box-shadow:0 18px 48px rgba(31,68,63,.16);
    }
    .hero:after {
        content:""; position:absolute; width:320px; height:320px; right:3%; top:-56%;
        border:1px solid rgba(255,255,255,.14); border-radius:50%;
        box-shadow:0 0 0 34px rgba(255,255,255,.035),0 0 0 70px rgba(255,255,255,.025);
    }
    .hero-kicker { color:#e7b994; font-size:.74rem; font-weight:700; letter-spacing:.17em; text-transform:uppercase; }
    .hero h1 { color:#f7f5ee; margin:.6rem 0 .75rem; }
    .hero-copy { max-width:670px; color:rgba(247,245,238,.77); font-size:1rem; line-height:1.7; }
    .city-pills { display:flex; gap:.6rem; margin-top:1.5rem; flex-wrap:wrap; }
    .city-pill {
        display:inline-flex; align-items:center; gap:.5rem; padding:.5rem .8rem;
        border:1px solid rgba(255,255,255,.2); border-radius:99px;
        background:rgba(255,255,255,.07); font-size:.8rem; font-weight:600;
    }
    .city-dot { width:8px; height:8px; border-radius:50%; background:#e98a69; }
    .city-dot.london { background:#81b7b6; }
    .section-heading { display:flex; align-items:center; gap:.8rem; margin:2.55rem 0 .35rem; }
    .section-number {
        display:grid; place-items:center; width:30px; height:30px; flex:0 0 30px;
        border:1px solid #d6e0d6; border-radius:10px; color:var(--forest);
        background:#e9eee6; font-size:.76rem; font-weight:700;
    }
    .section-heading h2 { margin:0; }
    .section-note { margin:0 0 1.1rem 2.85rem; color:var(--muted); font-size:.9rem; line-height:1.6; }
    .insight {
        padding:1rem 1.2rem; border:1px solid #dfe7dc; border-left:3px solid #7fa89a;
        border-radius:0 12px 12px 0; background:rgba(255,255,255,.66);
        color:#3e5652; line-height:1.7;
    }
    .profile-card {
        height:100%; padding:1.1rem 1.15rem .2rem; border:1px solid var(--line);
        border-radius:16px; background:rgba(255,255,255,.5);
    }
    .profile-card h3 { margin:.15rem 0 .2rem; }
    .profile-card p { margin:0; color:var(--muted); font-size:.84rem; line-height:1.5; }
    .footer {
        margin-top:3.25rem; padding-top:1.1rem; border-top:1px solid var(--line);
        color:var(--muted); font-size:.78rem; line-height:1.7;
    }
    @media (max-width: 800px) {
        .block-container { padding: 1.2rem 1rem 3rem; }
        .hero { padding:1.7rem 1.3rem; border-radius:18px; }
        .masthead { margin-bottom:1.2rem; }
        .edition { font-size:.64rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Cargando registros meteorológicos...")
def load_data(file_modified_time: int) -> pd.DataFrame:
    return pd.read_parquet(DATA_PATH, engine="pyarrow")


def section_heading(number: str, title: str, note: str) -> None:
    st.markdown(
        f'<div class="section-heading"><span class="section-number">{number}</span>'
        f"<h2>{title}</h2></div><p class=\"section-note\">{note}</p>",
        unsafe_allow_html=True,
    )


def style_figure(figure: go.Figure, height: int = 390) -> go.Figure:
    figure.update_layout(
        height=height,
        margin={"l": 16, "r": 16, "t": 28, "b": 12},
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font={"family": PLOT_FONT, "color": "#193332", "size": 11},
        legend={
            "orientation": "h",
            "y": 1.12,
            "x": 0,
            "xanchor": "left",
            "font": {"size": 11},
        },
        hoverlabel={"bgcolor": "#193332", "font": {"color": "#ffffff"}},
    )
    figure.update_xaxes(showgrid=False, linecolor="#e4e8df", tickfont={"color": "#657875"})
    figure.update_yaxes(
        gridcolor="#e9ede6",
        zeroline=False,
        linecolor="#e4e8df",
        tickfont={"color": "#657875"},
    )
    return figure


def build_temperature_figure(
    historical: pd.DataFrame, estimated: pd.DataFrame, show_forecast: bool
) -> go.Figure:
    figure = go.Figure()
    for city, color in CITY_COLORS.items():
        city_data = historical.loc[historical["city"].eq(city)].sort_values("date")
        if city_data.empty:
            continue
        dates = city_data["date"]
        fill_color = "rgba(223,112,79,.12)" if city == "Madrid" else "rgba(78,140,145,.13)"
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
                name=f"{city} · rango diario",
                hovertemplate="%{x|%b %Y}<br>Máxima: %{y:.1f} °C<extra>" + city + "</extra>",
            )
        )

    for city, color in CITY_COLORS.items():
        city_data = historical.loc[historical["city"].eq(city)].sort_values("date")
        if not city_data.empty:
            figure.add_trace(
                go.Scatter(
                    x=city_data["date"],
                    y=city_data["metrics.temperature.avg"],
                    mode="lines",
                    name=f"{city} · media",
                    line={"color": color, "width": 2.8},
                    hovertemplate="%{x|%b %Y}<br>Media: %{y:.1f} °C<extra>" + city + "</extra>",
                )
            )
        city_estimates = estimated.loc[estimated["city"].eq(city)].sort_values("date")
        if show_forecast and not city_estimates.empty:
            figure.add_trace(
                go.Scatter(
                    x=city_estimates["date"],
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
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.12, "x": 0, "xanchor": "left", "font": {"size": 10}},
        xaxis_title="Año",
        yaxis_title="Temperatura (°C)",
    )
    return style_figure(figure, 430)


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
                marker={"size": 7, "color": color, "line": {"color": "#fff", "width": 1.5}},
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

    temperature_figure.update_layout(
        hovermode="x unified",
        xaxis_title=None,
        yaxis_title="Temperatura media (°C)",
        legend={"orientation": "h", "y": 1.16, "x": 0, "xanchor": "left"},
    )
    precipitation_figure.update_layout(
        barmode="group",
        bargap=0.28,
        hovermode="x unified",
        xaxis_title=None,
        yaxis_title="Precipitación media (mm)",
        legend={"orientation": "h", "y": 1.16, "x": 0, "xanchor": "left"},
    )
    return style_figure(temperature_figure, 330), style_figure(precipitation_figure, 330), monthly


if not DATA_PATH.exists():
    st.error(f"No se encontró el fichero de datos: {DATA_PATH}")
    st.stop()

try:
    df = load_data(DATA_PATH.stat().st_mtime_ns)
except Exception as error:
    st.error(f"No se pudieron leer los datos Parquet: {error}")
    st.stop()

if "data_type" not in df.columns:
    df["data_type"] = "real"

required_columns = {
    "city",
    "year",
    "month",
    "metrics.temperature.max",
    "metrics.temperature.avg",
    "metrics.temperature.min",
    "metrics.precipitation.avg",
}
missing_columns = required_columns.difference(df.columns)
if missing_columns:
    st.error(f"Faltan columnas necesarias en el Parquet: {', '.join(sorted(missing_columns))}")
    st.stop()

cities = [city for city in CITY_COLORS if city in df["city"].unique()]
if len(cities) < 2:
    st.error("El fichero debe contener datos tanto de Madrid como de Londres.")
    st.stop()

historical_years = sorted(
    df.loc[df["data_type"].eq("real"), "year"].dropna().astype(int).unique().tolist()
)
if not historical_years:
    st.error("No hay años de observaciones históricas disponibles.")
    st.stop()

st.sidebar.markdown('<div class="eyebrow">PANEL DE EXPLORACIÓN</div>', unsafe_allow_html=True)
st.sidebar.markdown(
    '<div class="sidebar-intro"><strong>Explora los datos</strong><br>'
    "Elige los años que quieres comparar y decide si mostrar la tendencia estimada.</div>",
    unsafe_allow_html=True,
)
year_range = st.sidebar.select_slider(
    "Años de observación",
    options=historical_years,
    value=(historical_years[0], historical_years[-1]),
)
show_forecast = st.sidebar.toggle("Mostrar estimaciones hasta 2036", value=True)
st.sidebar.markdown("---")
st.sidebar.markdown(
    '<div class="sidebar-help"><strong>Cómo leer los gráficos</strong><br>'
    '<span style="color:#df704f">●</span> Madrid &nbsp; '
    '<span style="color:#4e8c91">●</span> Londres<br>'
    "El área sombreada muestra el rango térmico. "
    "La línea discontinua indica máximas estimadas.</div>",
    unsafe_allow_html=True,
)

historical = df.loc[
    df["data_type"].eq("real") & df["year"].between(year_range[0], year_range[1])
].copy()
estimated = df.loc[df["data_type"].eq("estimado")].copy()
for records in (historical, estimated):
    records["date"] = pd.to_datetime(
        {"year": records["year"].astype(int), "month": records["month"].astype(int), "day": 1}
    )

period_coverage = historical.groupby(["year", "month"])["city"].nunique()
shared_periods = period_coverage.loc[period_coverage.eq(2)]
if shared_periods.empty:
    st.warning("No hay un mes compartido por ambas ciudades dentro del periodo seleccionado.")
    st.stop()

latest_year, latest_month = max(shared_periods.index)
latest = historical.loc[
    historical["year"].eq(latest_year) & historical["month"].eq(latest_month)
].set_index("city")
latest_label = f"{MONTH_NAMES[int(latest_month) - 1]} {int(latest_year)}"

st.markdown(
    '<div class="masthead"><div class="brand"><span class="brand-mark">◒</span>'
    "OBSERVATORIO DEL CLIMA</div><div class=\"edition\">Madrid · Londres &nbsp; / &nbsp; Serie mensual</div></div>",
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="hero"><div class="hero-kicker">Una mirada al clima urbano</div>'
    f"<h1>Pulso climático</h1>"
    f'<div class="hero-copy">Dos ciudades, dos maneras de vivir las estaciones. '
    f'Explora la evolución de la temperatura y la lluvia entre {year_range[0]} y '
    f'{year_range[1]}, y consulta la tendencia estimada para la próxima década.</div>'
    f'<div class="city-pills"><span class="city-pill"><span class="city-dot"></span>Madrid</span>'
    f'<span class="city-pill"><span class="city-dot london"></span>Londres</span></div></div>',
    unsafe_allow_html=True,
)

section_heading(
    "01",
    "El último dato compartido",
    f"Instantánea comparativa de {latest_label}. Temperatura media mensual y precipitación acumulada.",
)
metric_columns = st.columns(4)
metric_columns[0].metric(
    "Temperatura media · Madrid",
    f"{latest.loc['Madrid', 'metrics.temperature.avg']:.1f} °C",
)
metric_columns[1].metric(
    "Temperatura media · Londres",
    f"{latest.loc['Londres', 'metrics.temperature.avg']:.1f} °C",
)
metric_columns[2].metric(
    "Precipitación · Madrid",
    f"{latest.loc['Madrid', 'metrics.precipitation.avg']:.1f} mm",
)
metric_columns[3].metric(
    "Precipitación · Londres",
    f"{latest.loc['Londres', 'metrics.precipitation.avg']:.1f} mm",
)

section_heading(
    "02",
    "El ritmo de la temperatura",
    "El área sombreada representa el rango entre mínimas y máximas. Las líneas muestran la temperatura media; las discontinuas, la máxima estimada.",
)
temperature_figure = build_temperature_figure(historical, estimated, show_forecast)
st.plotly_chart(
    temperature_figure,
    width="stretch",
    config={"displaylogo": False, "responsive": True},
)

peak = historical.loc[historical["metrics.temperature.max"].idxmax()]
mean_ranges = (
    historical.groupby("city")["thermal_range"].mean()
    if "thermal_range" in historical
    else (historical["metrics.temperature.max"] - historical["metrics.temperature.min"])
    .groupby(historical["city"])
    .mean()
)
range_difference = mean_ranges["Madrid"] - mean_ranges["Londres"]
if range_difference > 0:
    range_sentence = f"Madrid tiene una oscilación térmica media {abs(range_difference):.1f} °C mayor."
elif range_difference < 0:
    range_sentence = f"Londres tiene una oscilación térmica media {abs(range_difference):.1f} °C mayor."
else:
    range_sentence = "La oscilación térmica media es similar en ambas ciudades."
st.markdown(
    f'<div class="insight"><strong>Una pista del periodo</strong><br>'
    f'El máximo observado fue de <strong>{peak["metrics.temperature.max"]:.1f} °C</strong> '
    f'en {peak["city"]}, en {MONTH_NAMES[int(peak["month"]) - 1]} de {int(peak["year"])}. '
    f'{range_sentence}</div>',
    unsafe_allow_html=True,
)

section_heading(
    "03",
    "Un año, dos climas",
    "Promedio de los años seleccionados. Temperatura y precipitación se muestran por separado para comparar sus valores sin mezclar unidades.",
)
temperature_monthly, precipitation_monthly, monthly = build_monthly_figures(historical)
temperature_column, precipitation_column = st.columns(2, gap="large")
with temperature_column:
    st.markdown(
        '<div class="profile-card"><h3>Temperatura media</h3>'
        '<p>El ciclo estacional a lo largo del año · °C</p></div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        temperature_monthly,
        width="stretch",
        config={"displaylogo": False, "responsive": True},
    )
with precipitation_column:
    st.markdown(
        '<div class="profile-card"><h3>Calendario de lluvia</h3>'
        '<p>Promedio mensual de precipitación · mm</p></div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        precipitation_monthly,
        width="stretch",
        config={"displaylogo": False, "responsive": True},
    )

hottest_months = monthly.loc[monthly.groupby("city")["temperature"].idxmax()].set_index("city")
wettest_months = monthly.loc[monthly.groupby("city")["precipitation"].idxmax()].set_index("city")
monthly_summary = " ".join(
    f"En {city}, el mes más cálido es {MONTH_NAMES[int(hottest_months.loc[city, 'month']) - 1]} "
    f"({hottest_months.loc[city, 'temperature']:.1f} °C) y el más lluvioso es "
    f"{MONTH_NAMES[int(wettest_months.loc[city, 'month']) - 1]} "
    f"({wettest_months.loc[city, 'precipitation']:.1f} mm)."
    for city in cities
)
st.markdown(
    f'<div class="insight"><strong>La estación también cuenta</strong><br>'
    f'{monthly_summary}</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="footer"><strong>Sobre estos datos</strong><br>'
    f'Observaciones meteorológicas mensuales de {year_range[0]}–{year_range[1]}. '
    f'Las máximas futuras son estimaciones lineales basadas en la tendencia histórica '
    f'por ciudad y mes; no son predicciones meteorológicas diarias.</div>',
    unsafe_allow_html=True,
)
