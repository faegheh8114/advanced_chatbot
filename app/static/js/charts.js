// Saipa Mashayekh 3299 — minimal dependency-free canvas charts for the
// Management Dashboard / Reports pages. No external chart library required.

const CHART_COLORS = ["#2452e8", "#059669", "#d97706", "#dc2626", "#0891b2", "#7c3aed", "#64748b"];

function drawBarChart(canvas, series, opts) {
  opts = opts || {};
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const cssWidth = canvas.clientWidth || 480;
  const cssHeight = canvas.height / (canvas.width / cssWidth) || 220;
  canvas.width = cssWidth * dpr;
  canvas.height = 220 * dpr;
  canvas.style.height = "220px";
  ctx.scale(dpr, dpr);

  const w = cssWidth;
  const h = 220;
  const padding = { top: 16, right: 12, bottom: 34, left: 34 };
  const chartW = w - padding.left - padding.right;
  const chartH = h - padding.top - padding.bottom;

  ctx.clearRect(0, 0, w, h);

  const maxValue = Math.max(1, ...series.map((s) => s.value));
  const barGap = 10;
  const barWidth = Math.max(6, chartW / series.length - barGap);

  ctx.strokeStyle = "#e2e8f0";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padding.top + (chartH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(w - padding.right, y);
    ctx.stroke();
    ctx.fillStyle = "#94a3b8";
    ctx.font = "10px -apple-system, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(Math.round(maxValue - (maxValue / 4) * i), padding.left - 6, y + 3);
  }

  series.forEach((s, i) => {
    const barH = (s.value / maxValue) * chartH;
    const x = padding.left + i * (barWidth + barGap) + barGap / 2;
    const y = padding.top + chartH - barH;
    ctx.fillStyle = opts.color || CHART_COLORS[0];
    roundedRect(ctx, x, y, barWidth, barH, 4);
    ctx.fill();

    ctx.fillStyle = "#64748b";
    ctx.font = "10px -apple-system, sans-serif";
    ctx.textAlign = "center";
    const label = s.label.length > 10 ? s.label.slice(0, 9) + "…" : s.label;
    ctx.fillText(label, x + barWidth / 2, h - padding.bottom + 14);
  });
}

function drawLineChart(canvas, series, opts) {
  opts = opts || {};
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const cssWidth = canvas.clientWidth || 480;
  canvas.width = cssWidth * dpr;
  canvas.height = 220 * dpr;
  canvas.style.height = "220px";
  ctx.scale(dpr, dpr);

  const w = cssWidth;
  const h = 220;
  const padding = { top: 16, right: 16, bottom: 30, left: 34 };
  const chartW = w - padding.left - padding.right;
  const chartH = h - padding.top - padding.bottom;

  ctx.clearRect(0, 0, w, h);

  const maxValue = Math.max(1, ...series.map((s) => s.value));
  const stepX = series.length > 1 ? chartW / (series.length - 1) : 0;

  ctx.strokeStyle = "#e2e8f0";
  for (let i = 0; i <= 4; i++) {
    const y = padding.top + (chartH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(w - padding.right, y);
    ctx.stroke();
    ctx.fillStyle = "#94a3b8";
    ctx.font = "10px -apple-system, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(Math.round(maxValue - (maxValue / 4) * i), padding.left - 6, y + 3);
  }

  const points = series.map((s, i) => ({
    x: padding.left + i * stepX,
    y: padding.top + chartH - (s.value / maxValue) * chartH,
  }));

  ctx.beginPath();
  ctx.moveTo(points[0].x, padding.top + chartH);
  points.forEach((p) => ctx.lineTo(p.x, p.y));
  ctx.lineTo(points[points.length - 1].x, padding.top + chartH);
  ctx.closePath();
  ctx.fillStyle = "rgba(36, 82, 232, 0.08)";
  ctx.fill();

  ctx.beginPath();
  points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.strokeStyle = opts.color || CHART_COLORS[0];
  ctx.lineWidth = 2;
  ctx.stroke();

  points.forEach((p) => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = opts.color || CHART_COLORS[0];
    ctx.fill();
  });

  ctx.fillStyle = "#64748b";
  ctx.font = "10px -apple-system, sans-serif";
  ctx.textAlign = "center";
  series.forEach((s, i) => {
    if (series.length > 10 && i % 2 !== 0) return;
    ctx.fillText(s.label, points[i].x, h - padding.bottom + 14);
  });
}

function drawDonutChart(canvas, series) {
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const size = Math.min(canvas.clientWidth || 220, 220);
  canvas.width = size * dpr;
  canvas.height = size * dpr;
  canvas.style.height = size + "px";
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, size, size);

  const total = series.reduce((sum, s) => sum + s.value, 0) || 1;
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = size / 2 - 6;
  const rInner = rOuter * 0.62;
  let start = -Math.PI / 2;

  series.forEach((s, i) => {
    const angle = (s.value / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, rOuter, start, start + angle);
    ctx.closePath();
    ctx.fillStyle = CHART_COLORS[i % CHART_COLORS.length];
    ctx.fill();
    start += angle;
  });

  ctx.globalCompositeOperation = "destination-out";
  ctx.beginPath();
  ctx.arc(cx, cy, rInner, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";

  ctx.fillStyle = "#0f172a";
  ctx.font = "bold 16px -apple-system, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(total, cx, cy + 5);
}

function roundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}
