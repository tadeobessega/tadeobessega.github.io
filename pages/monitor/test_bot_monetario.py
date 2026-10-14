"""Tests del post-proceso del bot (no usan red). Correr con:  python -m unittest pages/monitor/test_bot_monetario.py -v"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_monetario as bot  # noqa: E402

HOY = pd.Timestamp('2026-05-15')


def memoria_sintetica():
    """24 meses nominales hasta 2026-04; el IPC de EE.UU. termina en 2026-02 (rezago)."""
    meses = pd.period_range('2024-05', '2026-04', freq='M').strftime('%Y-%m')
    n = len(meses)
    df = pd.DataFrame(index=pd.Index(meses, name='fecha'))
    df['ipc_mensual'] = 2.0
    df['us_cpi'] = [300 + i * 0.5 for i in range(n)]
    df.loc[df.index > '2026-02', 'us_cpi'] = float('nan')
    df['m2'] = [1000.0 * (1.02 ** i) for i in range(n)]
    df['reservas'] = [40000.0 + 100 * i for i in range(n)]
    df['tc_mayorista'] = [1000.0 + 10 * i for i in range(n)]
    df['tc_minorista'] = df['tc_mayorista'] * 1.01
    df['dolar_mep'] = df['tc_mayorista'] * 1.05
    df['rem_interanual'] = [20.0 + 0.1 * i for i in range(n)]
    df['banda_superior'] = float('nan')
    df.loc[df.index >= '2025-06', 'banda_superior'] = 1500.0
    return df


class PostProceso(unittest.TestCase):
    def test_sin_filas_futuras_ni_extrapolacion(self):
        mem = memoria_sintetica()
        # una fila futura copiada (lo que hacía el ffill viejo)
        futura = mem.iloc[[-1]].copy()
        futura.index = pd.Index(['2026-11'], name='fecha')
        out, ultimo = bot.calcular_mensual(pd.concat([mem, futura]), HOY)
        self.assertEqual(out.index[-1], '2026-04')  # la fila de 2026-11 y todo lo posterior a hoy se descarta
        self.assertTrue((out.index <= HOY.strftime('%Y-%m')).all())
        self.assertEqual(ultimo['us_cpi'], '2026-02')
        # us_cpi no se extrapola, pero su índice (deflactor) sí se mantiene
        self.assertTrue(out.loc['2026-03':, 'us_cpi'].isna().all())
        self.assertTrue(out['us_cpi_index'].notna().all())

    def test_ultimo_mes_deflactado_vale_igual_al_nominal(self):
        out, _ = bot.calcular_mensual(memoria_sintetica(), HOY)
        self.assertAlmostEqual(out['m2'].iloc[-1], out['m2_corriente'].iloc[-1])
        self.assertAlmostEqual(out['ipc_index'].iloc[-1], 1.0)

    def test_ida_y_vuelta_no_deflacta_dos_veces(self):
        """Guardar -> cargar como memoria -> volver a calcular debe dar lo mismo."""
        out1, _ = bot.calcular_mensual(memoria_sintetica(), HOY)
        guardado = pd.DataFrame(bot.tabla_a_json(out1)).set_index('fecha')
        restaurado = bot.restaurar_nominales(guardado)
        out2, _ = bot.calcular_mensual(restaurado, HOY)
        for col in ['m2', 'm2_corriente', 'reservas', 'reservas_corriente', 'tc_mayorista', 'brecha_mep', 'rem_interanual']:
            pd.testing.assert_series_equal(out1[col].round(3), out2[col].round(3), check_names=False, obj=col)

    def test_rem_se_desplaza_12_meses(self):
        mem = memoria_sintetica()
        out, _ = bot.calcular_mensual(mem, HOY)
        self.assertAlmostEqual(out.loc['2025-05', 'rem_interanual'], mem.loc['2024-05', 'rem_interanual'])
        self.assertTrue(out.loc[:'2025-04', 'rem_interanual'].isna().all())

    def test_columnas_huerfanas_se_descartan(self):
        mem = memoria_sintetica()
        mem['emae'] = 150.0
        mem['desempleo'] = 0.075
        out, _ = bot.calcular_mensual(mem, HOY)
        self.assertNotIn('emae', out.columns)
        self.assertNotIn('desempleo', out.columns)

    def test_diario_sin_futuro_y_sin_cola_rellenada(self):
        dias = pd.date_range('2026-05-01', '2026-05-31').strftime('%Y-%m-%d')
        df = pd.DataFrame(index=pd.Index(dias, name='fecha'))
        df['badlar_tea'] = 30.0
        df.loc[df.index > '2026-05-11', 'badlar_tea'] = float('nan')
        df['banda_superior'] = 1500.0
        out, ultimo = bot.calcular_diario(df, HOY)
        self.assertEqual(out.index[-1], '2026-05-15')
        self.assertEqual(ultimo['badlar_tea'], '2026-05-11')
        self.assertTrue(out.loc['2026-05-12':, 'badlar_tea'].isna().all())

    def test_recortar_colas_repetidas(self):
        df = pd.DataFrame({'us_cpi': [1.0, 2.0, 3.0, 3.0, 3.0], 'otra': [5.0, 5.0, 5.0, 5.0, 5.0]},
                          index=pd.Index(['2026-01', '2026-02', '2026-03', '2026-04', '2026-05'], name='fecha'))
        out = bot.recortar_colas_repetidas(df, ['us_cpi'])
        self.assertEqual(out['us_cpi'].last_valid_index(), '2026-03')
        self.assertEqual(out['otra'].last_valid_index(), '2026-05')  # solo toca las columnas pedidas

    def test_json_valido_sin_nan(self):
        out, _ = bot.calcular_mensual(memoria_sintetica(), HOY)
        texto = json.dumps(bot.tabla_a_json(out), allow_nan=False)  # lanza ValueError si queda NaN/inf
        self.assertNotIn('NaN', texto)


class Escritura(unittest.TestCase):
    def test_no_reescribe_si_los_datos_son_iguales(self):
        out, ultimo = bot.calcular_mensual(memoria_sintetica(), HOY)
        salida = {'meta': {'actualizado': 'x', 'ultimo_dato': {'mensual': ultimo}},
                  'mensual': bot.tabla_a_json(out), 'diario': {}}
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, 'd.json')
            self.assertFalse(bot.sin_cambios(ruta, salida))  # no existe todavía
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump(salida, f)
            otra_hora = json.loads(json.dumps(salida))
            otra_hora['meta']['actualizado'] = 'otra hora'
            self.assertTrue(bot.sin_cambios(ruta, otra_hora))  # solo cambió la marca de tiempo
            otra_hora['mensual']['m2'][0] += 1
            self.assertFalse(bot.sin_cambios(ruta, otra_hora))  # cambió un dato


class Fuentes(unittest.TestCase):
    def test_cpi_bls_api(self):
        respuesta = mock.Mock()
        respuesta.raise_for_status.return_value = None
        respuesta.json.return_value = {
            'status': 'REQUEST_SUCCEEDED',
            'Results': {'series': [{'data': [
                {'year': '2026', 'period': 'M03', 'value': '330.213'},
                {'year': '2026', 'period': 'M02', 'value': '326.785'},
                {'year': '2026', 'period': 'M13', 'value': '999'},      # promedio anual: se ignora
                {'year': '2026', 'period': 'M01', 'value': '-'},         # dato faltante
            ]}]}}
        with mock.patch.object(bot, 'http_get', return_value=respuesta):
            df = bot.fetch_us_cpi_api()
        self.assertEqual(df['fecha'].dt.strftime('%Y-%m').tolist(), ['2026-02', '2026-03'])
        self.assertEqual(df['us_cpi'].tolist(), [326.785, 330.213])

    def test_cpi_bls_api_caida_devuelve_vacio(self):
        with mock.patch.object(bot, 'http_get', side_effect=OSError('sin red')):
            self.assertTrue(bot.fetch_us_cpi_api().empty)

    def test_la_corrida_falla_si_el_bcra_no_responde(self):
        vacio = pd.DataFrame(columns=['fecha'])
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(bot, 'BASE_DIR', tmp), \
                mock.patch.object(bot, 'fetch_dolares_history', return_value=vacio), \
                mock.patch.object(bot, 'fetch_itcrm_excel', return_value=vacio), \
                mock.patch.object(bot, 'fetch_us_cpi', return_value=pd.DataFrame(columns=['fecha', 'us_cpi'])), \
                mock.patch.object(bot, 'fetch_tasa_fed', return_value=vacio), \
                mock.patch.object(bot, 'fetch_bandas_cambiarias', return_value=vacio), \
                mock.patch.object(bot, 'fetch_riesgo_pais', return_value=vacio), \
                mock.patch.object(bot, 'fetch_bcra_history', side_effect=lambda i, n, is_daily=False: pd.DataFrame(columns=['fecha', n])):
            with self.assertRaises(SystemExit) as cm:
                bot.main(['--hoy', '2026-05-15'])
            self.assertEqual(cm.exception.code, 1)
            self.assertFalse(os.path.exists(os.path.join(tmp, 'datos_historicos.json')))  # no pisa el JSON


if __name__ == '__main__':
    unittest.main()
