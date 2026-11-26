import { fmt } from './utils.js';

export function renderMetrics(currentResult) {
  const t = currentResult.totals;
  document.getElementById('m-latest').textContent = fmt(t.latest_total);
  document.getElementById('m-cl-ult').textContent = fmt(t.cl_ultimate);
  document.getElementById('m-bf-ult').textContent = fmt(t.bf_ultimate);
  document.getElementById('m-cl-ibnr').textContent = fmt(t.cl_ibnr);
  document.getElementById('m-bf-ibnr').textContent = fmt(t.bf_ibnr);
}

export function renderTriangle(currentResult, triangleMode) {
  const observed = currentResult.triangle;
  if (!observed || observed.length === 0) return;

  const triSource = triangleMode === 'cl' ? currentResult.triangle_cl
                  : triangleMode === 'bf' ? currentResult.triangle_bf
                  : observed;

  const lags = Object.keys(observed[0]).filter(k => k !== 'AccidentYear');

  let allVals = [];
  triSource.forEach(r => {
    lags.forEach(l => { if (r[l] !== null) allVals.push(r[l]); });
  });

  const minV = Math.min(...allVals);
  const maxV = Math.max(...allVals);
  const range = maxV - minV || 1;

  const heatClass = (v) => {
    if (v === null) return 'na';
    const pct = (v - minV) / range;
    if (pct < 0.2) return 'heat-1';
    if (pct < 0.4) return 'heat-2';
    if (pct < 0.6) return 'heat-3';
    if (pct < 0.8) return 'heat-4';
    return 'heat-5';
  };

  let html = '<table class="triangle"><thead><tr><th data-col="0">AY</th>';
  lags.forEach((l, ci) => html += `<th data-col="${ci + 1}">${l}</th>`);
  html += '</tr></thead><tbody>';

  triSource.forEach((row, ri) => {
    const obsRow = observed[ri];
    html += `<tr><td data-col="0">${row.AccidentYear}</td>`;
    lags.forEach((l, ci) => {
      const v = row[l];
      const isProjected = triangleMode !== 'observed' && obsRow[l] === null && v !== null;
      const cls = [heatClass(v)];
      if (isProjected) cls.push('projected');
      html += `<td data-col="${ci + 1}" class="${cls.join(' ')}">${v === null ? '' : fmt(v)}</td>`;
    });
    html += '</tr>';
  });

  html += '</tbody></table>';
  document.getElementById('triangle-table').innerHTML = html;

  const table = document.querySelector('.triangle');
  if (!table) return;

  table.addEventListener('mouseover', (e) => {
    const td = e.target.closest('td');
    if (!td) return;
    const col = td.dataset.col;
    const row = td.parentElement;

    table.querySelectorAll('td, th').forEach(c => {
      c.classList.remove('highlight-cell', 'highlight-row', 'highlight-col');
    });

    row.querySelectorAll('td').forEach(c => c.classList.add('highlight-row'));
    table.querySelectorAll(`[data-col="${col}"]`).forEach(c => c.classList.add('highlight-col'));
    td.classList.remove('highlight-row', 'highlight-col');
    td.classList.add('highlight-cell');
  });

  table.addEventListener('mouseleave', () => {
    table.querySelectorAll('td, th').forEach(c => {
      c.classList.remove('highlight-cell', 'highlight-row', 'highlight-col');
    });
  });
}

export function renderFactors(currentResult) {
  const factors = currentResult.selected_factors;
  const container = document.getElementById('factors-row');
  container.innerHTML = '';

  Object.entries(factors).forEach(([period, value]) => {
    const pill = document.createElement('div');
    pill.className = 'factor-pill';
    pill.innerHTML = `<span class="period">${period}</span><span class="value">${value.toFixed(4)}</span>`;
    container.appendChild(pill);
  });
}

export function renderCompareTable(currentResult) {
  const comp = currentResult.comparison;
  let html = `<table class="compare">
    <thead><tr>
      <th>AY</th><th>Latest paid</th><th>CL ultimate</th><th>BF ultimate</th>
      <th>CL IBNR</th><th>BF IBNR</th><th>Difference</th>
    </tr></thead><tbody>`;

  let totals = { latest: 0, cl_ult: 0, bf_ult: 0, cl_ibnr: 0, bf_ibnr: 0, diff: 0 };

  comp.forEach(r => {
    const diff = r.cl_ibnr - r.bf_ibnr;
    totals.latest += r.latest_value || 0;
    totals.cl_ult += r.cl_ultimate || 0;
    totals.bf_ult += r.bf_ultimate || 0;
    totals.cl_ibnr += r.cl_ibnr || 0;
    totals.bf_ibnr += r.bf_ibnr || 0;
    totals.diff += diff || 0;

    html += `<tr>
      <td>${r.accident_year}</td>
      <td>${fmt(r.latest_value)}</td>
      <td>${fmt(r.cl_ultimate)}</td>
      <td>${fmt(r.bf_ultimate)}</td>
      <td>${fmt(r.cl_ibnr)}</td>
      <td>${fmt(r.bf_ibnr)}</td>
      <td>${fmt(diff)}</td>
    </tr>`;
  });

  html += `<tr class="total-row">
    <td>Total</td>
    <td>${fmt(totals.latest)}</td>
    <td>${fmt(totals.cl_ult)}</td>
    <td>${fmt(totals.bf_ult)}</td>
    <td>${fmt(totals.cl_ibnr)}</td>
    <td>${fmt(totals.bf_ibnr)}</td>
    <td>${fmt(totals.diff)}</td>
  </tr>`;

  html += '</tbody></table>';
  document.getElementById('compare-table').innerHTML = html;
}
