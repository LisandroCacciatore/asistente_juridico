// Verificación numérica de rail(): extrae STAGES/REACHED/nextStepsFor/rail/esc
// del dashboard real y comprueba el HTML que produce para cada estado.
const fs = require('fs');
const path = require('path');
const h = fs.readFileSync(path.join(__dirname, '..', 'asistente_juridico.html'), 'utf8').replace(/\r\n/g, '\n');

function slice(s, e) {
  const a = h.indexOf(s), b = h.indexOf(e, a);
  if (a < 0 || b < 0) throw new Error('marcador no encontrado: ' + (a < 0 ? s : e));
  return h.slice(a, b + e.length);
}

const code = [
  slice('/* ---------------- Riel de estados con avance', '\n  return h;\n}'),
  slice('function esc(v){', '})[ch]);\n}'),
  'module.exports={rail,STAGES,REACHED,nextStepsFor};'
].join('\n');

const mod = { exports: {} };
new Function('module', 'exports', code)(mod, mod.exports);
const { rail } = mod.exports;

const casos = [
  // estado,      nodos, hechos, idxCur, riel%, barra%
  ['generada',     6,     2,     2,      20,    33.33],
  ['firmada',      6,     4,     4,      60,    66.67],
  ['presentada',   6,     6,    -1,     100,   100],
];

let ok = true;
for (const [estado, nNodos, nDone, idxCur, posPct, donePct] of casos) {
  const out = rail(estado);
  const nodes = out.match(/class="node[^"]*"/g) || [];
  const done = nodes.filter(x => x.includes('done')).length;
  const cur = nodes.findIndex(x => x.includes('current'));
  const tf = parseFloat((out.match(/track[^>]*><div class="fill" style="width:([\d.]+)%/) || [])[1]);
  const bf = parseFloat((out.match(/bar"><div class="fill" style="width:([\d.]+)%/) || [])[1]);
  const pct = (out.match(/class="pct">([^<]+)</) || [])[1];
  const pasos = (out.match(/class="ns-item/g) || []).length;

  const checks = [
    ['nodos', nodes.length, nNodos],
    ['hechos', done, nDone],
    ['actual(idx)', cur, idxCur],
    ['riel%', Math.round(tf), Math.round(posPct)],
    ['barra%', Math.round(bf), Math.round(donePct)],
    ['texto avance', pct, nDone + '/' + nNodos],
  ];
  const fallos = checks.filter(([, got, exp]) => got !== exp);
  ok = ok && fallos.length === 0;
  console.log(
    estado.padEnd(11),
    'nodos:' + nodes.length, 'hechos:' + done, 'actual:' + cur,
    'riel:' + Math.round(tf) + '%', 'barra:' + Math.round(bf) + '%',
    'pct:' + pct, 'pasos:' + pasos,
    fallos.length ? '  ← FALLA: ' + JSON.stringify(fallos) : '  ✓'
  );
}
console.log(ok ? '\nTODO OK' : '\nHAY FALLAS');
