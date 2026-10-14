# Dashboard del CEER (`pages/monitor/`)

Dashboard económico con gráficos históricos (BCRA, FRED, BLS, Ámbito).
Lo desarrolló el equipo del CEER. Se integró al sitio del CER: desde
`pages/ceer.html` → botón **"Abrir el dashboard"**.

## Archivos

| Archivo | Qué es |
|---|---|
| `index.html` | Estructura de la página (header, filtros, pestañas, footer). |
| `monitor.css` | Estilos. La vista celular es una media query (`max-width: 768px`). |
| `monitor.js` | Lógica: carga el JSON, KPIs, filtros de fecha, gráficos (Chart.js) y Generador. Las tarjetas de gráficos se definen en `CARDS`. |
| `datos_historicos.json` | Series ya procesadas (~400 KB). **Es lo que mantiene al día el bot.** Incluye `meta` con la fecha de actualización y el último dato de cada serie clave. |
| `bot_monetario.py` | Reconstruye el JSON: baja BCRA, BLS, ITCRM, bandas, dólares, riesgo país y Tasa FED. |
| `test_bot_monetario.py` | Tests del post-proceso del bot (no usan red). |
| `requirements.txt` | Dependencias del bot. |
| `ceer-blanco.png`, `ceer_azul*.png` | Logos. |

El dashboard es estático (no necesita backend). Chart.js y html2canvas se cargan
desde jsDelivr / cdnjs con versión fija.

## Mantener los datos al día

### Automático — GitHub Action (recomendado)

`.github/workflows/monitor-datos.yml` corre los tests y después `bot_monetario.py`
cada día a las 08:00 UTC (05:00 AR) y commitea `datos_historicos.json` **solo si hay
datos nuevos**. También se puede lanzar a mano: **Actions → Actualizar datos del
dashboard → Run workflow**.

La corrida **falla** (y GitHub avisa por mail al dueño del repo) si responden menos
de la mitad de las series del BCRA; en ese caso no se toca el JSON. Si una fuente
secundaria cae (dólares, ITCRM, bandas, FED, riesgo país, BLS) el bot usa lo que ya
estaba en el JSON y deja un `::warning::` en el log.

### A mano

```
pip install -r pages/monitor/requirements.txt
python pages/monitor/bot_monetario.py
```

Opciones útiles:

- `--offline`: no descarga nada; solo re-normaliza el JSON existente (sirve para limpiarlo o probar).
- `--hoy AAAA-MM-DD`: fecha de referencia (por defecto, hoy en Argentina).

Tests: `python -m unittest discover -s pages/monitor -p 'test_*.py' -v`

## Cómo trata los datos el bot

- **Sin fechas futuras.** Se descartan meses/días posteriores a hoy (las bandas
  cambiarias vienen proyectadas) y ninguna serie se extrapola más allá de su último dato real.
  Solo los índices de precios (IPC y CPI de EE.UU.) se arrastran para poder deflactar.
- **"Reales"** = deflactados: pesos por el IPC argentino y dólares por el CPI-U de EE.UU.,
  en valores del último mes disponible. Los valores nominales quedan en `*_corriente`.
- **Memoria.** El JSON anterior sirve para completar lo que una fuente no devuelva. Se
  lee en valores nominales para no deflactar dos veces.
- **IPC de EE.UU. (BLS):** se baja de la API pública del BLS (serie `CUUR0000SA0`, sin clave).
  Si además hay un `SeriesReport*.xlsx` en esta carpeta (o en `~/Downloads`), se usa para
  la historia larga. Si el último dato real tiene más de 2 meses, el dashboard lo avisa.
- **TLS:** se verifica en todas las fuentes salvo `bcra.gob.ar` (su cadena de certificados suele venir incompleta).
- Genera temporales `*_temp.xlsx` que borra solo (están en `.gitignore`).
- BCRA / ITCRM / bandas: sin API key.

## Probar el dashboard localmente

No abrir `index.html` con doble clic (el navegador bloquea el `fetch` del JSON). Servirlo por HTTP:

```
cd pages/monitor && python -m http.server 8000
```
y abrir `http://localhost:8000`.
