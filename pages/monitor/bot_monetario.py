import argparse
import glob
import json
import math
import os
import re
import sys
import warnings

import pandas as pd
import requests

# Solo silenciamos el aviso de TLS de los hosts del BCRA (ver http_get); el resto de los warnings se ven.
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VARS_MENSUAL = {
    110: 'adelantos', 111: 'documentos', 112: 'hipotecarios', 113: 'prendarios', 114: 'personales', 115: 'tarjetas',
    85: 'cc', 86: 'ca', 24: 'plazo_fijo', 108: 'depositos_usd', 125: 'prestamos_usd',
    1: 'reservas', 78: 'compra_divisas', 5: 'tc_mayorista', 4: 'tc_minorista',
    27: 'ipc_mensual', 28: 'ipc_interanual', 29: 'rem_interanual',
    15: 'base_monetaria', 109: 'm2', 197: 'm2_transaccional', 16: 'circulacion_monetaria', 17: 'billetes_monedas',
    152: 'pases_pasivos', 196: 'lefi',
    161: 'tasa_politica_tea', 35: 'badlar_tea', 45: 'tamar_tea', 11: 'baibar_tea', 8: 'tm20_tea'
}
VARS_DIARIO = {35: 'badlar_tea', 45: 'tamar_tea'}

# La cadena de certificados de bcra.gob.ar suele venir incompleta; ahí (y solo ahí) no se verifica TLS.
HOSTS_SIN_VERIFICAR = ('bcra.gob.ar',)
SERIE_CPI_BLS = 'CUUR0000SA0'  # CPI-U, todos los rubros, sin desestacionalizar

def http_get(url, **kwargs):
    kwargs.setdefault('verify', not any(h in url for h in HOSTS_SIN_VERIFICAR))
    kwargs.setdefault('timeout', 30)
    return requests.get(url, **kwargs)

HEADERS_BOT = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7'
}

def fetch_itcrm_excel():
    print("Descargando ITCRM y Bilaterales (Scrapeando Excel BCRA)...")
    temp_path = os.path.join(BASE_DIR, 'itcrm_temp.xlsx')
    try:
        r = http_get("https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/ITCRMSerie.xlsx", headers=HEADERS_BOT, timeout=30)
        if r.status_code == 200:
            with open(temp_path, 'wb') as f: f.write(r.content)
            df = pd.read_excel(temp_path, sheet_name=0, skiprows=1)
            col_map = {}
            for c in df.columns:
                c_str = str(c).strip().lower()
                if 'fecha' in c_str or 'período' in c_str or 'periodo' in c_str: col_map[c] = 'fecha'
                elif c_str == 'itcrm': col_map[c] = 'itcrm'
                elif 'brasil' in c_str: col_map[c] = 'tcr_brasil'
                elif 'canadá' in c_str or 'canada' in c_str: col_map[c] = 'tcr_canada'
                elif 'chile' in c_str: col_map[c] = 'tcr_chile'
                elif 'estados unidos' in c_str or 'usa' in c_str: col_map[c] = 'tcr_usa'
                elif 'méxico' in c_str or 'mexico' in c_str: col_map[c] = 'tcr_mexico'
                elif 'uruguay' in c_str: col_map[c] = 'tcr_uruguay'
                elif 'china' in c_str: col_map[c] = 'tcr_china'
                elif 'india' in c_str: col_map[c] = 'tcr_india'
                elif 'japón' in c_str or 'japon' in c_str: col_map[c] = 'tcr_japon'
                elif 'reino unido' in c_str: col_map[c] = 'tcr_reino_unido'
                elif 'suiza' in c_str: col_map[c] = 'tcr_suiza'
                elif 'zona euro' in c_str: col_map[c] = 'tcr_zona_euro'
                elif 'vietnam' in c_str: col_map[c] = 'tcr_vietnam'
            df = df.rename(columns=col_map)
            cols_to_keep = list(col_map.values())
            df = df[cols_to_keep].dropna(subset=['fecha'])
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
            for c in cols_to_keep:
                if c != 'fecha': df[c] = pd.to_numeric(df[c], errors='coerce')
            if os.path.exists(temp_path): os.remove(temp_path)
            return df
    except Exception as e: print(f"  -> Error Excel ITCRM: {e}")
    return pd.DataFrame(columns=['fecha'])

