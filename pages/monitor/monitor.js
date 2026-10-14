const C_PRINCIPAL = '#1A1AE6';
const C_INFORMES = '#06B6D4'; //24BBF2
const C_MORADO = '#5021BA'; // 4404C5
const C_AZUL_CLARO = '#7C4AED'; // A984FE
const C_MORADO_CLARO = '#8A52FF'; // 8A52FF
const C_TEXT = '#111827';

// Paleta de fondos — modificar acá para cambiar toda la jerarquía de colores
const BG_PAGINA = '#FAFAFA'; // fondo de página y body
const BG_TARJETA = '#F2F2F2'; // fondo de card y canvas del gráfico
const BG_GRAFICO = '#FAFAFA'; // área interior del gráfico (plugin chartAreaBg)

Chart.register({ id: 'customCanvasBackgroundColor', beforeDraw: (c) => { const ctx = c.canvas.getContext('2d'); ctx.save(); ctx.globalCompositeOperation = 'destination-over'; ctx.fillStyle = BG_TARJETA; ctx.fillRect(0, 0, c.width, c.height); ctx.restore(); } });
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.weight = '600';
Chart.defaults.color = C_TEXT;

window.allCharts = []; window.data_m = {}; window.fechas_m = []; window.cGen = null;

const DICT = {
    'bandas': { l: 'Bandas Cambiarias (ARS/USD)', cD: true, isU: false },
    'riesgo_pais': { l: 'Riesgo País (Puntos Básicos)', cD: false, isU: false },
    'tasa_fed': { l: 'Tasa FED (EFFR %)', cD: false, isU: false },
    'tc_minorista': { l: 'T.C. Minorista (ARS/USD)', cD: true, isU: false }, 'tc_mayorista': { l: 'T.C. Mayorista (ARS/USD)', cD: true, isU: false },
    'dolar_mep': { l: 'Dólar MEP (ARS/USD)', cD: true, isU: false }, 'dolar_blue': { l: 'Dólar Blue (ARS/USD)', cD: true, isU: false }, 'dolar_ccl': { l: 'Dólar CCL (ARS/USD)', cD: true, isU: false },
    'brecha_mep': { l: 'Brecha MEP (%)', cD: false, isU: false }, 'brecha_blue': { l: 'Brecha Blue (%)', cD: false, isU: false }, 'brecha_ccl': { l: 'Brecha CCL (%)', cD: false, isU: false },
    'itcrm': { l: 'ITCRM General (Base 100)', cD: false, isU: false }, 'tcr_brasil': { l: 'TCR Brasil', cD: false, isU: false }, 'tcr_usa': { l: 'TCR EE.UU.', cD: false, isU: false }, 'tcr_zona_euro': { l: 'TCR Euro', cD: false, isU: false }, 'tcr_china': { l: 'TCR China', cD: false, isU: false }, 'tcr_mexico': { l: 'TCR México', cD: false, isU: false }, 'tcr_chile': { l: 'TCR Chile', cD: false, isU: false }, 'tcr_uruguay': { l: 'TCR Uruguay', cD: false, isU: false },
    'base_monetaria': { l: 'Base Monetaria (ARS)', cD: true, isU: false }, 'circulacion_monetaria': { l: 'Circulación Monetaria (ARS)', cD: true, isU: false }, 'billetes_monedas': { l: 'Billetes Público (ARS)', cD: true, isU: false }, 'm2': { l: 'M2 Total (ARS)', cD: true, isU: false }, 'm2_transaccional': { l: 'M2 Transaccional (ARS)', cD: true, isU: false }, 'pases_pasivos': { l: 'Pases Pasivos (ARS)', cD: true, isU: false }, 'lefi': { l: 'LEFI (ARS)', cD: true, isU: false },
    'tarjetas': { l: 'Préstamos: Tarjetas (ARS)', cD: true, isU: false }, 'personales': { l: 'Préstamos: Personales (ARS)', cD: true, isU: false }, 'hipotecarios': { l: 'Préstamos: Hipotecarios (ARS)', cD: true, isU: false }, 'prendarios': { l: 'Préstamos: Prendarios (ARS)', cD: true, isU: false }, 'plazo_fijo': { l: 'Depósitos: Plazo Fijo (ARS)', cD: true, isU: false }, 'ca': { l: 'Cajas Ahorro (ARS)', cD: true, isU: false }, 'cc': { l: 'Cuentas Ctes (ARS)', cD: true, isU: false },
    'depositos_usd': { l: 'Depósitos Privados (USD)', cD: true, isU: true }, 'prestamos_usd': { l: 'Préstamos Privados (USD)', cD: true, isU: true }, 'reservas': { l: 'Reservas Brutas BCRA (USD)', cD: true, isU: true }, 'compra_divisas': { l: 'Compras BCRA (USD)', cD: true, isU: true },
    'tc_mayorista_var': { l: 'Devaluación (%)', cD: false, isU: false }, 'ipc_mensual': { l: 'IPC Mensual (%)', cD: false, isU: false }, 'ipc_interanual': { l: 'IPC Interanual (%)', cD: false, isU: false }, 'rem_interanual': { l: 'REM 12m (%)', cD: false, isU: false },
    'tasa_politica_tea': { l: 'Tasa Política (TEA %)', cD: false, isU: false }, 'badlar_tea': { l: 'BADLAR (TEA %)', cD: false, isU: false }, 'tamar_tea': { l: 'TAMAR (TEA %)', cD: false, isU: false }
};

