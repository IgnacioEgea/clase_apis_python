# Consumir y analizar la API de clientes

Este ejemplo consulta `/clientes`, aplana el JSON anidado con
`pandas.json_normalize`, calcula variables derivadas y muestra dos gráficos
interactivos. Los datos del API del ejercicio son sintéticos y solo sirven para
pruebas y aprendizaje.

## Ejecutar localmente

Instala las dependencias desde la raíz del repositorio:

```bash
python -m pip install -r consumir_primerapi/requirements.txt
```

En una terminal inicia la API de clientes:

```bash
python ejercicios_api/06_filtros/app.py
```

En otra terminal, procesa los datos:

```bash
python consumir_primerapi/app.py
```

Inicia el dashboard con:

```bash
streamlit run consumir_primerapi/dashboard.py
```

Por omisión, el cliente consulta `http://127.0.0.1:5000/clientes`. Para consumir
el servicio desplegado, define `API_URL` con la URL pública del endpoint:

```bash
API_URL=https://tu-servicio.onrender.com/clientes \
  python consumir_primerapi/app.py
```

En Windows PowerShell, usa `$env:API_URL = "https://tu-servicio.onrender.com/clientes"`
antes de ejecutar los comandos.

El ratio de endeudamiento es el número de préstamos vigentes dividido por los
ingresos anuales. El índice de salud crediticia transforma el score de 0–1000 a
un porcentaje de 0–100. Los gráficos muestran los datos individuales devueltos
por la API; el dashboard conserva la respuesta en caché durante cinco minutos.
