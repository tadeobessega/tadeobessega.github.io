/* ============================================================
   CER — cliente de datos
   Sitio 100% estático (GitHub Pages). Los datos vienen del
   Web App de Google Apps Script del equipo.
   ============================================================ */
(function (global) {
  'use strict';

  // Web App de Apps Script (lectura + escritura del panel).
  var API = 'https://script.google.com/macros/s/AKfycbz0a0VXQPcGS41kWw0-77v51ddlxdTbN0NDhkToZeyMjJlwsleF8yoKkudhcee7sgXv/exec';
  global.CER_API = API;

  function apiGet(action, params) {
    var qs = new URLSearchParams(Object.assign({ action: action }, params || {}));
    return fetch(API + '?' + qs.toString())
      .then(function (r) { return r.text(); })
      .then(function (t) {
        var d;
        try { d = JSON.parse(t); }
        catch (e) { throw new Error('El servidor no respondió JSON.'); }
        if (!d || d.success === false) throw new Error((d && d.error) || 'Error del servidor');
        return d;
      });
  }

  function byFechaDesc(a, b) {
    return new Date(b.fecha || b.created_at || 0) - new Date(a.fecha || a.created_at || 0);
  }

  function getReports(centro) {
    return apiGet('getReports', { centro: centro || 'all' })
      .then(function (d) { return (d.reports || []).slice().sort(byFechaDesc); });
  }
  function getReportById(id) { return apiGet('getReport', { id: id }).then(function (d) { return d.report || null; }); }
  function getFeatured()     { return apiGet('getFeatured').then(function (d) { return d.reports || []; }); }
  function getMiembros(c)    { return apiGet('getMiembros', { centro: c || 'all' }).then(function (d) { return d.miembros || []; }); }
  function getConfig(key)    { return apiGet('getConfig', { key: key }).then(function (d) { return d.value || ''; }); }
  function getUsers()        { return apiGet('getUsers').then(function (d) { return d.users || []; }); }
  function getNotes(only)    { return apiGet('getNotes', { soloAprobadas: only ? 'true' : 'false' }).then(function (d) { return d.notes || []; }); }

  global.CERData = {
    api: API,
    getReports: getReports,
    getReportById: getReportById,
    getFeatured: getFeatured,
    getMiembros: getMiembros,
    getConfig: getConfig,
    getUsers: getUsers,
    getNotes: getNotes
  };
})(window);
