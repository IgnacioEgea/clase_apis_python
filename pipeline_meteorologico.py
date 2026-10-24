from pathlib import Path

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
CITIES = {
    "Madrid": "https://meteometrics.rlopez.org/historical-data/MAD",
    "Londres": "https://meteometrics.rlopez.org/historical-data/LON",
}
TEMPERATURE_COLUMNS = (
    "max",
    "avg",
    "min",
    "metrics.temperature.max",
    "metrics.temperature.avg",
    "metrics.temperature.min",
)


def _first_column(dataframe, candidates):
    return next((name for name in candidates if name in dataframe.columns), None)


def limpiar_datos_meteorologicos(dataframe):
    """Normaliza, limpia y ordena las observaciones meteorológicas reales."""
    dataframe = dataframe.copy()
    initial_count = len(dataframe)
    city_column = _first_column(dataframe, ("city_name", "city"))
    temperature_unit = _first_column(
        dataframe, ("unit", "metrics.temperature.unit")
    )
    precipitation_unit = "metrics.precipitation.unit"

    if city_column is None or not {"year", "month"}.issubset(dataframe.columns):
        raise ValueError("Se requieren ciudad, year y month para limpiar los registros.")

    unit_columns = {
        name
        for name in (temperature_unit, precipitation_unit)
        if name is not None and name in dataframe.columns
    }
    city_columns = {name for name in ("city_name", "city") if name in dataframe.columns}
    metric_columns = [
        name
        for name in dataframe.columns
        if name not in unit_columns
        and (name.startswith("metrics.") or name in TEMPERATURE_COLUMNS[:3])
    ]

    # Normaliza comas decimales antes de inferir los valores numéricos.
    dataframe[metric_columns] = dataframe[metric_columns].replace(",", ".", regex=True)
    numeric_columns = dataframe.columns.difference(unit_columns | city_columns)
    dataframe[numeric_columns] = dataframe[numeric_columns].apply(
        pd.to_numeric, errors="coerce"
    )
    # Convierte explícitamente el centinela conocido en un dato ausente.
    dataframe[numeric_columns] = dataframe[numeric_columns].mask(
        dataframe[numeric_columns].eq(-999.0)
    )

    # Entre duplicados conserva el registro con menos valores ausentes.
    dataframe["_missing_count"] = dataframe.isna().sum(axis=1)
    dataframe = dataframe.sort_values("_missing_count", kind="stable")
    dataframe = dataframe.drop_duplicates(
        subset=[city_column, "year", "month"], keep="first"
    ).drop(columns="_missing_count")
    dataframe = dataframe.sort_values(
        [city_column, "year", "month"], kind="stable"
    ).reset_index(drop=True)

    # La unidad es compartida: convierte máxima, media y mínima juntas.
    if temperature_unit is not None:
        temperature_columns = [
            name for name in TEMPERATURE_COLUMNS if name in dataframe.columns
        ]
        is_fahrenheit = dataframe[temperature_unit].eq("F")
        dataframe.loc[is_fahrenheit, temperature_columns] = (
            dataframe.loc[is_fahrenheit, temperature_columns].sub(32).mul(5).div(9)
        )
        dataframe.loc[is_fahrenheit, temperature_unit] = "C"

    # Estandariza la precipitación de Londres a milímetros.
    if {precipitation_unit, "metrics.precipitation.avg"}.issubset(dataframe.columns):
        is_inches = dataframe[precipitation_unit].eq("inches")
        dataframe.loc[is_inches, "metrics.precipitation.avg"] *= 25.4
        dataframe.loc[is_inches, precipitation_unit] = "mm"

    return dataframe, initial_count


