/* Episodes (ticket 45). Two modes, set by the page's data:
   "list" — the Events page's second view: the confirmed episodes in a list, each a numbered ring on the
            map in its two claimants' colours, larger for more events; a pair filter.
   "one"  — one episode: the map shows where (one marker per place, its ring split by claimant), the strip
            below shows when (one row per claimant), and Play lights the events in order.
   MapLibre draws the map; the markers are plain elements, so they show even when the tiles cannot load. */
(function () {
  "use strict";
  var src = document.getElementById("epdata");
  if (!src) return;
  var DATA = JSON.parse(src.textContent);
  var NAMES = DATA.names, PROSE = DATA.prose || NAMES;
  var $ = function (id) { return document.getElementById(id); };
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var SVGNS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs) { var e = document.createElementNS(SVGNS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); return e; }
  function cvar(code) { return "var(--" + code.toLowerCase() + ")"; }
  function day(iso) { var p = iso.split("-"); return Date.UTC(+p[0], (+p[1] || 1) - 1, +p[2] || 1); }

  var head = document.querySelector(".navband");
  function sizeTracker() { if (head) document.documentElement.style.setProperty("--head-h", head.offsetHeight + "px"); }
  sizeTracker();
  window.addEventListener("resize", sizeTracker);

  // ---- the map ------------------------------------------------------------------------------------------
  var map = null;
  function geoBounds(gj) {
    var w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
    function walk(c) {
      if (typeof c[0] === "number") { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]); }
      else c.forEach(walk);
    }
    gj.features.forEach(function (f) { walk(f.geometry.coordinates); });
    return [[w, s], [e, n]];
  }
  function makeMap(bounds, maxZoom) {
    if (typeof maplibregl === "undefined" || !$("map")) return null;
    var styleEl = $("mapstyle");
    var STYLE = styleEl ? JSON.parse(styleEl.textContent) : { version: 8, sources: {}, layers: [] };
    var m;
    try {
      m = new maplibregl.Map({ container: "map", style: STYLE, bounds: bounds, fitBoundsOptions: { padding: 60, maxZoom: maxZoom },
        minZoom: 3.5, maxZoom: 12, cooperativeGestures: true, attributionControl: false, dragRotate: false, pitchWithRotate: false });
    } catch (err) { return null; }   // no WebGL: the list and the strip still work
    m.touchZoomRotate.disableRotation();
    // the stage settles its size after the map is made (the strip, narrow screens): follow it
    if (typeof ResizeObserver !== "undefined") new ResizeObserver(function () { m.resize(); }).observe($("map"));
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    m.addControl(new maplibregl.AttributionControl({ compact: false }));
    m.on("error", function (e) {
      var msg = e && e.error ? String(e.error.message || e.error) : "";
      if (!/tile|sprite|glyph|font|fetch|network|load|status|json|response/i.test(msg)) console.warn("map: " + msg);
    });
    return m;
  }
  function marker(el, lon, lat) {
    if (!map) return null;
    return new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat([lon, lat]).addTo(map);
  }

  if (DATA.mode === "list") listMode(); else oneMode();

  // ---- the list -----------------------------------------------------------------------------------------
  function listMode() {
    var EPS = DATA.episodes;
    var placed = EPS.filter(function (x) { return x.lat !== null; });
    var bounds = placed.length ? placed.reduce(function (b, x) {
      return [[Math.min(b[0][0], x.lon), Math.min(b[0][1], x.lat)], [Math.max(b[1][0], x.lon), Math.max(b[1][1], x.lat)]];
    }, [[Infinity, Infinity], [-Infinity, -Infinity]]) : geoBounds(DATA.subregions);
    map = makeMap(bounds, 7);
    var maxN = Math.max.apply(null, EPS.map(function (x) { return x.n; }).concat([1]));
    var rings = {}, groups = [];
    EPS.forEach(function (x) {
      // the card's strip: the events in time, in their claimant's colour
      var li = document.querySelector('#ep-list li[data-k="' + x.k + '"]');
      var mini = li && li.querySelector(".ep-mini");
      if (mini) {
        var t0 = day(x.first), t1 = Math.max(day(x.last), t0 + 1), s = svg("svg", { viewBox: "0 0 220 20", width: "100%", height: 20 });
        s.appendChild(svg("line", { x1: 4, y1: 10, x2: 216, y2: 10, stroke: "var(--rule)" }));
        x.dots.forEach(function (d) { s.appendChild(svg("circle", { cx: (4 + 212 * (day(d[0]) - t0) / (t1 - t0)).toFixed(1), cy: d[1] === x.a ? 6 : 14, r: 3.5, fill: cvar(d[1]) })); });
        mini.appendChild(s);
      }
      if (x.lat === null) return;
      var a = document.createElement("a");
      a.className = "ep-ring"; a.href = "episodes/" + x.slug + ".html";
      a.setAttribute("aria-label", x.k + ". " + x.name + ", " + x.pair + ", " + x.n + " events");
      var size = Math.round(26 + 22 * Math.sqrt(x.n / maxN));
      a.style.cssText = "--a:" + cvar(x.a) + ";--b:" + cvar(x.b) + ";width:" + size + "px;height:" + size + "px";
      a.textContent = x.k;
      a.addEventListener("mouseenter", function () { hover(x.k, true); });
      a.addEventListener("mouseleave", function () { hover(x.k, false); });
      var mk = marker(a, x.lon, x.lat);
      if (mk) groupOf(x).push({ mk: mk, size: size });
      rings[x.k] = a;
      if (li) {
        li.addEventListener("mouseenter", function () { hover(x.k, true); });
        li.addEventListener("mouseleave", function () { hover(x.k, false); });
      }
    });
    // episodes at the same feature (Scarborough Shoal in 2016, 2023 and 2025) would sit on one another: they
    // stand side by side in a row, oldest on the left, centred on the place
    function groupOf(x) {
      var g = groups.filter(function (G) { return Math.abs(G.lat - x.lat) < 0.25 && Math.abs(G.lon - x.lon) < 0.25; })[0];
      if (!g) { g = { lat: x.lat, lon: x.lon, items: [] }; groups.push(g); }
      return g.items;
    }
    function spread() {
      groups.forEach(function (G) {
        var items = G.items.slice().reverse(), total = items.reduce(function (t, it) { return t + it.size + 4; }, -4), left = -total / 2;
        items.forEach(function (it) { it.mk.setOffset([left + it.size / 2, 0]); left += it.size + 4; });
      });
    }
    function hover(k, on) {
      if (rings[k]) rings[k].classList.toggle("is-hot", on);
      var li = document.querySelector('#ep-list li[data-k="' + k + '"]');
      if (li) li.classList.toggle("is-hot", on);
    }
    spread();
    var sel = $("ep-pair");
    function applyPair() {
      var v = sel ? sel.value : "";
      EPS.forEach(function (x) {
        var show = !v || x.pair_slug === v;
        var li = document.querySelector('#ep-list li[data-k="' + x.k + '"]');
        if (li) li.hidden = !show;
        if (rings[x.k]) rings[x.k].hidden = !show;
      });
      var h = v ? "#pair-" + v : "";
      if (location.hash !== h) history.replaceState(null, "", h || location.pathname + location.search);
    }
    if (sel) {
      var m = /^#pair-([a-z-]+)$/.exec(location.hash);
      if (m && sel.querySelector('option[value="' + m[1] + '"]')) sel.value = m[1];
      sel.addEventListener("change", applyPair);
      applyPair();
    }
  }

  // ---- one episode --------------------------------------------------------------------------------------
  function oneMode() {
    var EP = DATA.episode, EVS = EP.events, PL = EP.places;
    var bounds = PL.length ? PL.reduce(function (b, p) {
      return [[Math.min(b[0][0], p.lon), Math.min(b[0][1], p.lat)], [Math.max(b[1][0], p.lon), Math.max(b[1][1], p.lat)]];
    }, [[Infinity, Infinity], [-Infinity, -Infinity]]) : geoBounds(DATA.subregions);
    map = makeMap(bounds, 8);
    var maxN = Math.max.apply(null, PL.map(function (p) { return p.n[EP.a] + p.n[EP.b]; }).concat([1]));
    var pins = PL.map(function (p, i) {
      var n = p.n[EP.a] + p.n[EP.b], share = Math.round(100 * p.n[EP.a] / n);
      var el = document.createElement("div");
      el.className = "ep-pin";
      var size = Math.round(34 + 18 * Math.sqrt(n / maxN));
      el.style.cssText = "--a:" + cvar(EP.a) + ";--b:" + cvar(EP.b) + ";--share:" + share + "%;--size:" + size + "px";
      var ring = document.createElement("span"); ring.className = "ep-pin-ring"; ring.textContent = n;
      var lab = document.createElement("span"); lab.className = "ep-pin-label";
      var nm = document.createElement("b"); nm.textContent = p.name || "Unnamed place";
      var by = document.createElement("span");
      by.textContent = [[EP.a, p.n[EP.a]], [EP.b, p.n[EP.b]]].filter(function (t) { return t[1]; }).map(function (t) { return t[1] + " by " + PROSE[t[0]]; }).join(" · ");
      lab.appendChild(nm); lab.appendChild(by);
      el.appendChild(ring); el.appendChild(lab);
      el.setAttribute("role", "img");
      el.setAttribute("aria-label", (p.name || "A place") + ": " + by.textContent);
      marker(el, p.lon, p.lat);
      return el;
    });

    // the strip: when, one row per claimant, numbered as in the list
    var host = $("ep-strip"), W, H = 214, X0 = 110, X1, ROW_A = 60, AXIS = 110, ROW_B = 160, R = 11;
    var cursor, dots = [];
    var t0 = day(EVS[0].d), t1 = day(EVS[EVS.length - 1].d);
    var pad = Math.max((t1 - t0) * 0.04, 86400000 * 10); t0 -= pad; t1 += pad;
    function X(iso) { return X0 + (X1 - X0) * (day(iso) - t0) / (t1 - t0); }
    function drawStrip() {
    W = Math.max(host.clientWidth || 880, 300); X0 = W < 600 ? 90 : 110; X1 = W - (W < 600 ? 14 : 24);
    host.textContent = "";
    var s = svg("svg", { viewBox: "0 0 " + W + " " + H, width: "100%", height: H, preserveAspectRatio: "xMinYMid meet" });
    [[EP.a, ROW_A], [EP.b, ROW_B]].forEach(function (r) {
      var t = svg("text", { x: 16, y: r[1] + 4, "font-size": 12, "font-weight": 600, fill: cvar(r[0]) }); t.textContent = NAMES[r[0]]; s.appendChild(t);
      s.appendChild(svg("line", { x1: X0, y1: r[1], x2: X1, y2: r[1], stroke: "var(--rule)", "stroke-width": 1 }));
    });
    s.appendChild(svg("line", { x1: X0, y1: AXIS, x2: X1, y2: AXIS, stroke: "var(--rule-strong)", "stroke-width": 1 }));
    // ticks: months for a short episode, years for a long one
    var a0 = new Date(t0), months = (t1 - t0) / (86400000 * 30.4);
    var per = (X1 - X0) / Math.max(months, 1), step = per >= 40 ? 1 : per >= 14 ? 3 : 12;   // a label needs about 40 px
    var y = a0.getUTCFullYear(), mo = a0.getUTCMonth() + 1;
    if (step === 12) { y += 1; mo = 0; } else { mo = Math.ceil(mo / step) * step; }
    for (var guard = 0; guard < 80; guard++) {
      var tt = Date.UTC(y, mo, 1); if (tt > t1) break;
      if (tt >= t0) {
        var x = X0 + (X1 - X0) * (tt - t0) / (t1 - t0);
        s.appendChild(svg("line", { x1: x, y1: AXIS - 5, x2: x, y2: AXIS + 5, stroke: "var(--rule-strong)" }));
        var lab = svg("text", { x: x + 3, y: AXIS + 4, "font-size": 11, fill: "var(--muted)", stroke: "var(--surface)", "stroke-width": 4, "paint-order": "stroke" });
        lab.textContent = step === 12 ? String(y) : (mo === 0 || step > 1 ? MONTHS[mo] + " " + String(y).slice(2) : MONTHS[mo]);
        s.appendChild(lab);
      }
      mo += step; if (mo > 11) { y += Math.floor(mo / 12); mo = mo % 12; }
    }
    cursor = svg("line", { x1: -10, y1: 14, x2: -10, y2: H - 8, stroke: "var(--ink)", "stroke-width": 1.5 });
    s.appendChild(cursor);
    // events a few days apart stack outward from their row rather than overlap
    var levels = {};
    dots = EVS.map(function (e, i) {
      var top = e.c === EP.a, row = top ? ROW_A : ROW_B, x = X(e.d), k = 0;
      var used = levels[e.c] || (levels[e.c] = []);
      while (used.some(function (u) { return u[1] === k && Math.abs(u[0] - x) < 2 * R + 1; }) && k < 2) k++;
      used.push([x, k]);
      var cy = row + (top ? -1 : 1) * k * (2 * R + 1);
      var g = svg("g", { "class": "ep-dot", "data-i": i, tabindex: -1 });
      g.appendChild(svg("line", { x1: x, y1: top ? AXIS - 6 : AXIS + 6, x2: x, y2: cy, stroke: "var(--rule-strong)", "stroke-width": 1 }));
      g.appendChild(svg("circle", { cx: x, cy: cy, r: R, fill: cvar(e.c), stroke: "var(--surface)", "stroke-width": 2 }));
      var t = svg("text", { x: x, y: cy + 4, "text-anchor": "middle", "font-size": 11, "font-weight": 600, fill: "#ffffff" }); t.textContent = i + 1; g.appendChild(t);
      var tip = svg("title", {}); tip.textContent = (i + 1) + ". " + e.dl + " · " + NAMES[e.c] + " · " + e.tl; g.appendChild(tip);
      g.addEventListener("click", function () { stop(); show(i, true); });
      s.appendChild(g);
      return { g: g, x: x };
    });
    host.appendChild(s);
    }
    drawStrip();
    var lastW = W, rt = null;
    window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if (Math.abs((host.clientWidth || 880) - lastW) > 8) { drawStrip(); lastW = W; show(cur, false); } }, 150); });

    var steps = Array.prototype.slice.call(document.querySelectorAll("#ep-steps .ep-step"));
    var status = $("ep-strip-status"), playBtn = $("ep-play");
    var cur = -1, timer = null;
    function show(i, focusList) {
      cur = i;
      dots.forEach(function (d, k) { d.g.style.opacity = i < 0 || k <= i ? 1 : 0.3; });
      steps.forEach(function (li, k) { li.classList.toggle("is-current", k === i); li.classList.toggle("is-later", i >= 0 && k > i); });
      pins.forEach(function (p, k) { p.classList.toggle("is-current", i >= 0 && EVS[i].p === k); });
      if (i < 0) { cursor.setAttribute("x1", -10); cursor.setAttribute("x2", -10); status.textContent = ""; return; }
      cursor.setAttribute("x1", dots[i].x); cursor.setAttribute("x2", dots[i].x);
      status.textContent = "Event " + (i + 1) + " of " + EVS.length + ": " + EVS[i].dl + ", " + NAMES[EVS[i].c];
      if (focusList && steps[i]) {
        var side = steps[i].closest(".side"), r = steps[i].getBoundingClientRect(), b = side.getBoundingClientRect();
        if (r.top < b.top + 40 || r.bottom > b.bottom - 8) side.scrollTo({ top: side.scrollTop + r.top - b.top - b.height / 3, behavior: "smooth" });
      }
    }
    function stop() { if (timer) { clearInterval(timer); timer = null; } playBtn.setAttribute("aria-pressed", "false"); playBtn.textContent = "▶ Play the episode"; }
    playBtn.addEventListener("click", function () {
      if (timer) { stop(); return; }
      playBtn.setAttribute("aria-pressed", "true"); playBtn.textContent = "❚❚ Pause";
      if (cur >= EVS.length - 1) cur = -1;
      show(cur + 1, true);
      timer = setInterval(function () {
        if (cur >= EVS.length - 1) { stop(); return; }
        show(cur + 1, true);
      }, 1400);
    });
    Array.prototype.forEach.call(document.querySelectorAll("#ep-steps .ep-num"), function (b) {
      b.addEventListener("click", function () { stop(); var i = +b.getAttribute("data-i"); show(cur === i ? -1 : i, false); });
    });
  }
})();