function setMode(m) {
    document.body.classList.toggle('mobile-mode', m === 'mobile');
    if (document.getElementById('btnMobile')) {
        document.getElementById('btnMobile').classList.toggle('active', m === 'mobile');
        document.getElementById('btnDesktop').classList.toggle('active', m === 'desktop');
    }
    if (window.allCharts) window.allCharts.forEach(c => { if (c.canvas) c.resize(); });
}

function verTab(e, id) { document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active')); document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active')); document.getElementById(id).classList.add('active'); e.currentTarget.classList.add('active'); window.allCharts.forEach(c => c.update()); }

function filtrarTexto(){
let s=document.getElementById('dateStart').value, e=document.getElementById('dateEnd').value;
let st_m=window.fechas_m[0], en_m=window.fechas_m[window.fechas_m.length-1];
let st_d=window.fechas_d[0], en_d=window.fechas_d[window.fechas_d.length-1];
if(s){ let s_m=s.substring(0,7); st_m=window.fechas_m.find(f=>f>=s_m)||st_m; st_d=window.fechas_d.find(f=>f>=s)||st_d; }
if(e){ let e_m=e.substring(0,7); en_m=[...window.fechas_m].reverse().find(f=>f<=e_m)||en_m; en_d=[...window.fechas_d].reverse().find(f=>f<=e)||en_d; }

window.allCharts.forEach(c=>{
    try {
        if(c.options.scales.x && c.config.type !== 'scatter'){
            c.options.scales.x.min = (c.canvas.id==='chartDiario')?st_d:st_m;
            c.options.scales.x.max = (c.canvas.id==='chartDiario')?en_d:en_m;
            
            // BUSCAR DONDE TODAS LAS LÍNEAS TENGAN DATOS AL MISMO TIEMPO (Intersección)
            if (c.data.labels && c.data.labels.length > 0) {
                let indicesInicio = [];
                if (c.data.datasets) {
                    c.data.datasets.forEach(ds => {
                        if (ds.data && Array.isArray(ds.data)) {
                            let idx = ds.data.findIndex(val => val !== null && val !== undefined && !Number.isNaN(val));
                            if(idx !== -1) indicesInicio.push(idx);
                        }
                    });
                }
                
                // Aplicar recorte automático si el usuario no fijó fecha manual "Desde"
                if (indicesInicio.length > 0 && !s) {
                    // Math.max toma el inicio más "tardío" entre todas las variables del gráfico
                    let inicioComun = Math.max(...indicesInicio);
                    c.options.scales.x.min = c.data.labels[inicioComun];
                }
            }
            c.update();
        }
    } catch (err) {
        console.error("Error ajustando fechas:", err);
    }
});
    }
function initGen() {
    [1, 2].forEach(i => {
        const sel = document.getElementById(`genSelect${i}`);
        sel.innerHTML = '<option value="" disabled selected>-- Seleccione una Métrica --</option>';
        for (let k in DICT) sel.appendChild(new Option(DICT[k].l, k));
    });
}