def fetch_dolares_history():
    print("Descargando Dólares Históricos (MEP, Blue y CCL)...")
    df_d = pd.DataFrame(columns=['fecha'])
    
    # MEP
    try:
        r = http_get("https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa", headers=HEADERS_BOT, timeout=20)
        if r.status_code == 200:
            df_mep = pd.DataFrame(r.json())
            df_mep['fecha'] = pd.to_datetime(df_mep['fecha'])
            df_d = pd.merge(df_d, df_mep[['fecha', 'venta']].rename(columns={'venta': 'dolar_mep'}), on='fecha', how='outer')
    except Exception as e:
        print(f"  -> argentinadatos falló ({e}); probando Ámbito...")
        try:
            now = pd.Timestamp.now().strftime('%Y-%m-%d')
            r = http_get(f"https://mercados.ambito.com//dolar/mep/historico-general/2004-01-01/{now}", headers=HEADERS_BOT)
            data = r.json()
            if len(data) > 1:
                df_mep = pd.DataFrame(data[1:], columns=data[0])
                df_mep['fecha'] = pd.to_datetime(df_mep['Fecha'], format='%d-%m-%Y', errors='coerce')
                df_mep['dolar_mep'] = df_mep['Venta'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_mep['dolar_mep'] = pd.to_numeric(df_mep['dolar_mep'], errors='coerce')
                df_d = pd.merge(df_d, df_mep[['fecha', 'dolar_mep']].dropna(), on='fecha', how='outer')
        except Exception as e: print(f"  -> Error en fallback Ámbito: {e}")

    # BLUE
    try:
        r = http_get("https://api.argentinadatos.com/v1/cotizaciones/dolares/blue", headers=HEADERS_BOT, timeout=20)
        if r.status_code == 200:
            df_blue = pd.DataFrame(r.json())
            df_blue['fecha'] = pd.to_datetime(df_blue['fecha'])
            if df_d.empty:
                df_d = df_blue[['fecha', 'venta']].rename(columns={'venta': 'dolar_blue'})
            else:
                df_d = pd.merge(df_d, df_blue[['fecha', 'venta']].rename(columns={'venta': 'dolar_blue'}), on='fecha', how='outer')
    except Exception as e:
        print(f"  -> argentinadatos falló ({e}); probando Ámbito...")
        try:
            now = pd.Timestamp.now().strftime('%Y-%m-%d')
            r = http_get(f"https://mercados.ambito.com//dolar/informal/historico-general/2004-01-01/{now}", headers=HEADERS_BOT)
            data = r.json()
            if len(data) > 1:
                df_b = pd.DataFrame(data[1:], columns=data[0])
                df_b['fecha'] = pd.to_datetime(df_b['Fecha'], format='%d-%m-%Y', errors='coerce')
                df_b['dolar_blue'] = df_b['Venta'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_b['dolar_blue'] = pd.to_numeric(df_b['dolar_blue'], errors='coerce')
                if df_d.empty:
                    df_d = df_b[['fecha', 'dolar_blue']].dropna()
                else:
                    df_d = pd.merge(df_d, df_b[['fecha', 'dolar_blue']].dropna(), on='fecha', how='outer')
        except Exception as e: print(f"  -> Error en fallback Ámbito: {e}")

    # CCL
    try:
        r = http_get("https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui", headers=HEADERS_BOT, timeout=20)
        if r.status_code == 200:
            df_ccl = pd.DataFrame(r.json())
            df_ccl['fecha'] = pd.to_datetime(df_ccl['fecha'])
            if df_d.empty:
                df_d = df_ccl[['fecha', 'venta']].rename(columns={'venta': 'dolar_ccl'})
            else:
                df_d = pd.merge(df_d, df_ccl[['fecha', 'venta']].rename(columns={'venta': 'dolar_ccl'}), on='fecha', how='outer')
    except Exception as e:
        print(f"  -> argentinadatos falló ({e}); probando Ámbito...")
        try:
            now = pd.Timestamp.now().strftime('%Y-%m-%d')
            r = http_get(f"https://mercados.ambito.com//dolar/contado-con-liqui/historico-general/2004-01-01/{now}", headers=HEADERS_BOT)
            data = r.json()
            if len(data) > 1:
                df_c = pd.DataFrame(data[1:], columns=data[0])
                df_c['fecha'] = pd.to_datetime(df_c['Fecha'], format='%d-%m-%Y', errors='coerce')
                df_c['dolar_ccl'] = df_c['Venta'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_c['dolar_ccl'] = pd.to_numeric(df_c['dolar_ccl'], errors='coerce')
                if df_d.empty:
                    df_d = df_c[['fecha', 'dolar_ccl']].dropna()
                else:
                    df_d = pd.merge(df_d, df_c[['fecha', 'dolar_ccl']].dropna(), on='fecha', how='outer')
        except Exception as e: print(f"  -> Error en fallback Ámbito: {e}")

    return df_d

def fetch_riesgo_pais():
    print("Descargando Riesgo País...")
    try:
        r = http_get("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais", headers=HEADERS_BOT, timeout=20)
        if r.status_code == 200:
            df_rp = pd.DataFrame(r.json())
            df_rp['fecha'] = pd.to_datetime(df_rp['fecha'])
            df_rp = df_rp.rename(columns={'valor': 'riesgo_pais'})
            return df_rp[['fecha', 'riesgo_pais']].sort_values('fecha')
    except Exception as e:
        print(f"  -> Riesgo país: argentinadatos falló ({e}); probando Ámbito...")

    try:
        now = pd.Timestamp.now().strftime('%Y-%m-%d')
        url = f"https://mercados.ambito.com//riesgopais/historico-general/2004-01-01/{now}"
        r = http_get(url, headers=HEADERS_BOT, timeout=20)
        if r.status_code == 200:
            data = r.json()
            if len(data) > 1:
                df_rp = pd.DataFrame(data[1:], columns=data[0])
                df_rp['fecha'] = pd.to_datetime(df_rp['Fecha'], format='%d-%m-%Y', errors='coerce')
                df_rp['riesgo_pais'] = df_rp['Valor'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df_rp['riesgo_pais'] = pd.to_numeric(df_rp['riesgo_pais'], errors='coerce')
                return df_rp[['fecha', 'riesgo_pais']].dropna().sort_values('fecha')
    except Exception as e: print(f"  -> Error Riesgo país (Ámbito): {e}")
        
    return pd.DataFrame(columns=['fecha', 'riesgo_pais'])

def fetch_us_cpi_api():
    """Últimos 10 años del CPI-U desde la API pública del BLS (v1, no pide clave)."""
    anio = pd.Timestamp.now().year
    url = f"https://api.bls.gov/publicAPI/v1/timeseries/data/{SERIE_CPI_BLS}?startyear={anio - 9}&endyear={anio}"
    try:
        r = http_get(url, headers=HEADERS_BOT)
        r.raise_for_status()
        j = r.json()
        if j.get('status') != 'REQUEST_SUCCEEDED':
            raise ValueError(f"BLS respondió {j.get('status')}: {j.get('message')}")
        filas = [(pd.Timestamp(int(d['year']), int(d['period'][1:]), 1), d['value'])
                 for d in j['Results']['series'][0]['data'] if re.fullmatch(r'M(0[1-9]|1[0-2])', d['period'])]
        df = pd.DataFrame(filas, columns=['fecha', 'us_cpi'])
        df['us_cpi'] = pd.to_numeric(df['us_cpi'], errors='coerce')
        df = df.dropna().sort_values('fecha')
        if not df.empty:
            print(f"  -> BLS API: {len(df)} meses, último dato {df['fecha'].max().strftime('%Y-%m')}")
        return df
    except Exception as e:
        print(f"  -> Error API del BLS: {e}")
        return pd.DataFrame(columns=['fecha', 'us_cpi'])

def fetch_us_cpi(df_memoria):
    print("Procesando CPI de EEUU (Inflación en Dólares desde BLS)...")
    df_cpi = pd.DataFrame(columns=['fecha', 'us_cpi'])

    # 1) Memoria: lo que ya tenía el JSON anterior
    if not df_memoria.empty and 'us_cpi' in df_memoria.columns:
        df_cpi = df_memoria[['us_cpi']].dropna().reset_index()
        df_cpi['fecha'] = pd.to_datetime(df_cpi['fecha'], errors='coerce')

    # 2) API del BLS: se actualiza sola, sin bajar ningún Excel a mano
    df_api = fetch_us_cpi_api()
    if not df_api.empty:
        df_cpi = pd.concat([df_cpi, df_api]) if not df_cpi.empty else df_api
        df_cpi = df_cpi.drop_duplicates(subset=['fecha'], keep='last')

    # 3) Excel manual (SeriesReport*.xlsx): trae la historia larga; si está, tiene prioridad
    cpi_path = None
    try:
        archivos_bls = glob.glob(os.path.join(os.path.expanduser('~'), 'Downloads', 'SeriesReport*.xlsx'))
        archivos_bls += glob.glob(os.path.join(BASE_DIR, 'SeriesReport*.xlsx'))
        if archivos_bls:
            cpi_path = max(archivos_bls, key=os.path.getmtime)
            print(f"  -> Archivo BLS encontrado: {cpi_path}")
    except Exception as e:
        print(f"  -> No se pudo buscar el Excel del BLS: {e}")

    if cpi_path and os.path.exists(cpi_path):
        try:
            df_hist = pd.read_excel(cpi_path, skiprows=11)
            if 'Year' in df_hist.columns and 'Jan' in df_hist.columns:
                meses = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                df_hist = df_hist.melt(id_vars=['Year'], value_vars=[m for m in meses if m in df_hist.columns], var_name='Month', value_name='us_cpi')
                df_hist = df_hist.dropna(subset=['us_cpi'])
                df_hist['fecha'] = pd.to_datetime(df_hist['Year'].astype(str) + '-' + df_hist['Month'], format='%Y-%b')
                df_cpi = df_hist[['fecha', 'us_cpi']] if df_cpi.empty else pd.concat([df_cpi, df_hist[['fecha', 'us_cpi']]]).drop_duplicates(subset=['fecha'], keep='last')
                print(f"  -> Datos del Excel BLS integrados. Último dato: {df_cpi['fecha'].max().strftime('%Y-%m')}")
        except Exception as e:
            print(f"  -> Error procesando el archivo del BLS: {e}")

    return df_cpi.sort_values('fecha')

def fetch_tasa_fed():
    print("Descargando Tasa de la FED (EFFR)...")
    now = pd.Timestamp.now()
    start_date = "2000-01-01" 
    end_date = now.strftime('%Y-%m-%d')
    url = f"https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json?startDate={start_date}&endDate={end_date}"
    
    try:
        r = http_get(url, headers=HEADERS_BOT, timeout=20)
        
        if r.status_code == 200:
            data = r.json().get('refRates', [])
            if data:
                df = pd.DataFrame(data)
                df = df[['effectiveDate', 'percentRate']].rename(columns={
                    'effectiveDate': 'fecha', 
                    'percentRate': 'tasa_fed'
                })
                
                df['fecha'] = pd.to_datetime(df['fecha'])
                df['tasa_fed'] = pd.to_numeric(df['tasa_fed'], errors='coerce')
                
                df['periodo'] = df['fecha'].dt.to_period('M')
                df_mensual = df.groupby('periodo').last().reset_index()
                df_mensual['fecha'] = df_mensual['periodo'].dt.strftime('%Y-%m')
                return df_mensual[['fecha', 'tasa_fed']]
    except Exception as e: print(f"  -> Error Tasa FED: {e}")
        
    return pd.DataFrame(columns=['fecha', 'tasa_fed'])

def fetch_bandas_cambiarias():
    import re
    print("Procesando Bandas Cambiarias del BCRA (Hardcode 2025 + Scraping 2026)...")
    df_final = pd.DataFrame(columns=['fecha', 'banda_inferior', 'banda_superior'])
    
    # --- 1. HARDCODE 2025 AUTOMATIZADO ---
    str_sup = "14/04/20251.400,0015/04/20251.400,4616/04/20251.400,9321/04/20251.403,2522/04/20251.403,7223/04/20251.404,1924/04/20251.404,6525/04/20251.405,1228/04/20251.406,5229/04/20251.406,9830/04/20251.407,4505/05/20251.409,7906/05/20251.410,2507/05/20251.410,7208/05/20251.411,1909/05/20251.411,6612/05/20251.413,0613/05/20251.413,5314/05/20251.414,0015/05/20251.414,4716/05/20251.414,9419/05/20251.416,3520/05/20251.416,8221/05/20251.417,2922/05/20251.417,7623/05/20251.418,2326/05/20251.419,6427/05/20251.420,1128/05/20251.420,5829/05/20251.421,0530/05/20251.421,5202/06/20251.422,9403/06/20251.423,4104/06/20251.423,8805/06/20251.424,3606/06/20251.424,8309/06/20251.426,2510/06/20251.426,7211/06/20251.427,1912/06/20251.427,6713/06/20251.428,1417/06/20251.430,0418/06/20251.430,5119/06/20251.430,9823/06/20251.432,8824/06/20251.433,3625/06/20251.433,8426/06/20251.434,3127/06/20251.434,7930/06/20251.436,2201/07/20251.436,6902/07/20251.437,1703/07/20251.437,6504/07/20251.438,1207/07/20251.439,5508/07/20251.440,0310/07/20251.440,9911/07/20251.441,4614/07/20251.442,9015/07/20251.443,3816/07/20251.443,8617/07/20251.444,3418/07/20251.444,8221/07/20251.446,2522/07/20251.446,7323/07/20251.447,2124/07/20251.447,6925/07/20251.448,1728/07/20251.449,6229/07/20251.450,1030/07/20251.450,5831/07/20251.451,0601/08/20251.451,5404/08/20251.452,9905/08/20251.453,4706/08/20251.453,9507/08/20251.454,4308/08/20251.454,9111/08/20251.456,3612/08/20251.456,8513/08/20251.457,3314/08/20251.457,8118/08/20251.459,7519/08/20251.460,2320/08/20251.460,7221/08/20251.461,2022/08/20251.461,6925/08/20251.463,1426/08/20251.463,6327/08/20251.464,1128/08/20251.464,6029/08/20251.465,0801/09/20251.466,5402/09/20251.467,0303/09/20251.467,5104/09/20251.468,0005/09/20251.468,4908/09/20251.469,9509/09/20251.470,4410/09/20251.470,9311/09/20251.471,4112/09/20251.471,9015/09/20251.473,3716/09/20251.473,8617/09/20251.474,3518/09/20251.474,8319/09/20251.475,3222/09/20251.476,7923/09/20251.477,2824/09/20251.477,7725/09/20251.478,2626/09/20251.478,7529/09/20251.480,2230/09/20251.480,7201/10/20251.481,2102/10/20251.481,7003/10/20251.482,1906/10/20251.483,6707/10/20251.484,1608/10/20251.484,6509/10/20251.485,1413/10/20251.487,1114/10/20251.487,6115/10/20251.488,1016/10/20251.488,5917/10/20251.489,0920/10/20251.490,5721/10/20251.491,0722/10/20251.491,5623/10/20251.492,0524/10/20251.492,5527/10/20251.494,0428/10/20251.494,5329/10/20251.495,0330/10/20251.495,5231/10/20251.496,0203/11/20251.497,5104/11/20251.498,0105/11/20251.498,5007/11/20251.499,5010/11/20251.500,9911/11/20251.501,4912/11/20251.501,9913/11/20251.502,4814/11/20251.502,9817/11/20251.504,4818/11/20251.504,9819/11/20251.505,4820/11/20251.505,9825/11/20251.508,4826/11/20251.508,9827/11/20251.509,4828/11/20251.509,9801/12/20251.511,4802/12/20251.511,9803/12/20251.512,4804/12/20251.512,9905/12/20251.513,4909/12/20251.515,5010/12/20251.516,0011/12/20251.516,5012/12/20251.517,0115/12/20251.518,5216/12/20251.519,0217/12/20251.519,5218/12/20251.520,0319/12/20251.520,5322/12/20251.522,0523/12/20251.522,5526/12/20251.524,0729/12/20251.525,5830/12/20251.526,09"
    str_inf = "14/04/20251.000,0015/04/2025999,6716/04/2025999,3321/04/2025997,6622/04/2025997,3223/04/2025996,9924/04/2025996,6625/04/2025996,3228/04/2025995,3229/04/2025994,9930/04/2025994,6505/05/2025992,9906/05/2025992,6607/05/2025992,3208/05/2025991,9909/05/2025991,6612/05/2025990,6613/05/2025990,3314/05/2025990,0015/05/2025989,6716/05/2025989,3419/05/2025988,3420/05/2025988,0121/05/2025987,6822/05/2025987,3523/05/2025987,0226/05/2025986,0327/05/2025985,7028/05/2025985,3729/05/2025985,0430/05/2025984,7102/06/2025983,7203/06/2025983,3904/06/2025983,0605/06/2025982,7306/06/2025982,4009/06/2025981,4110/06/2025981,0911/06/2025980,7612/06/2025980,4313/06/2025980,1017/06/2025978,7918/06/2025978,4619/06/2025978,1323/06/2025976,8224/06/2025976,4925/06/2025976,1726/06/2025975,8427/06/2025975,5130/06/2025974,5301/07/2025974,2102/07/2025973,8803/07/2025973,5604/07/2025973,2307/07/2025972,2508/07/2025971,9310/07/2025971,2711/07/2025970,9514/07/2025969,9715/07/2025969,6516/07/2025969,3217/07/2025969,0018/07/2025968,6821/07/2025967,7022/07/2025967,3823/07/2025967,0524/07/2025966,7325/07/2025966,4128/07/2025965,4429/07/2025965,1130/07/2025964,7931/07/2025964,4701/08/2025964,1404/08/2025963,1705/08/2025962,8506/08/2025962,5307/08/2025962,2108/08/2025961,8811/08/2025960,9212/08/2025960,6013/08/2025960,2714/08/2025959,9518/08/2025958,6719/08/2025958,3520/08/2025958,0221/08/2025957,7022/08/2025957,3825/08/2025956,4226/08/2025956,1027/08/2025955,7828/08/2025955,4629/08/2025955,1401/09/2025954,1802/09/2025953,8603/09/2025953,5404/09/2025953,2205/09/2025952,9008/09/2025951,9509/09/2025951,6310/09/2025951,3111/09/2025950,9912/09/2025950,6715/09/2025949,7216/09/2025949,4017/09/2025949,0818/09/2025948,7619/09/2025948,4422/09/2025947,4923/09/2025947,1724/09/2025946,8625/09/2025946,5426/09/2025946,2229/09/2025945,2730/09/2025944,9601/10/2025944,6402/10/2025944,3203/10/2025944,0106/10/2025943,0607/10/2025942,7408/10/2025942,4309/10/2025942,1113/10/2025940,8514/10/2025940,5315/10/2025940,2216/10/2025939,9017/10/2025939,5920/10/2025938,6521/10/2025938,3322/10/2025938,0223/10/2025937,7024/10/2025937,3927/10/2025936,4528/10/2025936,1329/10/2025935,8230/10/2025935,5131/10/2025935,1903/11/2025934,2504/11/2025933,9405/11/2025933,6307/11/2025933,0010/11/2025932,0711/11/2025931,7512/11/2025931,4413/11/2025931,1314/11/2025930,8217/11/2025929,8818/11/2025929,5719/11/2025929,2620/11/2025928,9525/11/2025927,3926/11/2025927,0827/11/2025926,7728/11/2025926,4601/12/2025925,5302/12/2025925,2203/12/2025924,9104/12/2025924,6005/12/2025924,2909/12/2025923,0510/12/2025922,7411/12/2025922,4412/12/2025922,1315/12/2025921,2016/12/2025920,8917/12/2025920,5818/12/2025920,2719/12/2025919,9722/12/2025919,0423/12/2025918,7326/12/2025917,8129/12/2025916,8930/12/2025916,58"
    
    matches_sup = re.findall(r'(\d{2}/\d{2}/\d{4})([\d\.,]+)', str_sup)
    matches_inf = re.findall(r'(\d{2}/\d{2}/\d{4})([\d\.,]+)', str_inf)
    
    dict_sup = {pd.to_datetime(d, format='%d/%m/%Y').strftime('%Y-%m-%d'): float(v.replace('.', '').replace(',', '.')) for d, v in matches_sup}
    dict_inf = {pd.to_datetime(d, format='%d/%m/%Y').strftime('%Y-%m-%d'): float(v.replace('.', '').replace(',', '.')) for d, v in matches_inf}
    
    all_dates = set(dict_sup.keys()).union(set(dict_inf.keys()))
    rows_2025 = [{'fecha': d, 'banda_inferior': dict_inf.get(d), 'banda_superior': dict_sup.get(d)} for d in all_dates]
    df_final = pd.concat([df_final, pd.DataFrame(rows_2025)])
    
    # --- 2. SCRAPING 2026 EN ADELANTE ---
    try:
        url_excel = "https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/serie-completa-bandas-cambiarias.xlsx"
        r = http_get(url_excel, headers=HEADERS_BOT, timeout=30)
        temp_bandas = os.path.join(BASE_DIR, 'bandas_temp.xlsx')
        if r.status_code == 200:
            with open(temp_bandas, 'wb') as f: f.write(r.content)
            df_actual = pd.read_excel(temp_bandas, skiprows=6)
            
            col_map = {}
            for c in df_actual.columns:
                c_str = str(c).strip().lower()
                if 'fecha' in c_str: col_map[c] = 'fecha'
                elif 'inferior' in c_str: col_map[c] = 'banda_inferior'
                elif 'superior' in c_str: col_map[c] = 'banda_superior'
            
            df_actual = df_actual.rename(columns=col_map)
            if all(col in df_actual.columns for col in ['fecha', 'banda_inferior', 'banda_superior']):
                df_actual = df_actual[['fecha', 'banda_inferior', 'banda_superior']].dropna(subset=['fecha'])
                df_actual['fecha'] = pd.to_datetime(df_actual['fecha'], errors='coerce')
                for col in ['banda_inferior', 'banda_superior']:
                    df_actual[col] = pd.to_numeric(df_actual[col], errors='coerce')
                
                df_final = pd.concat([df_final, df_actual])
                
            if os.path.exists(temp_bandas): os.remove(temp_bandas)
    except Exception as e:
        print(f"  -> Error al scrapear bandas actuales: {e}")
        
    if not df_final.empty:
        df_final['fecha'] = pd.to_datetime(df_final['fecha'], errors='coerce')
        df_final = df_final.dropna(subset=['fecha']).drop_duplicates(subset=['fecha']).sort_values('fecha')
        return df_final
        
    return pd.DataFrame(columns=['fecha', 'banda_inferior', 'banda_superior'])

def fetch_bcra_history(id_var, nombre, is_daily=False):
    print(f"Descargando {nombre}...")
    df_acumulado = pd.DataFrame()
    offset = 0
    while True:
        try:
            r = http_get(f"https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/{id_var}?limit=3000&offset={offset}", timeout=20)
            if r.status_code != 200: break
            data = r.json().get('results', [{}])[0].get('detalle')
            if not data: break
            df_acumulado = pd.concat([df_acumulado, pd.DataFrame(data)], ignore_index=True)
            if len(data) < 3000 or len(df_acumulado) >= 15000: break
            offset += 3000
        except Exception as e:
            print(f"  -> {nombre}: error de red ({e})")
            break
    if df_acumulado.empty: return pd.DataFrame(columns=['fecha', nombre])
    df_acumulado['fecha'] = pd.to_datetime(df_acumulado['fecha'])
    df_acumulado['valor'] = pd.to_numeric(df_acumulado['valor'], errors='coerce')
    df_acumulado = df_acumulado.rename(columns={'valor': nombre})
    
    if is_daily:
        df_acumulado['fecha'] = df_acumulado['fecha'].dt.strftime('%Y-%m-%d')
        return df_acumulado.groupby('fecha').last().reset_index()[['fecha', nombre]]
    else:
        df_acumulado['periodo'] = df_acumulado['fecha'].dt.to_period('M')
        df_acumulado = df_acumulado.groupby('periodo').last().reset_index()
        df_acumulado['fecha'] = df_acumulado['periodo'].dt.strftime('%Y-%m')
        return df_acumulado[['fecha', nombre]]

# =====================================================================
#  POST-PROCESO (funciones puras: se pueden probar sin red)
# =====================================================================
USD_COLS = ['depositos_usd', 'prestamos_usd', 'reservas', 'compra_divisas']
ARS_COLS = ['adelantos', 'documentos', 'hipotecarios', 'prendarios', 'personales', 'tarjetas',
            'cc', 'ca', 'plazo_fijo', 'base_monetaria', 'm2', 'm2_transaccional',
            'circulacion_monetaria', 'billetes_monedas', 'pases_pasivos', 'lefi',
            'tc_mayorista', 'tc_minorista', 'dolar_mep', 'dolar_blue', 'dolar_ccl', 'banda_inferior', 'banda_superior']
# Columnas que se calculan en cada corrida (no se guardan como "memoria")
DERIVADAS = ['us_cpi_index', 'ipc_index', 'tc_mayorista_var', 'brecha_mep', 'brecha_blue', 'brecha_ccl']
# Columnas viejas que el bot ya no genera y que el dashboard no usa
HUERFANAS = ['emae', 'desempleo']
# Series que publican con rezago: en modo --offline se les recorta la cola repetida (ver recortar_colas_repetidas)
COLS_REZAGADAS = ['us_cpi', 'itcrm', 'ipc_mensual', 'ipc_interanual', 'rem_interanual']
REM_DESFASE = 12          # el REM a 12 meses se muestra en el mes al que apunta
MAX_MESES = 600           # 50 años
MAX_DIAS = 1000
DECIMALES = 4
MIN_FRACCION_BCRA = 0.5   # si responden menos de la mitad de las series del BCRA, la corrida falla
CLAVES_ULTIMO_MENSUAL = ['tc_mayorista', 'ipc_mensual', 'ipc_interanual', 'reservas', 'tasa_politica_tea',
                         'itcrm', 'us_cpi', 'tasa_fed', 'dolar_mep', 'riesgo_pais']
CLAVES_ULTIMO_DIARIO = ['badlar_tea', 'tamar_tea', 'riesgo_pais', 'banda_superior']


def restaurar_nominales(df):
    """El JSON guarda `col` deflactada y `col_corriente` nominal. Como memoria hay que volver
    a lo nominal: si no, un valor deflactado se volvería a deflactar en la corrida siguiente."""
    df = df.copy()
    for c in [c for c in df.columns if c.endswith('_corriente')]:
        df[c[:-len('_corriente')]] = df[c]
    df = df.drop(columns=[c for c in df.columns if c.endswith('_corriente')])
    if 'rem_interanual' in df.columns:
        df['rem_interanual'] = df['rem_interanual'].shift(-REM_DESFASE)  # se vuelve a aplicar al calcular
    return df.drop(columns=DERIVADAS + HUERFANAS, errors='ignore')


def completar_meses(df):
    """Índice mensual sin saltos (el shift del REM y el índice de precios dependen de eso)."""
    if df.empty:
        return df
    rango = pd.period_range(df.index.min(), df.index.max(), freq='M').strftime('%Y-%m')
    df = df.reindex(rango)
    df.index.name = 'fecha'
    return df


def ultimo_valido(df):
    return {c: df[c].last_valid_index() for c in df.columns}


def recortar_colas_repetidas(df, cols):
    """Corrige un JSON viejo que arrastraba el último dato repetido (ffill) hacia adelante:
    deja el primer valor de la racha final y borra el resto. Solo para series con rezago."""
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            continue
        s = df[c]
        ult = s.last_valid_index()
        if ult is None:
            continue
        pos = s.index.get_loc(ult)
        j = pos
        while j > 0 and s.iloc[j - 1] == s.iloc[pos]:
            j -= 1
        if j < pos:
            df.iloc[j + 1:, df.columns.get_loc(c)] = float('nan')
    return df


def _anular_despues(out, col, hasta):
    if col in out.columns and hasta is not None:
        out.loc[out.index > hasta, col] = float('nan')


def calcular_mensual(df, hoy):
    """df: índice 'YYYY-MM', columnas en valores NOMINALES. Devuelve (df_salida, ultimo_dato).
    - No hay filas posteriores al mes actual.
    - Se rellenan huecos intermedios, pero ninguna serie se extrapola más allá de su último dato real
      (salvo los índices de precios, que necesitan continuidad para deflactar)."""
    df = df[df.index <= hoy.strftime('%Y-%m')]
    df = completar_meses(df)
    if df.empty:
        return df, {}
    ultimo = ultimo_valido(df)
    rell = df.ffill()
    out = rell.copy()

    # --- Dólares reales (deflactados por CPI de EE.UU., base = último dato) ---
    for c in USD_COLS:
        if c in rell.columns:
            out[c + '_corriente'] = rell[c]
    if 'us_cpi' in rell.columns and rell['us_cpi'].notna().any():
        out['us_cpi_index'] = rell['us_cpi'] / rell['us_cpi'].dropna().iloc[-1]
        for c in USD_COLS:
            if c in rell.columns:
                out[c] = rell[c] / out['us_cpi_index']

    # --- Pesos reales (deflactados por IPC; si falta el último mes se asume la inflación del anterior) ---
    if 'ipc_mensual' in rell.columns:
        factor = 1 + rell['ipc_mensual'].fillna(0) / 100.0
        factor.iloc[0] = 1.0
        indice = factor.cumprod()
        out['ipc_index'] = indice / indice.iloc[-1]
        for c in ARS_COLS:
            if c in rell.columns:
                out[c + '_corriente'] = rell[c]
                out[c] = rell[c] / out['ipc_index']

    # --- Derivadas sobre valores nominales ---
    if 'tc_mayorista' in rell.columns:
        out['tc_mayorista_var'] = rell['tc_mayorista'].pct_change() * 100
    if 'tc_minorista' in rell.columns:
        for nombre in ('mep', 'blue', 'ccl'):
            if f'dolar_{nombre}' in rell.columns:
                out[f'brecha_{nombre}'] = (rell[f'dolar_{nombre}'] / rell['tc_minorista'] - 1) * 100

    # --- REM: se desplaza 12 meses (sin extrapolar antes de desplazar) ---
    if 'rem_interanual' in df.columns:
        rem = df['rem_interanual'].ffill()
        if ultimo.get('rem_interanual') is not None:
            rem[rem.index > ultimo['rem_interanual']] = float('nan')
        out['rem_interanual'] = rem.shift(REM_DESFASE)

    # --- Nada se extrapola más allá del último dato real de su serie ---
    for c, hasta in ultimo.items():
        if c == 'rem_interanual':
            continue
        _anular_despues(out, c, hasta)
        _anular_despues(out, c + '_corriente', hasta)
    _anular_despues(out, 'tc_mayorista_var', ultimo.get('tc_mayorista'))
    for nombre in ('mep', 'blue', 'ccl'):
        deps = [ultimo.get(f'dolar_{nombre}'), ultimo.get('tc_minorista')]
        _anular_despues(out, f'brecha_{nombre}', None if None in deps else min(deps))

    out = out.drop(columns=HUERFANAS, errors='ignore').tail(MAX_MESES)
    return out, ultimo


def calcular_diario(df, hoy):
    """Igual criterio que el mensual: sin fechas futuras y sin extrapolar más allá del último dato."""
    df = df[df.index <= hoy.strftime('%Y-%m-%d')]
    if df.empty:
        return df, {}
    ultimo = ultimo_valido(df)
    out = df.ffill()
    for c, hasta in ultimo.items():
        _anular_despues(out, c, hasta)
    return out.tail(MAX_DIAS), ultimo


def _valor_json(v):
    if v is None:
        return None
    if isinstance(v, float):
        return None if (math.isnan(v) or math.isinf(v)) else round(v, DECIMALES)
    return v


def tabla_a_json(df):
    """{'fecha': [...], 'col': [...]} con None donde falta el dato (JSON válido, sin NaN)."""
    if df.empty:
        return {}
    df = df.reset_index()
    return {c: [_valor_json(v) for v in df[c].tolist()] for c in df.columns}


# =====================================================================
#  MEMORIA Y FUENTES
# =====================================================================
def cargar_memoria(json_path):
    """Lee el JSON anterior (si existe) para no dejar huecos cuando una fuente falla."""
    vacio = pd.DataFrame()
    if not os.path.exists(json_path):
        return vacio, vacio
    print("-> Cargando datos históricos anteriores para prevenir blancos...")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data_old = json.load(f)
    except Exception as e:
        print(f"  -> No se pudo leer el JSON anterior ({e}); se arranca sin memoria.")
        return vacio, vacio

    def tabla(clave, formato):
        crudo = data_old.get(clave)
        if not crudo:
            return vacio
        df = pd.DataFrame(crudo)
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        df = df.dropna(subset=['fecha'])
        df['fecha'] = df['fecha'].dt.strftime(formato)
        df = df.drop_duplicates(subset=['fecha'], keep='last').set_index('fecha')
        return df.apply(pd.to_numeric, errors='coerce')

    mensual = tabla('mensual', '%Y-%m')
    if not mensual.empty:
        mensual = restaurar_nominales(mensual)
    return mensual, tabla('diario', '%Y-%m-%d')


def _a_mensual(df_ext, columnas=None):
    df_ext = df_ext.copy()
    df_ext['fecha'] = pd.to_datetime(df_ext['fecha'], errors='coerce')
    df_ext = df_ext.dropna(subset=['fecha'])
    df_ext['periodo'] = df_ext['fecha'].dt.to_period('M')
    df_ext = df_ext.groupby('periodo').last().reset_index()
    df_ext['fecha'] = df_ext['periodo'].dt.strftime('%Y-%m')
    df_ext = df_ext.drop(columns=['periodo'])
    return df_ext if columnas is None else df_ext[['fecha'] + columnas]


def armar_mensual_fresco(externos, series_bcra, df_bandas, df_rp):
    df_mensual = pd.DataFrame(columns=['fecha'])
    for df_externo in externos:
        if not df_externo.empty:
            df_mensual = pd.merge(df_mensual, _a_mensual(df_externo), on='fecha', how='outer')
    for df_temp in series_bcra:
        if not df_temp.empty:
            df_mensual = pd.merge(df_mensual, df_temp, on='fecha', how='outer')
    if not df_bandas.empty:
        df_mensual = pd.merge(df_mensual, _a_mensual(df_bandas, ['banda_inferior', 'banda_superior']), on='fecha', how='outer')
    if not df_rp.empty:
        df_mensual = pd.merge(df_mensual, _a_mensual(df_rp, ['riesgo_pais']), on='fecha', how='outer')
    df_mensual = df_mensual.dropna(subset=['fecha'])
    return df_mensual.set_index('fecha') if not df_mensual.empty else pd.DataFrame()


def armar_diario_fresco(series_diarias, df_bandas, df_rp):
    df_diario = pd.DataFrame(columns=['fecha'])
    for df_temp in series_diarias:
        if not df_temp.empty:
            df_diario = pd.merge(df_diario, df_temp, on='fecha', how='outer')
    for extra in (df_bandas, df_rp):
        if not extra.empty:
            extra = extra.copy()
            extra['fecha'] = extra['fecha'].dt.strftime('%Y-%m-%d')
            df_diario = pd.merge(df_diario, extra, on='fecha', how='outer')
    df_diario = df_diario.dropna(subset=['fecha'])
    return df_diario.set_index('fecha') if not df_diario.empty else pd.DataFrame()


def combinar(fresco, memoria):
    """Los datos nuevos mandan; la memoria solo completa lo que la fuente no devolvió."""
    if fresco.empty:
        return memoria.copy()
    if memoria.empty:
        return fresco
    return fresco.combine_first(memoria)


def sin_cambios(json_path, salida):
    """True si el JSON ya guardado tiene exactamente los mismos datos (ignora la marca de tiempo)."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            previo = json.load(f)
        mismos_datos = previo.get('mensual') == salida['mensual'] and previo.get('diario') == salida['diario']
        return mismos_datos and previo.get('meta', {}).get('ultimo_dato') == salida['meta']['ultimo_dato']
    except Exception:
        return False


def hoy_argentina():
    try:
        return pd.Timestamp.now(tz='America/Argentina/Buenos_Aires').tz_localize(None).normalize()
    except Exception:
        return pd.Timestamp.now().normalize()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Actualiza datos_historicos.json del dashboard del CEER.")
    ap.add_argument('--offline', action='store_true',
                    help="No descarga nada: solo re-normaliza el JSON existente (útil para limpiarlo o probar).")
    ap.add_argument('--hoy', help="Fecha de referencia YYYY-MM-DD (por defecto, hoy en Argentina).")
    args = ap.parse_args(argv)

    hoy = pd.Timestamp(args.hoy) if args.hoy else hoy_argentina()
    json_path = os.path.join(BASE_DIR, 'datos_historicos.json')
    print(f"=== INICIANDO ROBOT BCRA ({hoy.strftime('%Y-%m-%d')}{' · OFFLINE' if args.offline else ''}) ===")

    mensual_old, diario_old = cargar_memoria(json_path)
    estado = {'offline': True} if args.offline else {}

    if args.offline:
        mensual_fresco, diario_fresco = pd.DataFrame(), pd.DataFrame()
        mensual_old = recortar_colas_repetidas(mensual_old, COLS_REZAGADAS) if not mensual_old.empty else mensual_old
    else:
        print("=== CONSTRUYENDO BASE DE DATOS ===")
        df_dolares = fetch_dolares_history()
        df_itcrm = fetch_itcrm_excel()
        df_us_cpi = fetch_us_cpi(mensual_old)
        df_fed = fetch_tasa_fed()
        df_bandas = fetch_bandas_cambiarias()
        df_rp = fetch_riesgo_pais()

        series_bcra = [fetch_bcra_history(i, n, is_daily=False) for i, n in VARS_MENSUAL.items()]
        series_diarias = [fetch_bcra_history(i, n, is_daily=True) for i, n in VARS_DIARIO.items()]
        ok_bcra = sum(1 for d in series_bcra if not d.empty)

        estado = {
            'bcra_variables_ok': ok_bcra, 'bcra_variables_total': len(series_bcra),
            'dolares': not df_dolares.empty and len(df_dolares.columns) > 1,
            'itcrm': not df_itcrm.empty and len(df_itcrm.columns) > 1,
            'us_cpi_bls': not df_us_cpi.empty, 'tasa_fed': not df_fed.empty,
            'bandas': not df_bandas.empty, 'riesgo_pais': not df_rp.empty,
        }
        caidas = [k for k, v in estado.items() if v is False]
        print(f"\n=== ESTADO DE FUENTES === {json.dumps(estado, ensure_ascii=False)}")
        if caidas:
            print(f"::warning::Fuentes sin respuesta (se usa la memoria del JSON anterior): {', '.join(caidas)}")
        if ok_bcra < len(series_bcra) * MIN_FRACCION_BCRA:
            print(f"::error::Solo respondieron {ok_bcra}/{len(series_bcra)} series del BCRA. No se escribe el JSON.")
            sys.exit(1)

        mensual_fresco = armar_mensual_fresco([df_us_cpi, df_itcrm, df_dolares, df_fed], series_bcra, df_bandas, df_rp)
        diario_fresco = armar_diario_fresco(series_diarias, df_bandas, df_rp)

    df_mensual, ultimo_m = calcular_mensual(combinar(mensual_fresco, mensual_old), hoy)
    df_diario, ultimo_d = calcular_diario(combinar(diario_fresco, diario_old), hoy)
    if df_mensual.empty:
        print("::error::No hay datos mensuales para escribir.")
        sys.exit(1)

    salida = {
        'meta': {
            'actualizado': pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%dT%H:%M:%SZ'),
            'hoy': hoy.strftime('%Y-%m-%d'),
            'fuentes': estado,
            'ultimo_dato': {
                'mensual': {c: ultimo_m.get(c) for c in CLAVES_ULTIMO_MENSUAL},
                'diario': {c: ultimo_d.get(c) for c in CLAVES_ULTIMO_DIARIO},
            },
        },
        'mensual': tabla_a_json(df_mensual),
        'diario': tabla_a_json(df_diario),
    }
    if sin_cambios(json_path, salida):
        print("\nSin datos nuevos: no se reescribe el JSON (así el workflow no ensucia el historial con commits vacíos).")
        return
    tmp = json_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(salida, f, separators=(',', ':'), allow_nan=False)
    os.replace(tmp, json_path)
    print(f"\n¡LISTO! Datos guardados en {json_path} "
          f"({len(df_mensual)} meses hasta {df_mensual.index[-1]}, {len(df_diario)} días)")


if __name__ == '__main__':
    main()
