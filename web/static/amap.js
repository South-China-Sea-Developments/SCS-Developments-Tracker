/* The assertiveness map (ticket 27): the ten sub-regions shaded on one ramp by the type-weighted moves of a
   five-year window (declarative 1, demonstrative 2, coercive 3, force 4; web.build.window_scores), each
   with its number of moves, the latest window first. The scale is fixed across every window for the
   claimant chosen, so a darker shade always means more, or harsher, moves. Zoomed in (or a sub-region
   clicked), the reefs, shoals and islands the moves name appear, each with its own moves. */
(function () {
  "use strict";
  var src = document.getElementById("mapdata");
  if (!src || typeof maplibregl === "undefined" || !document.getElementById("amap")) return;
  var DATA = JSON.parse(src.textContent);
  var A = DATA.assert;
  if (!A) return;
  var NAMES = DATA.names, SR_NAMES = DATA.subregion_names, TYPE_LABELS = DATA.type_labels, FEATS = A.features || {};
  var SPAN = A.span, ENDS = A.ends;
  var ZOOM_FEATURES = 5.8;   // from here in, features instead of sub-region counts
  var root = getComputedStyle(document.documentElement);
  var RAMP = (root.getPropertyValue("--seq") || "#cde2fb, #9ec5f4, #6da7ec, #3987e5, #256abf, #184f95, #0d366b").split(",").map(function (s) { return s.trim(); });
  var LINE = (root.getPropertyValue("--map-zone-line") || "#5d6b76").trim();
  var INK = (root.getPropertyValue("--ink") || "#0c1a2a").trim();

  var slider = document.getElementById("amap-year");
  var label = document.getElementById("amap-label");
  var whenEl = document.getElementById("amap-when");
  var whoEl = document.getElementById("amap-who");
  var claimSel = document.getElementById("amap-claimant");
  var detail = document.getElementById("amap-detail");
  var playBtn = document.getElementById("amap-play");
  var canvasBox = document.getElementById("amap");
  slider.min = String(ENDS[0]);
  slider.max = String(ENDS[ENDS.length - 1]);
  slider.value = slider.max;

  var rampEl = document.querySelector(".amap-ramp");
  if (rampEl) rampEl.style.background = "linear-gradient(to right, " + RAMP.join(", ") + ")";

  // the first screen is the menu and the map; the stage keeps its height when it sticks on scrolling
  var top = document.querySelector(".site-head");
  function sizeStage() { if (top) document.documentElement.style.setProperty("--top-h", top.offsetHeight + "px"); }
  sizeStage();

  var styleEl = document.getElementById("mapstyle");
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
  function padding() {   // the part of the stage above the fold, clear of the caption and the cue
    var below = phone.matches ? 0 : (top ? top.offsetHeight : 0);
    return { top: phone.matches ? 90 : 24, bottom: 56 + below, left: 24, right: 24 };
  }
  var map = new maplibregl.Map({
    container: "amap", style: STYLE, bounds: SEA, fitBoundsOptions: { padding: padding() },
    minZoom: 3.5, maxZoom: 10, cooperativeGestures: true, attributionControl: false, dragRotate: false, pitchWithRotate: false
  });
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
  function refit() { sizeStage(); map.resize(); map.fitBounds(SEA, { padding: padding(), animate: false }); }
  window.addEventListener("resize", refit);
  map.on("error", function (e) {
    var msg = e && e.error ? String(e.error.message || e.error) : "";
    if (!/tile|sprite|glyph|font|fetch|network|load|status|json|response/i.test(msg)) console.warn("amap: " + msg);
  });

  // ---- state -----------------------------------------------------------------------------------
  var state = { end: ENDS[ENDS.length - 1], who: "ALL", sel: null, feat: null };
  function windowLabel(end) { return (end - SPAN + 1) + "–" + end; }
  function scores() { return A.scores[state.who][String(state.end)]; }
  function scaleMax() { return A.max[state.who] || 0; }
  function inWindow() {
    var from = state.end - SPAN + 1;
    return A.moves.filter(function (m) { return m.y >= from && m.y <= state.end && (state.who === "ALL" || m.c === state.who); });
  }
  function byWeight(a, b) { return b.w - a.w || b.y - a.y || (a.m < b.m ? -1 : 1); }

  function shaded() {
    var s = scores(), top = scaleMax();
    return { type: "FeatureCollection", features: DATA.subregions.features.map(function (f) {
      var n = f.properties.n, v = s[n - 1];
      return { type: "Feature", id: n, geometry: f.geometry, properties: { n: n, name: f.properties.name, v: v, f: top ? Math.sqrt(v / top) : 0 } };   // square root: the low end stays legible beside the peak windows
    }) };
  }
  function rampExpr() {
    var e = ["interpolate", ["linear"], ["get", "f"]];
    RAMP.forEach(function (c, i) { e.push(i / (RAMP.length - 1), c); });
    return ["case", ["==", ["get", "v"], 0], "rgba(0,0,0,0)", e];
  }

  // ---- markers: a count per sub-region; zoomed in, the features ------------------------------------
  function el(tag, cls, text, parent) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }
  var markers = [];
  function clearMarkers() { markers.forEach(function (m) { m.remove(); }); markers = []; }
  function button(cls, text, title, onClick) {
    var b = el("button", cls, text);
    b.type = "button";
    b.title = title;
    b.setAttribute("aria-label", title);
    b.addEventListener("click", function (ev) { ev.stopPropagation(); onClick(); });
    return b;
  }
  function drawMarkers(ms) {
    clearMarkers();
    var wl = windowLabel(state.end);
    DATA.subregions.features.forEach(function (f) {
      var n = f.properties.n;
      var k = ms.filter(function (m) { return m.sr.indexOf(n) >= 0; }).length;
      var b = button("amap-count" + (k ? "" : " zero"), String(k), n + " " + f.properties.name + ": " + k + (k === 1 ? " move" : " moves") + " in " + wl, function () { select(n); });
      markers.push(new maplibregl.Marker({ element: b }).setLngLat(f.properties.lab).addTo(map));
    });
    var atFeature = {};
    ms.forEach(function (m) { (m.f || []).forEach(function (fid) { (atFeature[fid] = atFeature[fid] || []).push(m); }); });
    Object.keys(atFeature).forEach(function (fid) {
      var F = FEATS[fid];
      if (!F) return;
      var list = atFeature[fid], top = Math.max.apply(null, list.map(function (m) { return m.w; }));
      var wrap = el("span", "amap-feat");
      var size = Math.min(30, 12 + Math.round(5 * Math.sqrt(list.length - 1)));
      var dot = button("amap-feat-dot", list.length > 1 ? String(list.length) : "", F.n + ": " + list.length + (list.length === 1 ? " move" : " moves") + " in " + wl, function () { selectFeature(fid); });
      dot.style.width = dot.style.height = size + "px";
      dot.setAttribute("data-w", String(top));
      wrap.appendChild(dot);
      el("span", "amap-feat-name", F.n, wrap);
      markers.push(new maplibregl.Marker({ element: wrap, anchor: "left", offset: [-size / 2, 0] }).setLngLat([F.lon, F.lat]).addTo(map));
    });
  }
  var FILL_BY_ZOOM = ["interpolate", ["linear"], ["zoom"], ZOOM_FEATURES - 0.5, 0.9, ZOOM_FEATURES + 0.5, 0.35];
  function zoomClass() {   // features show when zoomed in, or once a sub-region is chosen whatever the zoom (a phone stays far out)
    var detailed = map.getZoom() >= ZOOM_FEATURES || state.sel !== null;
    canvasBox.classList.toggle("zoomed", detailed);
    if (loaded) map.setPaintProperty("asr-fill", "fill-opacity", state.sel !== null ? 0.35 : FILL_BY_ZOOM);
  }
  map.on("zoom", zoomClass);

  var loaded = false;
  map.on("load", function () {
    loaded = true;
    map.addSource("asr", { type: "geojson", data: shaded() });
    map.addLayer({ id: "asr-fill", type: "fill", source: "asr", paint: { "fill-color": rampExpr(),
      "fill-opacity": FILL_BY_ZOOM } });
    map.addLayer({ id: "asr-line", type: "line", source: "asr", paint: { "line-color": LINE, "line-width": 1, "line-opacity": 0.7 } });
    map.addLayer({ id: "asr-sel", type: "line", source: "asr", filter: ["==", ["get", "n"], -1], paint: { "line-color": INK, "line-width": 2.5 } });
    map.on("mousemove", "asr-fill", function () { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "asr-fill", function () { map.getCanvas().style.cursor = ""; });
    map.on("click", "asr-fill", function (ev) { select(ev.features[0].properties.n); });
    zoomClass();
    render();
  });

  // ---- selection -------------------------------------------------------------------------------
  function srFeature(n) { return DATA.subregions.features.filter(function (f) { return f.properties.n === n; })[0]; }
  function showPanel() {
    var panel = document.getElementById("amap-explore");
    if (panel && panel.getBoundingClientRect().top > window.innerHeight * 0.75) panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function select(n) {
    state.feat = null;
    state.sel = state.sel === n ? null : n;
    render();
    if (state.sel === null) map.fitBounds(SEA, { padding: padding() });
    else { map.fitBounds(geoBounds([srFeature(n)]), { padding: 40, maxZoom: 7.5 }); showPanel(); }
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
  function back(text, fn) { detail.appendChild(button("amap-sr", text, text, fn)); }
  function summary(ms, extra) {
    var hard = ms.filter(function (m) { return m.w >= 3; }).length;
    el("p", "amap-sum", ms.length + (ms.length === 1 ? " move" : " moves") + (extra || "") + "; " + hard + " coercive or force.", detail);
  }
  function renderDetail(all) {
    detail.textContent = "";
    var wl = windowLabel(state.end), s = scores();
    if (state.feat) {
      var F = FEATS[state.feat];
      var fm = all.filter(function (m) { return (m.f || []).indexOf(state.feat) >= 0; }).sort(byWeight);
      el("h3", "amap-detail-head", F.n + ", " + wl, detail);
      if (F.sr) el("p", "amap-where", "In sub-region " + F.sr + " " + SR_NAMES[F.sr], detail);
      if (!fm.length) { el("p", "amap-empty", "No moves naming it in these five years.", detail); }
      else { summary(fm); list(fm); }
      back(state.sel ? "Back to " + state.sel + " " + SR_NAMES[state.sel] : "Back to the whole sea", function () { state.feat = null; render(); });
      return;
    }
    if (state.sel !== null) {
      var n = state.sel;
      var ms = all.filter(function (m) { return m.sr.indexOf(n) >= 0; }).sort(byWeight);
      el("h3", "amap-detail-head", n + " " + SR_NAMES[n] + ", " + wl, detail);
      if (!ms.length) el("p", "amap-empty", "No moves in this sub-region in these five years.", detail);
      else {
        summary(ms, ", score " + s[n - 1]);
        var named = ms.filter(function (m) { return (m.f || []).length; }).length;
        el("p", "amap-hint", named ? named + " of them name a reef, shoal or island, shown on the map." : "None of them names a reef, shoal or island.", detail);
        list(ms);
      }
      back("Back to the whole sea", function () { select(n); });
      return;
    }
    el("h3", "amap-detail-head", "Across the sea, " + wl, detail);
    if (!all.length) { el("p", "amap-empty", "No moves in these five years.", detail); return; }
    summary(all);
    var ranked = s.map(function (v, i) { return { n: i + 1, v: v }; }).filter(function (r) { return r.v > 0; }).sort(function (a, b) { return b.v - a.v; }).slice(0, 3);
    var p = el("p", "amap-top", "Most intense: ", detail);
    ranked.forEach(function (r, i) {
      p.appendChild(button("amap-sr", r.n + " " + SR_NAMES[r.n], r.n + " " + SR_NAMES[r.n], function () { select(r.n); }));
      if (i < ranked.length - 1) p.appendChild(document.createTextNode(", "));
    });
    el("p", "amap-hint", "The number on each sub-region is its moves in these five years. Click one, or zoom in, to see the reefs, shoals and islands the moves name.", detail);
  }
  function render() {
    var wl = windowLabel(state.end);
    whenEl.textContent = wl;
    label.value = wl;
    slider.setAttribute("aria-valuetext", wl);
    whoEl.textContent = state.who === "ALL" ? "All claimants" : NAMES[state.who] || state.who;
    var all = inWindow();
    if (loaded) {
      map.getSource("asr").setData(shaded());
      map.setFilter("asr-sel", ["==", ["get", "n"], state.sel === null ? -1 : state.sel]);
      drawMarkers(all);
      zoomClass();
    }
    renderDetail(all);
  }

  slider.addEventListener("input", function () { state.end = parseInt(slider.value, 10); render(); });
  claimSel.addEventListener("change", function () { state.who = claimSel.value; render(); });

  var playTimer = null;
  function stopPlay() { clearInterval(playTimer); playTimer = null; playBtn.setAttribute("aria-pressed", "false"); playBtn.textContent = "Play"; }
  playBtn.addEventListener("click", function () {
    if (playTimer) { stopPlay(); return; }
    if (state.end >= ENDS[ENDS.length - 1]) { state.end = ENDS[0]; slider.value = String(state.end); render(); }
    playBtn.setAttribute("aria-pressed", "true"); playBtn.textContent = "Pause";
    playTimer = setInterval(function () {
      if (state.end >= ENDS[ENDS.length - 1]) { stopPlay(); return; }
      state.end += 1;
      slider.value = String(state.end);
      render();
    }, 550);
  });

  render();
})();