function chkDef(n) {
    const val = document.getElementById(`genSelect${n}`).value;
    if (val) document.getElementById(`genNom${n}`).disabled = !DICT[val].cD;
}

function toggleModoGen() {
    let isSc = document.getElementById('genModo').value === 'scatter';
    if (isSc) {
        document.querySelector('input[name="numVars"][value="2"]').checked = true;
        document.querySelector('input[name="numVars"][value="1"]').disabled = true;
    } else {
        document.querySelector('input[name="numVars"][value="1"]').disabled = false;
    }
    let v2 = document.querySelector('input[name="numVars"]:checked').value === '2';
    document.getElementById('panelVar2').style.opacity = v2 ? 1 : 0.5;
    document.getElementById('panelVar2').style.pointerEvents = v2 ? 'auto' : 'none';

    document.getElementById('wrapType1').style.display = isSc ? 'none' : 'flex';
    document.getElementById('wrapType2').style.display = isSc ? 'none' : 'flex';
    document.getElementById('wrapAxis2').style.display = isSc ? 'none' : 'flex';
}

function crearGen() {
    try {
        let v1_val = document.getElementById('genSelect1').value;
        if (!v1_val) { alert("Por favor, seleccioná al menos una métrica para la Variable 1."); return; }

        if (document.querySelector('input[name="numVars"]:checked').value === '2') {
            let v2_val = document.getElementById('genSelect2').value;
            if (!v2_val) { alert("Por favor, seleccioná la métrica para la Variable 2."); return; }
        }

        document.getElementById('resultadoGenerador').style.display = 'block';

        if (window.cGen) {
            window.allCharts = window.allCharts.filter(c => c !== window.cGen);
            window.cGen.destroy();
            window.cGen = null;
        }
        document.getElementById('canvasContainer').innerHTML = '<canvas id="chartGenerador"></canvas>';

        const getD = (n) => {
            const v = document.getElementById(`genSelect${n}`).value;
            const quiereCorriente = document.getElementById(`genNom${n}`).value === 'corriente';

            if (v === 'bandas') {
                let d_inf = window.data_m['banda_inferior' + (quiereCorriente ? '_corriente' : '')] || window.data_m['banda_inferior'];
                let d_sup = window.data_m['banda_superior' + (quiereCorriente ? '_corriente' : '')] || window.data_m['banda_superior'];
                return { isBanda: true, l: DICT[v].l + (quiereCorriente ? ' (Nominal)' : ''), d_inf: d_inf || [], d_sup: d_sup || [], t: 'line' };
            }

            let dataFinal = window.data_m[v] || [];
            if (DICT[v].cD && quiereCorriente) { dataFinal = window.data_m[v + '_corriente'] || window.data_m[v] || []; }
            return { isBanda: false, l: DICT[v].l + (DICT[v].cD && quiereCorriente ? ' (Nominal)' : ''), d: dataFinal, t: document.getElementById(`genType${n}`).value };
        };

        let sources = new Set();
        const addSrc = (v, n) => {
            if (v === 'riesgo_pais') sources.add('Ámbito');
            else if (v === 'tasa_fed') sources.add('NY Fed');
            else {
                sources.add('BCRA');
                if (DICT[v].isU && document.getElementById(`genNom${n}`).value === 'constante') sources.add('BLS');
            }
        };

        addSrc(v1_val, 1);
        if (document.querySelector('input[name="numVars"]:checked').value === '2') addSrc(document.getElementById('genSelect2').value, 2);

        let sArr = Array.from(sources);
        let fuenteSTR = 'Fuente: CEER en base a ' + (sArr.length === 1 ? sArr[0] : sArr.length === 2 ? sArr[0] + ' y ' + sArr[1] : sArr[0] + ', ' + sArr[1] + ' y ' + sArr[2]);

        let isSc = document.getElementById('genModo').value === 'scatter';
        let d1 = getD(1);

        if (isSc) {
            let d2 = getD(2);
            if (d1.isBanda || d2.isBanda) {
                alert("Las Bandas Cambiarias no se pueden usar en Gráficos de Correlación. Elegí Línea de Tiempo o cambiá la métrica."); return;
            }

            let pts = [];
            for (let i = 0; i < Math.min(d1.d.length, d2.d.length); i++) {
                if (d1.d[i] != null && d2.d[i] != null) pts.push({ y: d1.d[i], x: d2.d[i], label: window.fechas_m[i] });
            }

            if (pts.length < 2) {
                alert("No hay suficientes datos superpuestos en el tiempo entre ambas variables para calcular una correlación.");
                return;
            }

            let n = pts.length, sX = 0, sY = 0, sXY = 0, sXX = 0, sYY = 0;
            pts.forEach(p => { sX += p.x; sY += p.y; sXY += p.x * p.y; sXX += p.x * p.x; sYY += p.y * p.y; });
            let slope = (n * sXY - sX * sY) / (n * sXX - sX * sX); let intercept = (sY - slope * sX) / n;
            let r2 = Math.pow((n * sXY - sX * sY) / Math.sqrt((n * sXX - sX * sX) * (n * sYY - sY * sY)), 2);
            if (isNaN(r2)) r2 = 0;

            let minX = Math.min(...pts.map(p => p.x)), maxX = Math.max(...pts.map(p => p.x));

            let d = [
                { type: 'scatter', label: 'Observaciones', data: pts, backgroundColor: 'rgba(33,33,226,0.6)', pointRadius: 5, hoverRadius: 8 },
                { type: 'line', label: `Regresión (R² = ${r2.toFixed(4)})`, data: [{ x: minX, y: slope * minX + intercept }, { x: maxX, y: slope * maxX + intercept }], borderColor: C_MORADO, borderWidth: 3, pointRadius: 0, fill: false }
            ];

            window.cGen = buildC('chartGenerador', d, { x: { type: 'linear', position: 'bottom', title: { display: true, text: d2.l, font: { family: "'Inter', sans-serif", weight: '600' } } }, y: { title: { display: true, text: d1.l, font: { family: "'Inter', sans-serif", weight: '600' } } } }, false, true, fuenteSTR);
        } else {
            let d = [];

            const addDataset = (dObj, colorMain, yAxisID) => {
                if (dObj.isBanda) {
                    let colorBg = colorMain === C_PRINCIPAL ? 'rgba(33,33,226,0.1)' : 'rgba(0,0,222,0.1)';
                    d.push({ label: dObj.l + ' (Sup)', data: dObj.d_sup, borderColor: colorMain, backgroundColor: 'transparent', type: 'line', borderWidth: 2.5, yAxisID: yAxisID, pointRadius: 0 });
                    d.push({ label: dObj.l + ' (Inf)', data: dObj.d_inf, borderColor: colorMain, backgroundColor: colorBg, type: 'line', borderWidth: 2.5, yAxisID: yAxisID, fill: '-1', pointRadius: 0 });
                } else {
                    let bg = dObj.t !== 'line' ? (colorMain === C_PRINCIPAL ? 'rgba(33,33,226,0.2)' : 'rgba(68,4,197,0.2)') : null;
                    d.push({ label: dObj.l, data: dObj.d, borderColor: colorMain, backgroundColor: bg, type: dObj.t === 'area' ? 'line' : dObj.t, fill: dObj.t === 'area', borderWidth: 2.5, yAxisID: yAxisID });
                }
            };

            addDataset(d1, C_PRINCIPAL, 'y');
            let y1 = { display: false };
            if (document.querySelector('input[name="numVars"]:checked').value === '2') {
                let d2 = getD(2), u2 = document.getElementById('genAxis2').checked;
                addDataset(d2, C_MORADO, u2 ? 'y1' : 'y');
                if (u2) y1 = { type: 'linear', position: 'right', grid: { display: false }, border: { display: false }, ticks: { maxTicksLimit: 5, font: { family: "'Inter', sans-serif", weight: '400' } } };
            }
            window.cGen = buildC('chartGenerador', d, { y1: y1 }, false, false, fuenteSTR);
            filtrarTexto();
        }
        document.getElementById('resultadoGenerador').scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        alert("Oops! Ocurrió un error al generar el gráfico. Detalle técnico: " + error.message);
    }
}

