import requests
import pandas as pd
from pathlib import Path


url_mad = "https://meteometrics.rlopez.org/historical-data/MAD"
url_lon = "https://meteometrics.rlopez.org/historical-data/LON"


def limpiar_datos_meteorologicos(df):
	"""Normaliza las métricas, elimina duplicados y ordena los registros."""
	df = df.copy()
	registros_iniciales = len(df)
	columnas_unidad = ["metrics.temperature.unit", "metrics.precipitation.unit"]
	columnas_metricas = df.filter(regex=r"^metrics\.").columns.difference(columnas_unidad)
	columnas_numericas = df.columns.difference(columnas_unidad)

	# Unifica el separador decimal solo en las métricas meteorológicas.
	df[columnas_metricas] = df[columnas_metricas].replace(",", ".", regex=True)
	# Convierte las columnas a números y transforma los valores no válidos en nulos.
	df[columnas_numericas] = df[columnas_numericas].apply(pd.to_numeric, errors="coerce")
	# Los valores negativos de las métricas representan sentinelas, no medidas válidas.
	df[columnas_metricas] = df[columnas_metricas].where(df[columnas_metricas].ge(0))
	# Al ordenar por nulos de forma estable, se conserva el registro más completo.
	df["_nulos_fila"] = df.isna().sum(axis=1)
	df = df.sort_values("_nulos_fila", kind="stable")
	df = df.drop_duplicates(subset=["year", "month"], keep="first")
	df = df.drop(columns="_nulos_fila")
	# El orden cronológico se aplica después de resolver los duplicados.
	df = df.sort_values(["year", "month"], kind="stable").reset_index(drop=True)

	return df, registros_iniciales


