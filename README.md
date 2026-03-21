# Análisis del Oro — GC=F Dashboard

Dashboard web en Python/Flask para el análisis técnico del precio del oro al contado (ticker `GC=F`) usando datos en tiempo real de Yahoo Finance.

---

## Características

- **Precio en tiempo real** con variación diaria (valor y porcentaje).
- **Señal final** COMPRAR / MANTENER / VENDER calculada mediante sistema de scoring multi-indicador.
- **Métricas de contexto**: máximo y mínimo de los últimos 30 días, volatilidad de 14 días.
- **Gráfico interactivo** de los últimos 90 días con SMA20 y SMA50 superpuestas (Chart.js).
- **Cards de indicadores**: RSI(14), MACD(12,26,9), Bandas de Bollinger(20,2σ) y Cruce SMA.
- **Modo oscuro** persistente (localStorage).
- **Modal de ayuda** con descripción de cada indicador.
- Actualización de datos sin recarga de página (fetch a `/api/data`).

---

## Estructura del proyecto

```
midas/
├── app.py               # Backend Flask + lógica de indicadores y scoring
├── requirements.txt     # Dependencias Python
├── .gitignore
├── README.md
└── templates/
    └── index.html       # Frontend: dashboard, gráfico, dark mode, modal ayuda
```

---

## Requisitos

- Python 3.10 o superior
- Conexión a Internet (descarga datos de Yahoo Finance)

---

## Instalación y ejecución

```bash
# 1. Clonar el repositorio
git clone <url-repo>
cd midas

# 2. Crear entorno virtual (recomendado)
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Iniciar la aplicación
python app.py
```

Abre el navegador en **http://127.0.0.1:5000**

---

## Endpoints

| Método | Ruta        | Descripción                              |
|--------|-------------|------------------------------------------|
| `GET`  | `/`         | Sirve el dashboard HTML                  |
| `GET`  | `/api/data` | Devuelve JSON con precios e indicadores  |

### Ejemplo de respuesta `/api/data`

```json
{
  "current_price": 3025.40,
  "day_change": 12.30,
  "day_change_pct": 0.41,
  "metrics": {
    "high_30d": 3089.10,
    "low_30d": 2890.50,
    "volatility_14d": 0.7821
  },
  "chart": {
    "dates": ["2024-12-01", "..."],
    "prices": [2640.10, "..."],
    "sma20": [2635.00, "..."],
    "sma50": [2610.00, "..."]
  },
  "score": 2,
  "final_signal": "COMPRAR",
  "indicators": { "rsi": {}, "macd": {}, "bollinger": {}, "sma": {} },
  "updated_at": "2025-03-21 19:00:00"
}
```

---

## Indicadores técnicos

### RSI — Índice de Fuerza Relativa (14 períodos)

Mide la velocidad y magnitud de los movimientos de precio en una escala de 0 a 100. Identifica zonas de sobrecompra y sobreventa.

- **RSI < 35** → zona de sobreventa → señal **COMPRAR** (+1)
- **RSI > 65** → zona de sobrecompra → señal **VENDER** (−1)
- **35 ≤ RSI ≤ 65** → zona neutral → señal **MANTENER** (0)

> Umbral ajustado a 35/65 (en lugar del clásico 30/70) para mayor sensibilidad en commodities.

---

### MACD — Convergencia/Divergencia de Medias Móviles (12, 26, 9)

Calcula la diferencia entre la EMA de 12 y la EMA de 26 períodos. La línea de señal es una EMA de 9 períodos sobre el MACD.

- **Línea MACD > Línea de señal** → momentum alcista → señal **COMPRAR** (+1)
- **Línea MACD < Línea de señal** → momentum bajista → señal **VENDER** (−1)

> Un cruce alcista (golden cross del MACD) sugiere que la tendencia de corto plazo supera a la de medio plazo.

---

### Bandas de Bollinger (20 períodos, 2 desviaciones estándar)

Tres bandas que envuelven el precio: media móvil simple de 20 (banda media) ± 2 desviaciones estándar. El 95 % del precio suele quedar dentro de las bandas en condiciones normales.

- **Precio < Banda inferior** → precio estadísticamente bajo → señal **COMPRAR** (+1)
- **Precio > Banda superior** → precio estadísticamente alto → señal **VENDER** (−1)
- **Precio dentro de bandas** → sin señal extrema → señal **MANTENER** (0)

---

### Cruce de Medias Móviles Simples — SMA20 / SMA50

Compara dos medias móviles de distintos períodos para identificar la dirección de la tendencia de medio plazo.

- **SMA20 > SMA50** → tendencia alcista de medio plazo → señal **COMPRAR** (+1)
- **SMA20 < SMA50** → tendencia bajista de medio plazo → señal **VENDER** (−1)

> Cuando la SMA rápida (20) supera a la lenta (50) se denomina *golden cross*; la situación inversa es *death cross*.

---

## Lógica de scoring

Cada indicador aporta una puntuación parcial que se suma para obtener el score total (rango: −4 a +4):

| Score total | Señal final |
|-------------|-------------|
| ≥ +2        | **COMPRAR** |
| ≤ −2        | **VENDER**  |
| −1, 0, +1   | **MANTENER**|

---

## Dependencias principales

| Librería      | Versión mín. | Uso                                  |
|---------------|--------------|--------------------------------------|
| `flask`       | 3.0.0        | Servidor web y API REST              |
| `yfinance`    | 0.2.40       | Descarga de datos históricos OHLCV   |
| `pandas`      | 2.0.0        | Manipulación de series temporales    |
| `pandas-ta`   | 0.3.14b      | Cálculo de indicadores técnicos      |
| `numpy`       | 1.26.0       | Operaciones numéricas auxiliares     |
| `chart.js`    | 4.4.3 (CDN)  | Gráfico interactivo en el frontend   |

---

## Notas

- Los datos se obtienen en **tiempo diferido** (15–20 min) desde Yahoo Finance. No es un feed de tiempo real.
- El servidor de desarrollo de Flask **no debe usarse en producción**. Para despliegues usar Gunicorn o uWSGI.
- Los indicadores requieren un mínimo de ~50 sesiones históricas para estabilizarse (especialmente SMA50).

---

## Licencia

MIT