// Plugin para fondo blanco solo en el área del gráfico (entre ejes), como Excel
const chartAreaBgPlugin = {
    id: 'chartAreaBg',
    beforeDraw(chart) {
        const { ctx, chartArea } = chart;
        if (!chartArea) return;
        ctx.save();
        ctx.fillStyle = BG_GRAFICO;
        ctx.fillRect(chartArea.left, chartArea.top, chartArea.width, chartArea.height);
        ctx.restore();
    }
};
Chart.register(chartAreaBgPlugin);

// Plugin para logo CEER en esquina inferior derecha de cada gráfico
const ceerLogoPlugin = {
    id: 'ceerLogo',
    afterDraw(chart) {
        const ctx = chart.ctx;
        const img = window._ceerLogoImg;
        if (!img || !img.complete) return;
        const { chartArea } = chart;
        if (!chartArea) return;
        const logoH = 22;
        const logoW = img.naturalWidth * (logoH / img.naturalHeight);
        const x = chartArea.right - logoW;
        const y = chart.height - logoH - 4;
        ctx.save();
        ctx.globalAlpha = 0.85;
        ctx.drawImage(img, x, y, logoW, logoH);
        ctx.restore();
    }
};
Chart.register(ceerLogoPlugin);

// Plugin para agregar espacio debajo de la leyenda
Chart.register({
    id: 'legendBottomPadding',
    beforeInit(chart) {
        const origFit = chart.legend.fit.bind(chart.legend);
        chart.legend.fit = function () { origFit(); this.height += 16; };
    }
});

