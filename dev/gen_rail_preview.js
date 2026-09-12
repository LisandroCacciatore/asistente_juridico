// Genera rail_preview.html extrayendo el CSS/JS REALES del dashboard,
// para verificar visualmente el riel corregido sin depender del servidor.
const fs = require('fs');

const src = fs.readFileSync('../asistente_juridico.html', 'utf8').replace(/\r\n/g, '\n');

function slice(startMarker, endMarker) {
  const a = src.indexOf(startMarker);
  if (a < 0) throw new Error('no encontre inicio: ' + startMarker);
  const b = src.indexOf(endMarker, a);
  if (b < 0) throw new Error('no encontre fin: ' + endMarker);
  return src.slice(a, b + endMarker.length);
}

// 1) variables de color
const root = slice(':root{', '}');

// 2) CSS del riel + barra de avance + proximos pasos
const cssRail = slice('/* ---------- Riel de estados ---------- */', '.next-steps .ns-done .ic{color:var(--escudo)}');

// 3) JS: STAGES/REACHED/nextStepsFor/rail
const jsRail = slice('/* ---------------- Riel de estados con avance', '\n  return h;\n}');

// 4) JS: esc()
const jsEsc = slice('function esc(v){', '})[ch]);\n}');

const demo = `<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Riel de estados — preview</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Spectral:wght@500;600&display=swap" rel="stylesheet">
<style>
${root}
  body{font-family:'Inter',system-ui,sans-serif;background:#eef2f7;margin:0;padding:28px;color:var(--ink)}
  h1{font-family:'Spectral',serif;font-size:22px;margin:0 0 4px}
  .lead{font-size:13px;color:var(--muted);margin:0 0 22px}
  .card{background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-bottom:18px}
  .row{padding:18px 20px;border-bottom:1px solid var(--line)}
  .row:last-child{border-bottom:none}
  .caratula{font-size:15.5px;font-weight:600}
  .meta{display:flex;gap:14px;margin-top:6px;font-size:12.5px;color:var(--muted)}
  .cuij{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--ink-2)}
  .who{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--escudo);margin-bottom:8px}
${cssRail}
</style></head>
<body>
  <h1>Riel de estados — verificación</h1>
  <p class="lead">Renderizado con el CSS y el JS reales del dashboard. Tres estados: generada → firmada → presentada.</p>
  <div class="card" id="demo"></div>
<script>
${jsEsc}
${jsRail}

const CASOS = [
  {estado:"generada",   caratula:"GONZALEZ c/ ART EJEMPLO S/ ACCIDENTE LABORAL", cuij:"21-00000001-0"},
  {estado:"firmada",    caratula:"RAMIREZ c/ PROVINCIA DE SANTA FE S/ DAÑOS",    cuij:"21-00000002-0"},
  {estado:"presentada", caratula:"FERNANDEZ c/ COMERCIAL EJEMPLO S/ COBRO DE PESOS", cuij:"21-00000003-0"}
];

document.getElementById("demo").innerHTML = CASOS.map(c=>\`
  <div class="row">
    <div class="who">estado: \${c.estado}</div>
    <div class="caratula">\${esc(c.caratula)}</div>
    <div class="meta"><span class="cuij">CUIJ \${esc(c.cuij)}</span></div>
    \${rail(c.estado)}
  </div>\`).join("");
</script>
</body></html>`;

fs.writeFileSync('rail_preview.html', demo, 'utf8');
console.log('rail_preview.html generado (' + demo.length + ' bytes)');
