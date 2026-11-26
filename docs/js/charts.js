export function renderDevPlot(currentResult) {
  const tri = currentResult.triangle;
  if (!tri || tri.length === 0) return;

  const lags = Object.keys(tri[0]).filter(k => k !== 'AccidentYear').map(Number);
  const totalRows = tri.length;

  const palette = [
    '#2D5A27', '#2B5EA7', '#C44D2B', '#7B5EA7',
    '#B8860B', '#1B7A6E', '#A0522D', '#4A708B',
    '#8B4789', '#5F7A3B',
  ];

  const traces = tri.map((row, i) => {
    const ay = row.AccidentYear;
    const validLags = [];
    const validVals = [];
    lags.forEach(l => {
      const v = row[String(l)];
      if (v !== null) { validLags.push(l); validVals.push(v); }
    });

    const isRecent = i >= totalRows - 3;
    const opacity = isRecent ? 1.0 : 0.2 + (i / totalRows) * 0.4;
    const color = palette[i % palette.length];

    return {
      x: validLags,
      y: validVals,
      name: String(ay),
      type: 'scatter',
      mode: isRecent ? 'lines+markers' : 'lines',
      marker: { size: isRecent ? 5 : 3, color: color, opacity: opacity },
      line: { width: isRecent ? 2.5 : 1.2, color: color },
      opacity: opacity,
    };
  });

  const layout = {
    margin: { t: 10, r: 20, b: 40, l: 60 },
    xaxis: { title: 'Development lag', dtick: 1, gridcolor: '#F0EFEB', zerolinecolor: '#E8E7E3' },
    yaxis: { title: 'Cumulative paid loss', gridcolor: '#F0EFEB', zerolinecolor: '#E8E7E3' },
    legend: { font: { size: 10 }, orientation: 'h', y: -0.25 },
    font: { family: 'DM Sans', size: 12 },
    plot_bgcolor: 'rgba(0,0,0,0)',
    paper_bgcolor: 'rgba(0,0,0,0)',
    height: 300,
    hovermode: 'x unified',
  };

  Plotly.newPlot('dev-plot', traces, layout, { responsive: true, displayModeBar: false });
}

export function renderComparePlot(currentResult) {
  const comp = currentResult.comparison;
  const ays = comp.map(r => String(r.accident_year));

  const traces = [];

  comp.forEach((r, i) => {
    traces.push({
      x: [r.cl_ibnr, r.bf_ibnr],
      y: [ays[i], ays[i]],
      mode: 'lines',
      line: { color: '#D4D3CF', width: 2 },
      showlegend: false,
      hoverinfo: 'skip',
    });
  });

  traces.push({
    x: comp.map(r => r.cl_ibnr),
    y: ays,
    name: 'CL IBNR',
    mode: 'markers',
    marker: { color: '#2D5A27', size: 9, symbol: 'circle' },
    hovertemplate: 'CL IBNR: %{x:,.0f}<extra>%{y}</extra>',
  });

  traces.push({
    x: comp.map(r => r.bf_ibnr),
    y: ays,
    name: 'BF IBNR',
    mode: 'markers',
    marker: { color: '#2B5EA7', size: 9, symbol: 'diamond' },
    hovertemplate: 'BF IBNR: %{x:,.0f}<extra>%{y}</extra>',
  });

  const layout = {
    margin: { t: 10, r: 20, b: 40, l: 50 },
    xaxis: { title: 'IBNR reserve', gridcolor: '#F0EFEB', zerolinecolor: '#E8E7E3' },
    yaxis: { title: '', autorange: 'reversed', gridcolor: '#F0EFEB' },
    legend: { font: { size: 10 }, orientation: 'h', y: -0.2 },
    font: { family: 'DM Sans', size: 12 },
    plot_bgcolor: 'rgba(0,0,0,0)',
    paper_bgcolor: 'rgba(0,0,0,0)',
    height: 300,
    hovermode: 'closest',
  };

  Plotly.newPlot('compare-plot', traces, layout, { responsive: true, displayModeBar: false });
}