// Precargar el logo CEER azul
window._ceerLogoImg = new Image();
window._ceerLogoImg.src = 'ceer_azul.png';

function buildC(id, datasets, extraScales = {}, stacked = false, isSc = false, fStr = 'Fuente: CEER en base a BCRA') {
    let s = { x: { grid: { display: false }, ticks: { maxRotation: 45, minRotation: 45, autoSkip: true, maxTicksLimit: 12, font: { family: "'Inter', sans-serif", weight: '400' } } }, y: { grid: { color: 'rgba(0,0,0,0.06)' }, border: { display: false }, stacked: stacked, ticks: { maxTicksLimit: 5, font: { family: "'Inter', sans-serif", weight: '400' } } } }; Object.assign(s, extraScales);
    let lbls = isSc ? undefined : (id === 'chartDiario' ? window.fechas_d : window.fechas_m);
    let c = new Chart(document.getElementById(id).getContext('2d'), {
        type: isSc ? 'scatter' : 'line',
        data: { labels: lbls, datasets: datasets },
        options: {
            responsive: true, maintainAspectRatio: false, interaction: { mode: isSc ? 'nearest' : 'index', intersect: false }, spanGaps: true,
            elements: { point: { radius: isSc ? 5 : 0, hitRadius: 10, hoverRadius: 6 } }, scales: s,
            plugins: {
                tooltip: { backgroundColor: 'rgba(33,33,226,0.95)', padding: 12, titleFont: { family: "'Inter', sans-serif", size: 13 }, bodyFont: { family: "'Inter', sans-serif", size: 13 }, cornerRadius: 8, callbacks: isSc ? { label: (ctx) => `${ctx.raw.label}: (${ctx.raw.x.toFixed(2)}, ${ctx.raw.y.toFixed(2)})` } : {} },
                subtitle: { display: true, text: fStr, position: 'bottom', align: 'start', font: { family: "'Inter', sans-serif", style: 'italic', weight: '600', size: 11, color: '#6b7280' }, padding: { top: 22 } },
                legend: {
                    labels: { usePointStyle: true, boxWidth: 8, padding: 15, font: { family: "'Inter', sans-serif", weight: '600' } }
                }
            }
        }
    });
    window.allCharts.push(c); return c;
}

function dlPNG(id) {
    const cv = document.getElementById(id);
    // Buscar la card contenedora para incluir título
    const card = cv.closest('.chart-card');
    if (card && typeof html2canvas !== 'undefined') {
        html2canvas(card, { backgroundColor: BG_TARJETA, scale: 2, useCORS: true }).then(canvas => {
            const a = document.createElement('a'); a.href = canvas.toDataURL('image/png'); a.download = id + '_ceer.png'; a.click();
        });
    } else {
        // Fallback: solo el canvas si html2canvas no está disponible
        const a = document.createElement('a'); a.href = cv.toDataURL('image/png'); a.download = id + '_ceer.png'; a.click();
    }
}

