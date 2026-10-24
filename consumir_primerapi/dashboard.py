import plotly.express as px
import requests
import streamlit as st

from app import API_URL, obtener_clientes, procesar_clientes


st.set_page_config(page_title="Análisis de clientes", layout="wide")
st.title("Análisis de clientes")
st.caption(f"Fuente de datos: {API_URL}")


@st.cache_data(ttl=300)
def cargar_datos():
    return procesar_clientes(obtener_clientes())


try:
    clientes = cargar_datos()
except (requests.exceptions.RequestException, ValueError) as error:
    st.error(f"No se pudieron cargar los datos de la API: {error}")
    st.stop()

st.subheader("Ratio de endeudamiento por cliente")
endeudamiento = clientes.sort_values("ratio_endeudamiento", ascending=True)
grafico_endeudamiento = px.bar(
    endeudamiento,
    x="ratio_endeudamiento",
    y="nombre_completo",
    orientation="h",
    color="ratio_endeudamiento",
    color_continuous_scale=["green", "yellow", "red"],
    labels={
        "ratio_endeudamiento": "Ratio de endeudamiento",
        "nombre_completo": "Cliente",
    },
    hover_data={
        "ratio_endeudamiento": ":.6f",
        "ingresos_anuales": ":,.0f",
        "prestamos_vigentes": True,
    },
)
grafico_endeudamiento.update_layout(coloraxis_colorbar_title="Ratio")
st.plotly_chart(grafico_endeudamiento, width="stretch")

st.subheader("Ingresos anuales e índice de salud crediticia")
grafico_salud = px.scatter(
    clientes,
    x="ingresos_anuales",
    y="indice_salud_crediticia",
    color="tipo_cliente",
    hover_name="nombre_completo",
    hover_data={
        "indice_salud_crediticia": ":.1f",
        "ingresos_anuales": ":,.0f",
    },
    labels={
        "ingresos_anuales": "Ingresos anuales",
        "indice_salud_crediticia": "Índice de salud crediticia (0-100)",
        "tipo_cliente": "Tipo de cliente",
    },
    color_discrete_map={"Particular": "#2563eb", "Empresa": "#f97316"},
)
st.plotly_chart(grafico_salud, width="stretch")
