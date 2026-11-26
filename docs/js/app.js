import { renderMetrics, renderTriangle, renderFactors, renderCompareTable } from './render.js';
import { renderDevPlot, renderComparePlot } from './charts.js';

let INDEX = [];
let RESULTS = [];
let currentResult = null;
let triangleMode = 'observed';

async function init() {
  const [indexRes, resultsRes] = await Promise.all([
    fetch('data/index.json').then(r => r.json()),
    fetch('data/results.json').then(r => r.json()),
  ]);
  INDEX = indexRes;
  RESULTS = resultsRes;

  const lobs = [...new Set(INDEX.map(i => i.lob_name))].sort();
  const lobSelect = document.getElementById('lob-select');
  const lobLabels = {};
  INDEX.forEach(i => lobLabels[i.lob_name] = i.lob_label);

  lobs.forEach(l => {
    const opt = document.createElement('option');
    opt.value = l;
    opt.textContent = lobLabels[l];
    lobSelect.appendChild(opt);
  });

  if (lobs.includes('pp_auto')) lobSelect.value = 'pp_auto';

  lobSelect.addEventListener('change', () => updateCarriers());
  document.getElementById('carrier-select').addEventListener('change', () => render());

  document.getElementById('tri-toggle').addEventListener('click', (e) => {
    const btn = e.target.closest('.toggle-btn');
    if (!btn) return;
    document.querySelectorAll('#tri-toggle .toggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    triangleMode = btn.dataset.mode;
    document.getElementById('tri-legend').style.display = triangleMode === 'observed' ? 'none' : 'flex';
    renderTriangle(currentResult, triangleMode);
  });

  updateCarriers('1767');
}

function updateCarriers(defaultGrcode) {
  const lob = document.getElementById('lob-select').value;
  const carriers = INDEX.filter(i => i.lob_name === lob)
    .sort((a, b) => a.grname.localeCompare(b.grname));

  const sel = document.getElementById('carrier-select');
  sel.innerHTML = '';
  carriers.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.grcode;
    opt.textContent = c.grname;
    sel.appendChild(opt);
  });

  if (defaultGrcode && carriers.some(c => String(c.grcode) === String(defaultGrcode))) {
    sel.value = defaultGrcode;
  } else {
    const largest = carriers.reduce((a, b) => Math.abs(a.cl_ibnr) > Math.abs(b.cl_ibnr) ? a : b, carriers[0]);
    if (largest) sel.value = largest.grcode;
  }

  render();
}

function render() {
  const lob = document.getElementById('lob-select').value;
  const grcode = parseInt(document.getElementById('carrier-select').value);

  currentResult = RESULTS.find(r => r.lob_name === lob && r.grcode === grcode);
  if (!currentResult) return;

  renderMetrics(currentResult);
  renderTriangle(currentResult, triangleMode);
  renderFactors(currentResult);
  renderDevPlot(currentResult);
  renderComparePlot(currentResult);
  renderCompareTable(currentResult);
}

init();