function dlCSV(id) {
    const c = Chart.getChart(id); if (!c) return;
    const d = c.data.datasets; let csv = '';
    if (c.config.type === 'scatter') {
        csv = `"Mes","${c.options.scales.x.title.text} (X)","${c.options.scales.y.title.text} (Y)"\n`;
        d[0].data.forEach(p => csv += `"${p.label}",${p.x},${p.y}\n`);
    } else {
        const l = c.data.labels; let sI = c.options.scales.x.min ? l.findIndex(x => x >= c.options.scales.x.min) : 0, eI = c.options.scales.x.max ? l.findLastIndex(x => x <= c.options.scales.x.max) : l.length - 1;
        if (sI === -1) sI = 0; if (eI === -1) eI = l.length - 1;
        csv = 'Fecha'; d.forEach(x => csv += `,"${x.label}"`); csv += '\n';
        for (let i = sI; i <= eI; i++) { csv += l[i]; d.forEach(x => { let v = x.data[i]; csv += ',' + (v !== null && v !== undefined ? v : ''); }); csv += '\n'; }
    }
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' })); a.download = id + '_ceer.csv'; a.click();
}

async function load() {
    try {
        const res = await fetch(`datos_historicos.json?v=${new Date().getTime()}`);
        if (!res.ok) throw new Error('HTTP Error ' + res.status);

        const rawText = await res.text();
        const raw = JSON.parse(rawText.replace(/NaN/g, "null"));

        window.fechas_m = raw.mensual.fecha || []; window.fechas_d = raw.diario.fecha || []; const cln = (a) => a ? a.map(v => v === null ? null : Number(v)) : [];
        for (let k in raw.mensual) window.data_m[k] = cln(raw.mensual[k]); const m = (k) => window.data_m[k] || []; const d = (k) => cln(raw.diario[k]);

        const getNom = (k) => window.data_m[k + '_corriente'] ? window.data_m[k + '_corriente'] : (window.data_m[k] || []);

        // APLICANDO COLORES OFICIALES Y DERIVADOS
        buildC('chartPrestamos', [
            { label: 'Prendarios', data: m('prendarios'), backgroundColor: C_PRINCIPAL, fill: true, stacked: true, borderWidth: 0 },
            { label: 'Hipotecarios', data: m('hipotecarios'), backgroundColor: C_INFORMES, fill: true, stacked: true, borderWidth: 0 },
            { label: 'Personales', data: m('personales'), backgroundColor: C_MORADO, fill: true, stacked: true, borderWidth: 0 },
            { label: 'Tarjetas', data: m('tarjetas'), backgroundColor: C_AZUL_CLARO, fill: true, stacked: true, borderWidth: 0 }
        ], {}, true);

        buildC('chartDepositos', [
            { label: 'Plazo Fijo', data: m('plazo_fijo'), backgroundColor: C_PRINCIPAL, fill: true, stacked: true, borderWidth: 0 },
            { label: 'Cajas Ahorro', data: m('ca'), backgroundColor: C_INFORMES, fill: true, stacked: true, borderWidth: 0 },
            { label: 'Cuentas Ctes', data: m('cc'), backgroundColor: C_MORADO, fill: true, stacked: true, borderWidth: 0 }
        ], {}, true);

        buildC('chartUSD', [{ label: 'Depósitos (USD Nominales)', data: getNom('depositos_usd'), borderColor: C_MORADO, borderWidth: 2.5, fill: false }, { label: 'Préstamos (USD Nominales)', data: getNom('prestamos_usd'), borderColor: C_PRINCIPAL, borderWidth: 2.5, fill: false }]);

        buildC('chartRiesgoPais', [{ label: 'Riesgo País', data: m('riesgo_pais'), borderColor: C_PRINCIPAL, fill: false, borderWidth: 2.5 }], {}, false, false, 'Fuente: CEER en base a Ámbito / ArgentinaDatos');

        buildC('chartBrecha', [
            { label: 'Brecha Blue (%)', data: m('brecha_blue'), borderColor: C_PRINCIPAL, fill: false, yAxisID: 'y', borderWidth: 2.5 },
            { label: 'Brecha MEP (%)', data: m('brecha_mep'), borderColor: C_INFORMES, fill: false, yAxisID: 'y', borderWidth: 2.5 },
            { label: 'Brecha CCL (%)', data: m('brecha_ccl'), borderColor: C_MORADO, fill: false, yAxisID: 'y', borderWidth: 2.5 }
        ]);

        buildC('chartITCRM', [{ label: 'ITCRM General', data: m('itcrm'), borderColor: C_PRINCIPAL, fill: false, borderWidth: 2.5 }]);
        buildC('chartReservas', [{ label: 'Reservas Brutas', data: m('reservas'), borderColor: C_PRINCIPAL, yAxisID: 'y', borderWidth: 2.5, fill: false }, { label: 'Compras BCRA', data: m('compra_divisas'), type: 'bar', yAxisID: 'y1', backgroundColor: C_MORADO_CLARO, borderRadius: 4 }], { y1: { type: 'linear', position: 'right', grid: { display: false }, border: { display: false }, ticks: { maxTicksLimit: 5, font: { family: "'Inter', sans-serif", weight: '400' } } } }, false, false, 'Fuente: CEER en base a BCRA y BLS');
        buildC('chartCarrera', [{ label: 'Devaluación (%)', data: m('tc_mayorista_var'), borderColor: C_PRINCIPAL, fill: false, borderWidth: 2.5 }, { label: 'IPC (%)', data: m('ipc_mensual'), borderColor: C_MORADO, fill: false, borderWidth: 2.5 }]);
        buildC('chartIPC', [{ label: 'IPC Interanual', data: m('ipc_interanual'), borderColor: C_PRINCIPAL, fill: false, borderWidth: 2.5 }, { label: 'REM 12m', data: m('rem_interanual'), borderColor: C_MORADO, borderDash: [5, 5], fill: false, borderWidth: 2.5 }]);
        buildC('chartFED', [{ label: 'Tasa FED (EFFR %)', data: m('tasa_fed'), borderColor: C_PRINCIPAL, fill: false, borderWidth: 2.5 }], {}, false, false, 'Fuente: CEER en base a NY Fed');

        buildC('chartAgregados', [{ label: 'M2', data: m('m2'), borderColor: C_MORADO, fill: false, borderWidth: 2.5 }, { label: 'Base Monetaria', data: m('base_monetaria'), borderColor: C_PRINCIPAL, fill: false, borderWidth: 2.5 }]);
        buildC('chartTasas', [{label:'Tasa Política',data:m('tasa_politica_tea'),borderColor:C_PRINCIPAL,fill:false,borderWidth:2.5,yAxisID:'y'},{label:'BADLAR',data:m('badlar_tea'),borderColor:C_INFORMES,fill:false,borderWidth:2.5,yAxisID:'y'},{label:'IPC Interanual',data:m('ipc_interanual'),backgroundColor:'rgba(68,4,197,0.7)',type:'bar',yAxisID:'y',borderRadius:4}], {});
        buildC('chartDiario', [{ label: 'BADLAR', data: d('badlar_tea'), borderColor: C_PRINCIPAL, fill: false, borderWidth: 2 }, { label: 'TAMAR', data: d('tamar_tea'), borderColor: C_MORADO, fill: false, borderWidth: 2 }]);

        initGen();
        filtrarTexto();

        const loader = document.getElementById('loader');
        loader.style.opacity = '0';
        setTimeout(() => loader.style.display = 'none', 500);

    } catch (error) {
        console.error("Error crítico al cargar el Dashboard:", error);
        document.getElementById('spinnerIcon').style.display = 'none';
        document.getElementById('loader-text').style.display = 'none';
        document.getElementById('errorBox').style.display = 'block';
    }
}

// Auto-detectar dispositivo móvil
document.addEventListener('DOMContentLoaded', () => {
    if (window.innerWidth <= 768) {
        document.body.classList.add('mobile-mode');
    }
    load();
});