def añadir_estimaciones_temperatura(dataframe, horizon=10):
    """Calcula medias mensuales reales y proyecta máximas por ciudad y mes."""
    if horizon < 1:
        raise ValueError("El horizonte de estimación debe ser al menos un año.")

    dataframe = dataframe.copy()
    city_column = _first_column(dataframe, ("city_name", "city"))
    maximum_column = _first_column(
        dataframe, ("max", "metrics.temperature.max")
    )
    if city_column is None or maximum_column is None:
        raise ValueError("Se requieren una ciudad y la temperatura máxima.")

    groups = [city_column, "month"]
    dataframe["data_type"] = "real"
    # El promedio de referencia se calcula antes de crear filas estimadas.
    dataframe["media"] = dataframe.groupby(groups)[maximum_column].transform("mean")
    dataframe["diferencia_temperatura_maxima"] = (
        dataframe[maximum_column] - dataframe["media"]
    )

    observed = dataframe[[city_column, "year", "month", maximum_column]].dropna()
    if observed.empty:
        return dataframe

    # Ajusta una recta por ciudad y mes con sumas agrupadas de los datos reales.
    observed = observed.assign(
        year_squared=observed["year"] ** 2,
        year_max=observed["year"] * observed[maximum_column],
    )
    trend = observed.groupby(groups).agg(
        count=(maximum_column, "count"),
        sum_year=("year", "sum"),
        sum_max=(maximum_column, "sum"),
        sum_year_squared=("year_squared", "sum"),
        sum_year_max=("year_max", "sum"),
    ).reset_index()
    numerator = trend["count"] * trend["sum_year_max"] - trend["sum_year"] * trend["sum_max"]
    denominator = trend["count"] * trend["sum_year_squared"] - trend["sum_year"] ** 2
    trend["slope"] = numerator.div(denominator.where(denominator.ne(0))).fillna(0)
    trend["mean_year"] = trend["sum_year"] / trend["count"]
    trend["mean_max"] = trend["sum_max"] / trend["count"]
    monthly_mean = dataframe.groupby(groups)[maximum_column].mean().rename("media")
    trend = trend.merge(monthly_mean, on=groups)

    # Proyecta diez años desde el último año con datos disponibles.
    last_year = int(observed["year"].max())
    future_years = pd.DataFrame({"year": range(last_year + 1, last_year + horizon + 1)})
    estimated = trend.merge(future_years, how="cross")
    estimated[maximum_column] = estimated["mean_max"] + estimated["slope"] * (
        estimated["year"] - estimated["mean_year"]
    )
    estimated = estimated.dropna(subset=[maximum_column, "media"])
    estimated["diferencia_temperatura_maxima"] = (
        estimated[maximum_column] - estimated["media"]
    )
    estimated["data_type"] = "estimado"

    estimated_columns = groups + [
        "year",
        maximum_column,
        "media",
        "diferencia_temperatura_maxima",
        "data_type",
    ]
    if "city" in dataframe.columns and city_column != "city":
        estimated["city"] = estimated[city_column]
        estimated_columns.append("city")
    unit_column = _first_column(
        dataframe, ("unit", "metrics.temperature.unit")
    )
    if unit_column is not None:
        estimated[unit_column] = "C"
        estimated_columns.append(unit_column)

    estimated = estimated[estimated_columns].drop_duplicates(
        subset=[city_column, "year", "month"]
    )
    combined = pd.concat([dataframe, estimated], ignore_index=True, sort=False)
    return combined.sort_values(
        [city_column, "year", "month"], kind="stable"
    ).reset_index(drop=True)


def enriquecer_datos(dataframe):
    """Añade indicadores vectorizados y las máximas mensuales estimadas."""
    dataframe = dataframe.copy()
    maximum_column = _first_column(
        dataframe, ("max", "metrics.temperature.max")
    )
    minimum_column = _first_column(
        dataframe, ("min", "metrics.temperature.min")
    )
    city_column = _first_column(dataframe, ("city_name", "city"))
    precipitation_column = "metrics.precipitation.avg"

    dataframe["data_type"] = "real"
    dataframe["thermal_range"] = dataframe[maximum_column] - dataframe[minimum_column]
    dataframe["cumulative_rain_year"] = dataframe.groupby(
        [city_column, "year"]
    )[precipitation_column].cumsum()
    dataframe["kpi.heat_stress_index"] = dataframe[maximum_column].div(
        dataframe[precipitation_column].add(1)
    )

    mean_temperature = "metrics.temperature.avg"
    if mean_temperature in dataframe.columns:
        city_mean = dataframe.groupby(city_column)[mean_temperature].transform("mean")
        city_std = dataframe.groupby(city_column)[mean_temperature].transform("std")
        dataframe["kpi.temp_zscore"] = (
            dataframe[mean_temperature] - city_mean
        ).div(city_std.where(city_std.ne(0)))

    return añadir_estimaciones_temperatura(dataframe)


