/* The assertiveness map (ticket 27): the ten sub-regions shaded on one ramp by the type-weighted moves of a
   five-year window (declarative 1, demonstrative 2, coercive 3, force 4) or of the build-up since the first
   year, each with its number of moves and, for the window, an arrow when its score rose or fell against
   the five years before. The scale is fixed across every window for the current selection, so a darker
   shade always means more, or harsher, moves. Zoomed in (or a sub-region chosen) the reefs, shoals and
   islands the moves name appear. The scores are computed here from the moves, so the filters (types,
   claimant, directed at) and the weighting switch can recombine them; web.build.window_scores is the
   reference the tests hold this to. Below the map: a timeline, the slider, the filters, decade maps, a
   link to the view (#y2015-c-cn-at-p-t-cf-l-md-s6-f-scarborough-shoal). */
(function () {
  "use strict";
  var src = document.getElementById("mapdata");
  if (!src || typeof maplibregl === "undefined" || !document.getElementById("amap")) return;
  var DATA = JSON.parse(src.textContent);
  var A = DATA.assert;
  if (!A) return;
  var NAMES = DATA.names, SR_NAMES = DATA.subregion_names, TYPE_LABELS = DATA.type_labels, FEATS = A.features || {};
  var TARGETS = A.targets || {};
  var SPAN = A.span, ENDS = A.ends, FIRST = ENDS[0], LAST = ENDS[ENDS.length - 1], FIRST_YEAR = FIRST - SPAN + 1;
  var TYPES = ["declarative", "demonstrative", "coercive", "force"], TYPE_KEY = { declarative: "d", demonstrative: "m", coercive: "c", force: "f" };
  var ZOOM_FEATURES = 5.8, ZOOM_NAMES = 7;   // features from here in; their names from further in
  var CHANGE = 0.2;                          // an arrow when the score moved by a fifth or more
  var root = getComputedStyle(document.documentElement);
  var RAMP = (root.getPropertyValue("--seq") || "#cde2fb, #9ec5f4, #6da7ec, #3987e5, #256abf, #184f95, #0d366b").split(",").map(function (s) { return s.trim(); });
  var TYPE_COLOUR = {};
  TYPES.forEach(function (t) { TYPE_COLOUR[t] = (root.getPropertyValue("--t-" + t) || "#3987e5").trim(); });
  var INK = (root.getPropertyValue("--ink") || "#0c1a2a").trim();

  function $(id) { return document.getElementById(id); }
  var slider = $("amap-year"), label = $("amap-label"), whenEl = $("amap-when"), whoEl = $("amap-who");
  var claimSel = $("amap-claimant"), targetSel = $("amap-target"), sharedBox = $("amap-shared"), detail = $("amap-detail"), playBtn = $("amap-play");
  var canvasBox = $("amap"), decadesBox = $("amap-decades"), timeline = $("amap-timeline");
  var modeInputs = Array.prototype.slice.call(document.querySelectorAll('input[name="amap-mode"]'));
  var typeInputs = Array.prototype.slice.call(document.querySelectorAll('input[name="amap-type"]'));

  // the map opens on the latest five years with moves in them and moves forward as review fills the
  // recent years; the slider still reaches the build year
  var LAST_WITH_MOVES = Math.max.apply(null, A.moves.map(function (m) { return m.y; }).concat([FIRST]));
  var START = Math.min(Math.max(LAST_WITH_MOVES, FIRST), LAST);
  slider.min = String(FIRST);
  slider.max = String(LAST);

  var rampEl = document.querySelector(".amap-ramp");
  if (rampEl) rampEl.style.background = "linear-gradient(to right, " + RAMP.join(", ") + ")";

  var top = document.querySelector(".site-head");
  function sizeStage() { if (top) document.documentElement.style.setProperty("--top-h", top.offsetHeight + "px"); }
  sizeStage();

  var styleEl = $("mapstyle");
  var STYLE = styleEl ? JSON.parse(styleEl.textContent) : { version: 8, sources: {}, layers: [] };
  function geoBounds(features) {
    var w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
    function walk(c) {
      if (typeof c[0] === "number") { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]); }
      else c.forEach(walk);
    }
    features.forEach(function (f) { walk(f.geometry.coordinates); });
    return [[w, s], [e, n]];
  }
  var SEA = geoBounds(DATA.subregions.features);
  var phone = window.matchMedia("(max-width: 700px)");
  function padding() {
    var below = phone.matches ? 0 : (top ? top.offsetHeight : 0);
    return { top: phone.matches ? 90 : 24, bottom: 56 + below, left: 24, right: 24 };
  }
  var state = { end: START, who: "ALL", target: "", types: TYPES.slice(), sel: null, feat: null, mode: "window", lines: [] };
  var LINE_KEY = { maritime: "m", dashline: "d" };
  var lineInputs = ["maritime", "dashline"].map(function (k) { return $("amap-line-" + k); }).filter(Boolean);
  var map = new maplibregl.Map({
    container: "amap", style: STYLE, bounds: SEA, fitBoundsOptions: { padding: padding() },
    minZoom: 3.5, maxZoom: 10, cooperativeGestures: true, attributionControl: false, dragRotate: false, pitchWithRotate: false
  });
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
  window.addEventListener("resize", function () { sizeStage(); map.resize(); if (state.sel === null) map.fitBounds(SEA, { padding: padding(), animate: false }); });
  map.on("error", function (e) {
    var msg = e && e.error ? String(e.error.message || e.error) : "";
    if (!/tile|sprite|glyph|font|fetch|network|load|status|json|response/i.test(msg)) console.warn("amap: " + msg);
  });

  // ---- the measure, from the moves -------------------------------------------------------------
  function passes(m) {
    return (state.who === "ALL" || m.c === state.who) && state.types.indexOf(m.t) >= 0 && (!state.target || (m.g || []).indexOf(state.target) >= 0);
  }
  var cache = { key: null };
  function measure() {   // per-year sums for the current filters and weighting, and the scales
    var shared = !!(sharedBox && sharedBox.checked);
    var key = [state.who, state.target, state.types.join(","), shared].join("|");
    if (cache.key === key) return cache;
    var years = {};
    A.moves.forEach(function (m) {
      if (!passes(m)) return;
      var w = shared && m.sr.length ? m.w / m.sr.length : m.w;
      var row = years[m.y] || (years[m.y] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
      m.sr.forEach(function (i) { row[i - 1] += w; });
    });
    function sum(from, to) {
      var s = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
      for (var y = from; y <= to; y++) { var r = years[y]; if (r) for (var i = 0; i < 10; i++) s[i] += r[i]; }
      return s;
    }
    var win = {}, cum = {}, maxW = 0, maxC = 0;
    ENDS.forEach(function (end) {
      win[end] = sum(end - SPAN + 1, end);
      cum[end] = sum(FIRST_YEAR, end);
      maxW = Math.max(maxW, Math.max.apply(null, win[end]));
      maxC = Math.max(maxC, Math.max.apply(null, cum[end]));
    });
    var decades = {}, maxD = 0;
    for (var d = Math.floor(FIRST_YEAR / 10) * 10; d <= LAST; d += 10) {
      decades[d] = sum(d, Math.min(d + 9, LAST));
      maxD = Math.max(maxD, Math.max.apply(null, decades[d]));
    }
    cache = { key: key, win: win, cum: cum, maxW: maxW, maxC: maxC, decades: decades, maxD: maxD };
    return cache;
  }
  function windowLabel(end) { return (state.mode === "cumulative" ? FIRST_YEAR : end - SPAN + 1) + "–" + end; }
  function fiveLabel(end) { return (end - SPAN + 1) + "–" + end; }
  function scoresAt(end) { var M = measure(); return end >= FIRST ? (state.mode === "cumulative" ? M.cum : M.win)[end] : null; }
  function scores() { return scoresAt(state.end); }
  function scaleMax() { var M = measure(); return state.mode === "cumulative" ? M.maxC : M.maxW; }
  function fmt(v) { return Math.round(v * 10) / 10; }
  function inWindow() {
    var from = state.mode === "cumulative" ? FIRST_YEAR : state.end - SPAN + 1;
    return A.moves.filter(function (m) { return m.y >= from && m.y <= state.end && passes(m); });
  }
  function byWeight(a, b) { return b.w - a.w || b.y - a.y || (a.m < b.m ? -1 : 1); }
  function change(n) {   // against the five years before: "up", "down" or "", with the earlier score
    if (state.mode === "cumulative") return { dir: "", prev: null };   // a build-up only grows: no arrows
    var now = scores()[n - 1], prevS = scoresAt(state.end - SPAN);
    if (!prevS) return { dir: "", prev: null };
    var prev = prevS[n - 1];
    var dir = now > prev * (1 + CHANGE) && now - prev >= 1 ? "up" : now < prev * (1 - CHANGE) && prev - now >= 1 ? "down" : "";
    return { dir: dir, prev: prev };
  }
  function shaded() {
    var s = scores(), topV = scaleMax();
    return { type: "FeatureCollection", features: DATA.subregions.features.map(function (f) {
      var n = f.properties.n, v = s[n - 1];
      return { type: "Feature", id: n, geometry: f.geometry, properties: { n: n, name: f.properties.name, v: v, f: topV ? Math.sqrt(v / topV) : 0 } };   // square root: the low end stays legible beside the peaks
    }) };
  }
  function colourAt(f) { return RAMP[Math.max(0, Math.min(RAMP.length - 1, Math.round(f * (RAMP.length - 1))))]; }
  function rampExpr() {
    var e = ["interpolate", ["linear"], ["get", "f"]];
    RAMP.forEach(function (c, i) { e.push(i / (RAMP.length - 1), c); });
    return ["case", ["==", ["get", "v"], 0], "rgba(0,0,0,0)", e];
  }

  // ---- markers -----------------------------------------------------------------------------------
  function el(tag, cls, text, parent) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }
  function button(cls, text, title, onClick) {
    var b = el("button", cls, text);
    b.type = "button";
    if (title) { b.title = title; b.setAttribute("aria-label", title); }
    b.addEventListener("click", function (ev) { ev.stopPropagation(); onClick(); });
    return b;
  }
  var markers = [];
  function clearMarkers() { markers.forEach(function (m) { m.remove(); }); markers = []; }
  function drawMarkers(ms) {
    clearMarkers();
    var wl = windowLabel(state.end), prevWl = fiveLabel(state.end - SPAN);
    DATA.subregions.features.forEach(function (f) {
      var n = f.properties.n;
      var k = ms.filter(function (m) { return m.sr.indexOf(n) >= 0; }).length, ch = change(n);
      var title = n + " " + f.properties.name + ": " + k + (k === 1 ? " move" : " moves") + " in " + wl +
        (ch.dir ? "; intensity " + ch.dir + " from " + prevWl : "");
      var b = button("amap-count" + (k ? "" : " zero") + (state.sel === n ? " on" : ""), "", title, function () { select(n); });
      el("span", "amap-count-n", String(k), b);
      if (ch.dir) el("span", "amap-arrow " + ch.dir, ch.dir === "up" ? "▲" : "▼", b).setAttribute("aria-hidden", "true");
      markers.push(new maplibregl.Marker({ element: b }).setLngLat(f.properties.lab).addTo(map));
    });
    var atFeature = {};
    ms.forEach(function (m) { (m.f || []).forEach(function (fid) { (atFeature[fid] = atFeature[fid] || []).push(m); }); });
    Object.keys(atFeature).forEach(function (fid) {
      var F = FEATS[fid];
      if (!F) return;
      var list = atFeature[fid], topW = Math.max.apply(null, list.map(function (m) { return m.w; }));
      var wrap = el("span", "amap-feat" + (state.feat === fid ? " on" : ""));
      var size = Math.min(28, 11 + Math.round(5 * Math.sqrt(list.length - 1)));
      var dot = button("amap-feat-dot", list.length > 1 ? String(list.length) : "", F.n + ": " + list.length + (list.length === 1 ? " move" : " moves") + " in " + wl, function () { selectFeature(fid); });
      dot.style.width = dot.style.height = size + "px";
      dot.setAttribute("data-w", String(topW));
      wrap.appendChild(dot);
      el("span", "amap-feat-name", F.n, wrap).setAttribute("aria-hidden", "true");
      markers.push(new maplibregl.Marker({ element: wrap, anchor: "left", offset: [-size / 2, 0] }).setLngLat([F.lon, F.lat]).addTo(map));
    });
  }

  var loaded = false;
  var FILL_BY_ZOOM = ["interpolate", ["linear"], ["zoom"], ZOOM_FEATURES - 0.5, 0.55, ZOOM_FEATURES + 0.5, 0.22];
  function zoomClass() {
    var z = map.getZoom();
    canvasBox.classList.toggle("zoomed", z >= ZOOM_FEATURES || state.sel !== null);
    canvasBox.classList.toggle("named", z >= ZOOM_NAMES);
    if (loaded) map.setPaintProperty("asr-fill", "fill-opacity", state.sel !== null ? 0.22 : FILL_BY_ZOOM);
  }
  map.on("zoom", zoomClass);
  map.on("moveend", zoomClass);
  map.on("load", function () {
    loaded = true;
    map.addSource("asr", { type: "geojson", data: shaded() });
    map.addLayer({ id: "asr-fill", type: "fill", source: "asr", paint: { "fill-color": rampExpr(), "fill-opacity": FILL_BY_ZOOM } });
    // hairline white seams between the sub-regions read lighter than dark outlines on the grey sea
    map.addLayer({ id: "asr-line", type: "line", source: "asr", paint: { "line-color": "#ffffff", "line-width": 1.2, "line-opacity": 0.85 } });
    map.addLayer({ id: "asr-sel", type: "line", source: "asr", filter: ["==", ["get", "n"], -1], paint: { "line-color": INK, "line-width": 1.8 } });
    // reference lines, off by default: indicative maritime boundaries (dotted grey), China's dashed line (dashed ink)
    if (A.lines) {
      map.addSource("ln-maritime", { type: "geojson", data: A.lines.maritime });
      map.addLayer({ id: "ln-maritime", type: "line", source: "ln-maritime", layout: { visibility: "none", "line-cap": "round" },
                     paint: { "line-color": "#6b7780", "line-width": 1.1, "line-dasharray": [0.6, 2.2], "line-opacity": 0.9 } });
      map.addSource("ln-dashline", { type: "geojson", data: A.lines.dashline });
      map.addLayer({ id: "ln-dashline", type: "line", source: "ln-dashline", layout: { visibility: "none" },
                     paint: { "line-color": INK, "line-width": 1.4, "line-opacity": 0.75 } });
    }
    map.on("mousemove", "asr-fill", function () { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "asr-fill", function () { map.getCanvas().style.cursor = ""; });
    map.on("click", "asr-fill", function (ev) { select(ev.features[0].properties.n); });
    render();
    if (state.sel !== null) fitTo(state.sel, false);
  });

  // ---- selection -------------------------------------------------------------------------------
  function srFeature(n) { return DATA.subregions.features.filter(function (f) { return f.properties.n === n; })[0]; }
  function fitTo(n, animate) {   // clear of the caption, and of the panel where it sits over the map's right side
    var side = phone.matches ? 24 : 420;
    map.fitBounds(geoBounds([srFeature(n)]), { padding: { top: phone.matches ? 90 : 150, bottom: 40, left: 40, right: side }, maxZoom: 7.5, animate: animate !== false });
  }
  function showPanel() {
    var panel = $("amap-explore");
    if (panel && panel.getBoundingClientRect().top > window.innerHeight * 0.75) panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function select(n) {
    state.feat = null;
    state.sel = state.sel === n ? null : n;
    render();
    if (state.sel === null) map.fitBounds(SEA, { padding: padding() });
    else { fitTo(n); showPanel(); }
  }
  function selectFeature(fid) {
    var F = FEATS[fid];
    state.feat = fid;
    if (F && F.sr) state.sel = F.sr;
    render();
    showPanel();
  }

  // ---- details ---------------------------------------------------------------------------------
  function moveRow(m, parent) {
    var li = el("li", "amap-move", undefined, parent);
    var head = el("div", "event-row-head", undefined, li);
    el("span", "case-claimant", NAMES[m.c] || m.c, head).setAttribute("data-code", m.c);
    el("span", "event-date", String(m.y), head);
    var a = el("a", "case-id", m.m, head);
    a.href = "cases/" + m.m + ".html";
    el("span", "type-pill", TYPE_LABELS[m.t] || m.t, head).setAttribute("data-type", m.t);
    el("p", "event-summary", m.x.replace(/^\d{4}[^:]{0,24}:\s*/, ""), li);
  }
  function list(ms) {
    var ol = el("ol", "event-list amap-moves", undefined, detail);
    ms.slice(0, 40).forEach(function (m) { moveRow(m, ol); });
    if (ms.length > 40) el("p", "popup-more", "and " + (ms.length - 40) + " more", detail);
  }
  function back(text, fn) { detail.appendChild(button("amap-sr", text, "", fn)); }
  function summary(ms, extra) {
    var hard = ms.filter(function (m) { return m.w >= 3; }).length;
    el("p", "amap-sum", ms.length + (ms.length === 1 ? " move" : " moves") + (extra || "") + "; " + hard + " coercive or force.", detail);
  }
  function srLinks(prefix, ns) {
    var p = el("p", "amap-top", prefix, detail);
    ns.forEach(function (n, i) {
      p.appendChild(button("amap-sr", n + " " + SR_NAMES[n], "", function () { select(n); }));
      if (i < ns.length - 1) p.appendChild(document.createTextNode(", "));
    });
  }
  function none(what) { return state.mode === "cumulative" ? "No " + what + " yet." : "No " + what + " in these five years."; }
  function renderDetail(all) {
    detail.textContent = "";
    var wl = windowLabel(state.end), s = scores();
    if (state.feat) {
      var F = FEATS[state.feat];
      var fm = all.filter(function (m) { return (m.f || []).indexOf(state.feat) >= 0; }).sort(byWeight);
      el("h3", "amap-detail-head", F.n + ", " + wl, detail);
      if (F.sr) el("p", "amap-where", "In sub-region " + F.sr + " " + SR_NAMES[F.sr], detail);
      if (!fm.length) el("p", "amap-empty", none("moves naming it"), detail);
      else { summary(fm); list(fm); }
      back(state.sel ? "Back to " + state.sel + " " + SR_NAMES[state.sel] : "Back to the whole sea", function () { state.feat = null; render(); });
      return;
    }
    if (state.sel !== null) {
      var n = state.sel, ch = change(n);
      var ms = all.filter(function (m) { return m.sr.indexOf(n) >= 0; }).sort(byWeight);
      el("h3", "amap-detail-head", n + " " + SR_NAMES[n] + ", " + wl, detail);
      if (!ms.length) el("p", "amap-empty", none("moves in this sub-region"), detail);
      else {
        summary(ms, ", score " + fmt(s[n - 1]));
        if (ch.prev !== null) el("p", "amap-where", (ch.dir ? "Intensity " + ch.dir + " from " : "About as intense as in ") + fiveLabel(state.end - SPAN) + " (score " + fmt(ch.prev) + ").", detail);
        var named = ms.filter(function (m) { return (m.f || []).length; }).length;
        el("p", "amap-hint", named ? named + " of them name a reef, shoal or island, shown on the map." : "None of them names a reef, shoal or island.", detail);
        list(ms);
      }
      back("Back to the whole sea", function () { select(n); });
      return;
    }
    el("h3", "amap-detail-head", "Across the sea, " + wl, detail);
    if (!all.length) { el("p", "amap-empty", none("moves"), detail); return; }
    summary(all);
    var rising = DATA.subregions.features.map(function (f) { return f.properties.n; }).filter(function (n) { return change(n).dir === "up"; });
    if (rising.length) srLinks("Rising since " + fiveLabel(state.end - SPAN) + ": ", rising);
    el("p", "amap-hint", state.mode === "cumulative"
      ? "The number on each sub-region is its moves since " + FIRST_YEAR + ", building up year by year. Click a sub-region, or zoom in, for the reefs, shoals and islands the moves name."
      : "The number on each sub-region is its moves in these five years; ▲ and ▼ mark a rise or fall of a fifth or more in intensity against the five years before. Click a sub-region, or zoom in, for the reefs, shoals and islands the moves name.", detail);
  }

  // ---- the timeline: moves per year by type, the years shown highlighted ------------------------
  var SVG_NS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs, parent) {
    var n = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(n);
    return n;
  }
  function renderTimeline() {
    if (!timeline) return;
    var counts = {}, peak = 0;
    A.moves.forEach(function (m) {
      if (!passes(m) || (state.sel !== null && m.sr.indexOf(state.sel) < 0)) return;
      var c = counts[m.y] || (counts[m.y] = { declarative: 0, demonstrative: 0, coercive: 0, force: 0 });
      c[m.t] += 1;
    });
    Object.keys(counts).forEach(function (y) { var c = counts[y]; peak = Math.max(peak, c.declarative + c.demonstrative + c.coercive + c.force); });
    var n = LAST - FIRST_YEAR + 1, W = n * 6, H = 40;
    timeline.textContent = "";
    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + (H + 12), preserveAspectRatio: "none", role: "img",
      "aria-label": "Moves per year, " + FIRST_YEAR + " to " + LAST + (state.sel !== null ? ", sub-region " + state.sel : "") + "; the years on the map are highlighted" }, timeline);
    var from = state.mode === "cumulative" ? FIRST_YEAR : state.end - SPAN + 1;
    svgEl("rect", { x: (from - FIRST_YEAR) * 6, y: 0, width: (state.end - from + 1) * 6, height: H, class: "amap-tl-band" }, svg);
    for (var y = FIRST_YEAR; y <= LAST; y++) {
      var c = counts[y], x = (y - FIRST_YEAR) * 6, base = H;
      var inside = y >= from && y <= state.end;
      if (c && peak) TYPES.forEach(function (t) {
        if (!c[t]) return;
        var h = c[t] / peak * (H - 2);
        base -= h;
        svgEl("rect", { x: x + 0.5, y: base, width: 5, height: h, fill: TYPE_COLOUR[t], "fill-opacity": inside ? 1 : 0.35 }, svg);
      });
      var hit = svgEl("rect", { x: x, y: 0, width: 6, height: H, fill: "transparent", class: "amap-tl-hit" }, svg);
      var tot = c ? c.declarative + c.demonstrative + c.coercive + c.force : 0;
      svgEl("title", {}, hit).textContent = y + ": " + tot + (tot === 1 ? " move" : " moves") + (c && (c.coercive + c.force) ? ", " + (c.coercive + c.force) + " coercive or force" : "");
      (function (yy) { hit.addEventListener("click", function () { setEnd(state.mode === "cumulative" ? yy : yy + Math.floor(SPAN / 2)); }); })(y);
    }
    [FIRST_YEAR, 1990, 2010, LAST].forEach(function (yy) {
      if (yy < FIRST_YEAR || yy > LAST) return;
      var t = svgEl("text", { x: (yy - FIRST_YEAR) * 6 + 3, y: H + 10, class: "amap-tl-year", "text-anchor": yy === FIRST_YEAR ? "start" : yy === LAST ? "end" : "middle" }, svg);
      t.textContent = String(yy);
    });
  }

  // ---- small maps by decade --------------------------------------------------------------------
  var PROJ = (function () {   // equirectangular, scaled to a 100-wide box
    var b = SEA, k = 100 / (b[1][0] - b[0][0]);
    return { h: (b[1][1] - b[0][1]) * k, x: function (lon) { return (lon - b[0][0]) * k; }, y: function (lat) { return (b[1][1] - lat) * k; } };
  })();
  function pathOf(geom) {
    var polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates, d = "";
    polys.forEach(function (rings) { rings.forEach(function (r) {
      d += r.map(function (c, i) { return (i ? "L" : "M") + PROJ.x(c[0]).toFixed(1) + " " + PROJ.y(c[1]).toFixed(1); }).join("") + "Z";
    }); });
    return d;
  }
  var PATHS = DATA.subregions.features.map(function (f) { return pathOf(f.geometry); });
  function renderDecades() {
    if (!decadesBox) return;
    var M = measure();
    decadesBox.textContent = "";
    Object.keys(M.decades).map(Number).sort().forEach(function (d) {
      var vals = M.decades[d], end = Math.min(d + 9, LAST), current = state.end >= d && state.end <= d + 9;
      var b = button("amap-decade" + (current ? " on" : ""), "", "The " + d + "s: show " + fiveLabel(end), function () { setEnd(end); });
      var svg = svgEl("svg", { viewBox: "0 0 100 " + PROJ.h.toFixed(1), "aria-hidden": "true" }, b);
      PATHS.forEach(function (d0, i) {
        var v = vals[i];
        svgEl("path", { d: d0, fill: v && M.maxD ? colourAt(Math.sqrt(v / M.maxD)) : "none", "fill-opacity": "0.75", stroke: "#a7b1b8", "stroke-width": "0.5" }, svg);
      });
      el("span", "amap-decade-label", d + "s", b);
      decadesBox.appendChild(b);
    });
  }

  // ---- the tick where Chubb's coding ends --------------------------------------------------------
  function clampEnd(y) { return Math.min(LAST, Math.max(FIRST, y)); }
  (function sourceTick() {
    var ticks = $("amap-ticks"), mats = A.mats_last_year;
    if (!ticks || mats < FIRST || mats > LAST) return;
    var t = el("span", "amap-tick source", undefined, ticks);
    t.style.left = (100 * (mats - FIRST) / Math.max(1, LAST - FIRST)) + "%";
    t.title = "Chubb's coding (MATS) ends with " + mats;
  })();

  // ---- the view in the address: #y2015-c-cn-at-p-t-cf-s6-f-scarborough-shoal ---------------------
  function hashFor() {
    var t = state.types.length === TYPES.length ? "" : "-t-" + state.types.map(function (x) { return TYPE_KEY[x]; }).join("");
    return "#y" + state.end + (state.mode === "cumulative" ? "-c" : "") + (state.who !== "ALL" ? "-" + state.who.toLowerCase() : "") +
      (state.target ? "-at-" + state.target.toLowerCase() : "") + t +
      (state.lines.length ? "-l-" + state.lines.map(function (k) { return LINE_KEY[k]; }).join("") : "") +
      (state.sel !== null ? "-s" + state.sel : "") + (state.feat ? "-f-" + state.feat : "");
  }
  function readHash() {
    var m = /^#y(\d{4})(-c)?(?:-([a-z]{2}))?(?:-at-([a-z]))?(?:-t-([dmcf]+))?(?:-l-([md]+))?(?:-s(\d{1,2}))?(?:-f-([a-z0-9-]+))?$/.exec(location.hash);
    if (!m) return false;
    var y = parseInt(m[1], 10);
    if (y >= FIRST && y <= LAST) state.end = y;
    state.mode = m[2] ? "cumulative" : "window";
    state.who = m[3] && NAMES[m[3].toUpperCase()] ? m[3].toUpperCase() : "ALL";
    state.target = m[4] && TARGETS[m[4].toUpperCase()] ? m[4].toUpperCase() : "";
    state.types = m[5] ? TYPES.filter(function (t) { return m[5].indexOf(TYPE_KEY[t]) >= 0; }) : TYPES.slice();
    if (!state.types.length) state.types = TYPES.slice();
    state.lines = m[6] ? ["maritime", "dashline"].filter(function (k) { return m[6].indexOf(LINE_KEY[k]) >= 0; }) : [];
    state.sel = m[7] && SR_NAMES[m[7]] ? parseInt(m[7], 10) : null;
    state.feat = m[8] && FEATS[m[8]] ? m[8] : null;
    syncControls();
    return true;
  }
  function syncControls() {
    claimSel.value = state.who;
    if (targetSel) targetSel.value = state.target;
    modeInputs.forEach(function (i) { i.checked = i.value === state.mode; });
    typeInputs.forEach(function (i) { i.checked = state.types.indexOf(i.value) >= 0; });
    lineInputs.forEach(function (i) { i.checked = state.lines.indexOf(i.id.replace("amap-line-", "")) >= 0; });
  }
  function writeHash() {
    if (!history.replaceState) return;
    var isDefault = hashFor() === "#y" + START;
    try { history.replaceState(null, "", isDefault ? location.pathname + location.search : hashFor()); } catch (e) { /* a sandboxed frame */ }
  }
  var linkBtn = $("amap-link"), linkDone = $("amap-link-done");
  if (linkBtn) linkBtn.addEventListener("click", function () {
    var url = location.href.split("#")[0] + hashFor();
    function ok() { linkDone.textContent = "Copied"; setTimeout(function () { linkDone.textContent = ""; }, 2000); }
    try { navigator.clipboard.writeText(url).then(ok, function () { linkDone.textContent = url; }); }
    catch (e) { linkDone.textContent = url; }
  });

  // ---- render ----------------------------------------------------------------------------------
  function whoLine() {
    var parts = [state.who === "ALL" ? "All claimants" : NAMES[state.who] || state.who];
    if (state.types.length < TYPES.length) parts.push(state.types.map(function (t) { return (TYPE_LABELS[t] || t).toLowerCase(); }).join(", ") + " only");
    if (state.target) parts.push("directed at " + (TARGETS[state.target] || state.target));
    return parts.join(" · ");
  }
  function render() {
    var wl = windowLabel(state.end);
    whenEl.textContent = wl;
    label.value = wl;
    slider.value = String(state.end);
    slider.setAttribute("aria-valuetext", wl);
    whoEl.textContent = whoLine();
    var all = inWindow();
    if (loaded) {
      map.getSource("asr").setData(shaded());
      map.setFilter("asr-sel", ["==", ["get", "n"], state.sel === null ? -1 : state.sel]);
      drawMarkers(all);
      zoomClass();
      ["maritime", "dashline"].forEach(function (k) { if (map.getLayer("ln-" + k)) map.setLayoutProperty("ln-" + k, "visibility", state.lines.indexOf(k) >= 0 ? "visible" : "none"); });
    }
    renderDetail(all);
    renderTimeline();
    renderDecades();
    writeHash();
  }
  function setEnd(y) { state.end = clampEnd(y); render(); }

  slider.addEventListener("input", function () { setEnd(parseInt(slider.value, 10)); });
  claimSel.addEventListener("change", function () { state.who = claimSel.value; render(); });
  if (targetSel) targetSel.addEventListener("change", function () { state.target = targetSel.value; render(); });
  if (sharedBox) sharedBox.addEventListener("change", render);
  lineInputs.forEach(function (i) { i.addEventListener("change", function () {
    state.lines = lineInputs.filter(function (x) { return x.checked; }).map(function (x) { return x.id.replace("amap-line-", ""); });
    render();
  }); });
  modeInputs.forEach(function (i) { i.addEventListener("change", function () { if (i.checked) { state.mode = i.value; render(); } }); });
  typeInputs.forEach(function (i) {
    i.addEventListener("change", function () {
      var on = typeInputs.filter(function (x) { return x.checked; }).map(function (x) { return x.value; });
      if (!on.length) { i.checked = true; return; }   // at least one type stays on
      state.types = TYPES.filter(function (t) { return on.indexOf(t) >= 0; });
      render();
    });
  });
  window.addEventListener("hashchange", function () { if (readHash()) { render(); if (state.sel !== null) fitTo(state.sel); } });

  var playTimer = null;
  function stopPlay() { clearInterval(playTimer); playTimer = null; playBtn.setAttribute("aria-pressed", "false"); playBtn.textContent = "Play"; }
  playBtn.addEventListener("click", function () {
    if (playTimer) { stopPlay(); return; }
    if (state.end >= LAST) setEnd(FIRST);
    playBtn.setAttribute("aria-pressed", "true"); playBtn.textContent = "Pause";
    playTimer = setInterval(function () {
      if (state.end >= LAST) { stopPlay(); return; }
      setEnd(state.end + 1);
    }, 550);
  });

  readHash();
  render();
})();