def generar_graficas(df_madrid, df_londres):
	"""Crea y guarda cuatro gráficas comparativas de los datos limpios."""
	import matplotlib.pyplot as plt
	import seaborn as sns

	output_dir = Path("output")
	output_dir.mkdir(parents=True, exist_ok=True)
	meses = [
		"Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
		"Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
	]
	colores_ciudad = {"Madrid": "#c62828", "Londres": "#8e3030"}
	datos = pd.concat(
		[
			df_madrid.assign(ciudad="Madrid"),
			df_londres.assign(ciudad="Londres"),
		],
		ignore_index=True,
	)
	datos_agosto = datos.loc[datos["month"].eq(8)].copy()

	# La primera figura compara la temperatura máxima de agosto en ambas ciudades.
	fig, ax = plt.subplots(figsize=(10, 6))
	sns.lineplot(
		data=datos_agosto,
		x="year",
		y="metrics.temperature.max",
		hue="ciudad",
		style="ciudad",
		markers=True,
		palette=colores_ciudad,
		ax=ax,
	)
	ax.set_title("Temperatura máxima en agosto por año")
	ax.set_xlabel("Año")
	ax.set_ylabel("Temperatura máxima (°C)")
	fig.tight_layout()
	fig.savefig(output_dir / "temperatura_maxima_agosto.png", dpi=300)
	plt.close(fig)

	# Cada panel mantiene la unidad de precipitación propia de su ciudad.
	fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=False)
	for_ax_madrid = axes[0]
	for_ax_londres = axes[1]
	for_ax_madrid_data = datos_agosto.loc[datos_agosto["ciudad"].eq("Madrid")].sort_values("year")
	for_ax_londres_data = datos_agosto.loc[datos_agosto["ciudad"].eq("Londres")].sort_values("year")

	for_ax_madrid.bar(
		range(len(for_ax_madrid_data)),
		for_ax_madrid_data["metrics.precipitation.avg"],
		color="#5b9e78",
		label="Precipitación media",
	)
	for_ax_madrid.set_title("Madrid")
	for_ax_madrid.set_ylabel(
		f"Precipitación media ({for_ax_madrid_data['metrics.precipitation.unit'].iloc[0]})"
	)
	for_ax_madrid.set_xticks(
		range(len(for_ax_madrid_data)), for_ax_madrid_data["year"].astype(str), rotation=45
	)
	for_ax_madrid.set_xlabel("Año")
	for_ax_madrid_temp = for_ax_madrid.twinx()
	for_ax_madrid_temp.plot(
		range(len(for_ax_madrid_data)),
		for_ax_madrid_data["metrics.temperature.avg"],
		color="#c62828",
		marker="o",
		label="Temperatura media",
	)
	for_ax_madrid_temp.set_ylabel("Temperatura media (°C)")

	for_ax_londres.bar(
		range(len(for_ax_londres_data)),
		for_ax_londres_data["metrics.precipitation.avg"],
		color="#5b9e78",
		label="Precipitación media",
	)
	for_ax_londres.set_title("Londres")
	for_ax_londres.set_ylabel(
		f"Precipitación media ({for_ax_londres_data['metrics.precipitation.unit'].iloc[0]})"
	)
	for_ax_londres.set_xticks(
		range(len(for_ax_londres_data)), for_ax_londres_data["year"].astype(str), rotation=45
	)
	for_ax_londres.set_xlabel("Año")
	for_ax_londres_temp = for_ax_londres.twinx()
	for_ax_londres_temp.plot(
		range(len(for_ax_londres_data)),
		for_ax_londres_data["metrics.temperature.avg"],
		color="#c62828",
		marker="o",
		label="Temperatura media",
	)
	for_ax_londres_temp.set_ylabel("Temperatura media (°C)")
	fig.suptitle("Climograma de agosto: precipitación y temperatura media")
	fig.tight_layout()
	fig.savefig(output_dir / "climograma_agosto.png", dpi=300)
	plt.close(fig)

	# Los dos mapas comparten escala para permitir comparar sus temperaturas.
	fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=True)
	temperaturas = datos["metrics.temperature.avg"]
	vmin, vmax = temperaturas.min(), temperaturas.max()
	matriz_madrid = df_madrid.pivot(
		index="month", columns="year", values="metrics.temperature.avg"
	).reindex(range(1, 13))
	matriz_londres = df_londres.pivot(
		index="month", columns="year", values="metrics.temperature.avg"
	).reindex(range(1, 13))
	matriz_madrid.index = meses
	matriz_londres.index = meses
	sns.heatmap(
		matriz_madrid,
		ax=axes[0],
		cmap="coolwarm",
		vmin=vmin,
		vmax=vmax,
		cbar_kws={"label": "Temperatura media (°C)"},
	)
	axes[0].set_title("Madrid")
	axes[0].set_xlabel("Año")
	axes[0].set_ylabel("Mes")
	sns.heatmap(
		matriz_londres,
		ax=axes[1],
		cmap="coolwarm",
		vmin=vmin,
		vmax=vmax,
		cbar_kws={"label": "Temperatura media (°C)"},
	)
	axes[1].set_title("Londres")
	axes[1].set_xlabel("Año")
	axes[1].set_ylabel("Mes")
	fig.suptitle("Temperatura media mensual y evolución a lo largo de los años")
	fig.tight_layout()
	fig.savefig(output_dir / "mapa_calor_temperaturas.png", dpi=300)
	plt.close(fig)

	# Cada punto es un registro mensual de temperatura máxima e índice UV.
	fig, ax = plt.subplots(figsize=(10, 6))
	sns.scatterplot(
		data=datos,
		x="metrics.temperature.max",
		y="metrics.uv_index_max",
		hue="ciudad",
		style="ciudad",
		palette={"Madrid": "#c62828", "Londres": "#2878b5"},
		ax=ax,
	)
	ax.set_title("Temperatura máxima e índice UV por registro mensual")
	ax.set_xlabel("Temperatura máxima (°C)")
	ax.set_ylabel("Índice UV máximo")
	fig.tight_layout()
	fig.savefig(output_dir / "dispersion_temperatura_uv.png", dpi=300)
	plt.close(fig)


try:
	# Descarga y normaliza los datos de ambas ciudades.
	response_madrid = requests.get(url_mad)
	response_madrid.raise_for_status()
	df_madrid, iniciales_madrid = limpiar_datos_meteorologicos(
		pd.json_normalize(response_madrid.json())
	)

	response_londres = requests.get(url_lon)
	response_londres.raise_for_status()
	df_londres, iniciales_londres = limpiar_datos_meteorologicos(
		pd.json_normalize(response_londres.json())
	)

	# Resume en un único informe los registros procesados en las dos ciudades.
	registros_iniciales = iniciales_madrid + iniciales_londres
	registros_finales = len(df_madrid) + len(df_londres)
	registros_borrados = registros_iniciales - registros_finales
	with open("informe_limpieza.txt", "w", encoding="utf-8") as informe:
		informe.write(f"Número de registros iniciales: {registros_iniciales}\n")
		informe.write(f"Número de registros borrados: {registros_borrados}\n")
		informe.write(f"Número de registros finales: {registros_finales}\n")

	generar_graficas(df_madrid, df_londres)
	print("Datos meteorológicos de Madrid:")
	print(df_madrid)
	print("\nDatos meteorológicos de Londres:")
	print(df_londres)
	print("\nInforme generado: informe_limpieza.txt")
	print("Las cuatro gráficas se crearon correctamente en la carpeta 'output'.")
except requests.exceptions.RequestException as e:
	print(f"Error en la petición: {e}")
except Exception as e:
	print(f"Error al procesar los datos o crear las gráficas: {e}")