def generar_graficas(dataframe):
    """Guarda las cuatro gráficas con observaciones reales en output/."""
    import matplotlib.pyplot as plt
    import seaborn as sns

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    real = dataframe.loc[dataframe["data_type"].eq("real")]
    august = real.loc[real["month"].eq(8)]
    colors = {"Madrid": "#c62828", "Londres": "#2878b5"}
    cities = ("Madrid", "Londres")

    figure, axis = plt.subplots(figsize=(10, 6))
    sns.lineplot(
        data=august,
        x="year",
        y="metrics.temperature.max",
        hue="city",
        marker="o",
        palette=colors,
        ax=axis,
    )
    axis.set(title="Temperatura máxima en agosto por año", xlabel="Año", ylabel="Temperatura (°C)")
    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "temperatura_maxima_agosto.png", dpi=300)
    plt.close(figure)

    # Un panel por ciudad conserva las unidades de precipitación de cada serie.
    figure, axes = plt.subplots(1, 2, figsize=(14, 6))
    for city, axis in zip(cities, axes):
        city_data = august.loc[august["city"].eq(city)].sort_values("year")
        x_values = range(len(city_data))
        axis.bar(x_values, city_data["metrics.precipitation.avg"], color="#5b9e78")
        axis.set_title(city)
        axis.set_ylabel(
            f"Precipitación ({city_data['metrics.precipitation.unit'].iloc[0]})"
        )
        axis.set_xticks(x_values, city_data["year"].astype(str), rotation=45)
        axis.set_xlabel("Año")
        temperature_axis = axis.twinx()
        temperature_axis.plot(
            x_values,
            city_data["metrics.temperature.avg"],
            color=colors[city],
            marker="o",
        )
        temperature_axis.set_ylabel("Temperatura media (°C)")
    figure.suptitle("Climograma de agosto")
    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "climograma_agosto.png", dpi=300)
    plt.close(figure)

    # Separa las ciudades para comparar sus patrones térmicos mensuales.
    temperatures = real["metrics.temperature.avg"]
    minimum, maximum = temperatures.min(), temperatures.max()
    figure, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=True)
    month_names = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    for city, axis in zip(cities, axes):
        city_data = real.loc[real["city"].eq(city)]
        matrix = city_data.pivot(
            index="month", columns="year", values="metrics.temperature.avg"
        ).reindex(range(1, 13))
        matrix.index = month_names
        sns.heatmap(
            matrix,
            ax=axis,
            cmap="coolwarm",
            vmin=minimum,
            vmax=maximum,
            cbar_kws={"label": "Temperatura media (°C)"},
        )
        axis.set(title=city, xlabel="Año", ylabel="Mes")
    figure.suptitle("Temperatura media mensual")
    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "mapa_calor_temperaturas.png", dpi=300)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(10, 6))
    sns.scatterplot(
        data=real,
        x="metrics.temperature.max",
        y="metrics.uv_index_max",
        hue="city",
        style="city",
        palette=colors,
        ax=axis,
    )
    axis.set(
        title="Temperatura máxima e índice UV",
        xlabel="Temperatura máxima (°C)",
        ylabel="Índice UV máximo",
    )
    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "dispersion_temperatura_uv.png", dpi=300)
    plt.close(figure)


def generar_resumenes(dataframe):
    """Resume estadísticas históricas excluyendo filas estimadas."""
    real = dataframe.loc[dataframe["data_type"].eq("real")]
    city_summary = real.groupby("city").agg(
        temperatura_media_historica=("metrics.temperature.avg", "mean"),
        lluvia_total=("metrics.precipitation.avg", "sum"),
    ).reset_index()
    annual_summary = real.groupby(["city", "year"]).agg(
        temperatura_maxima_absoluta=("metrics.temperature.max", "max"),
        temperatura_minima_absoluta=("metrics.temperature.min", "min"),
    ).reset_index()
    return city_summary, annual_summary


def descargar_ciudad(city, url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return pd.json_normalize(response.json()).assign(city_name=city)


def guardar_resultados(dataframe, city_summary, annual_summary):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dataframe.to_parquet(DATA_DIR / "df_total.parquet", engine="pyarrow", index=False)
    city_summary.to_parquet(DATA_DIR / "resumen_ciudad.parquet", engine="pyarrow", index=False)
    annual_summary.to_parquet(DATA_DIR / "resumen_anual.parquet", engine="pyarrow", index=False)


def guardar_informe(initial_count, real_count):
    deleted_count = initial_count - real_count
    report = PROJECT_ROOT / "informe_limpieza.txt"
    report.write_text(
        f"Número de registros iniciales: {initial_count}\n"
        f"Número de registros borrados: {deleted_count}\n"
        f"Número de registros finales: {real_count}\n",
        encoding="utf-8",
    )


def main():
    raw_data = pd.concat(
        [descargar_ciudad(city, url) for city, url in CITIES.items()],
        ignore_index=True,
    )
    clean_data, initial_count = limpiar_datos_meteorologicos(raw_data)
    clean_data["city"] = clean_data["city_name"]
    total_data = enriquecer_datos(clean_data)
    real_count = int(total_data["data_type"].eq("real").sum())
    guardar_informe(initial_count, real_count)
    generar_graficas(total_data)
    city_summary, annual_summary = generar_resumenes(total_data)
    guardar_resultados(total_data, city_summary, annual_summary)

    print(f"Registros reales: {real_count}; estimados: {len(total_data) - real_count}.")
    print("Resumen histórico por ciudad:")
    print(city_summary.to_string(index=False))
    print("Resumen anual por ciudad:")
    print(annual_summary.to_string(index=False))
    print(f"Parquet, informe y gráficas guardados bajo {PROJECT_ROOT}.")


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as error:
        raise SystemExit(f"Error al consultar la API meteorológica: {error}") from error
