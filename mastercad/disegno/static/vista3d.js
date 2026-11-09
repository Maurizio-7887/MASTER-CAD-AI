/* MASTER CAD AI · vista 3D del solido (trascina per ruotare, rotella per lo zoom). Nessuna libreria esterna. */
(function (root) {
  'use strict';
  root.Vista3D = function (canvas) {
    var ctx = canvas.getContext('2d'), tri = [], yaw = -0.7, pitch = 0.65, zoom = 1, drag = null;
    function resize() { var r = canvas.getBoundingClientRect(); canvas.width = Math.max(200, Math.floor(r.width * devicePixelRatio)); canvas.height = Math.max(160, Math.floor(r.height * devicePixelRatio)); draw(); }
    function draw() {
      var w = canvas.width, h = canvas.height; ctx.fillStyle = '#122a40'; ctx.fillRect(0, 0, w, h);
      if (!tri.length) { ctx.fillStyle = '#97bbd1'; ctx.textAlign = 'center'; ctx.font = (13 * devicePixelRatio) + 'px system-ui'; ctx.fillText('ESTRUDI o RIVOLUZIONE per vedere il solido', w / 2, h / 2); return; }
      var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
      tri.forEach(function (f) { f.forEach(function (p) { for (var k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], p[k]); hi[k] = Math.max(hi[k], p[k]); } }); });
      var mid = lo.map(function (x, k) { return (x + hi[k]) / 2; }), span = Math.max(1, hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
      var sc = Math.min(w, h) * .62 * zoom / span, cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
      var pr = function (p) { var x = p[0] - mid[0], y = p[1] - mid[1], z = p[2] - mid[2], rx = x * cy - y * sy, ry = x * sy + y * cy; return [w / 2 + rx * sc, h / 2 - (ry * sp + z * cp) * sc, (ry * cp - z * sp) * sc]; };
      var facce = tri.map(function (f) { var v = f.map(pr); return {v: v, f: f, z: (v[0][2] + v[1][2] + v[2][2]) / 3}; }).sort(function (a, b) { return a.z - b.z; });
      // luce fissa rispetto alla vista: normale vera del triangolo nello spazio della camera
      facce.forEach(function (f) {
        var p = f.v, a = [p[1][0] - p[0][0], p[0][1] - p[1][1], p[1][2] - p[0][2]], b = [p[2][0] - p[0][0], p[0][1] - p[2][1], p[2][2] - p[0][2]];
        var n = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]], l = Math.hypot(n[0], n[1], n[2]) || 1;
        var luce = Math.abs((n[0] * -0.35 + n[1] * 0.55 + n[2] * -0.76) / l);
        var shade = Math.max(.22, Math.min(1, .25 + .75 * luce));
        ctx.fillStyle = 'rgb(' + Math.round(40 + 70 * shade) + ',' + Math.round(100 + 100 * shade) + ',' + Math.round(150 + 85 * shade) + ')';
        ctx.strokeStyle = ctx.fillStyle; ctx.lineWidth = .6;
        ctx.beginPath(); ctx.moveTo(p[0][0], p[0][1]); ctx.lineTo(p[1][0], p[1][1]); ctx.lineTo(p[2][0], p[2][1]); ctx.closePath(); ctx.fill(); ctx.stroke();
      });
    }
    canvas.addEventListener('pointerdown', function (e) { drag = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove', function (e) { if (!drag) return; yaw += (e.clientX - drag[0]) * .012; pitch = Math.max(-1.5, Math.min(1.5, pitch + (e.clientY - drag[1]) * .009)); drag = [e.clientX, e.clientY]; draw(); });
    canvas.addEventListener('pointerup', function () { drag = null; });
    canvas.addEventListener('wheel', function (e) { e.preventDefault(); zoom = Math.max(.2, Math.min(6, zoom * Math.exp(-e.deltaY * .001))); draw(); }, {passive: false});
    new ResizeObserver(resize).observe(canvas);
    return {mostra: function (t) { tri = t || []; zoom = 1; draw(); }};
  };
})(window);
