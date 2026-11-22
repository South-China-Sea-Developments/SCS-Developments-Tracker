/* The assertiveness map (ticket 27): the ten sub-regions shaded on one ramp by the type-weighted moves of a
   five-year window (declarative 1, demonstrative 2, coercive 3, force 4; web.build.window_scores), the
   latest window first. The scale is fixed across every window for the claimant chosen, so a darker shade
   always means more, or harsher, moves. Events are an optional layer in neutral ink. */
(function () {
  "use strict";
  var src = document.getElementById("mapdata");
  if (!src || typeof maplibregl === "undefined" || !document.getElementById("amap")) return;
  var DATA = JSON.parse(src.textContent);
  var A = DATA.assert;
  if (!A) return;
  var NAMES = DATA.names, SR_NAMES = DATA.subregion_names, TYPE_LABELS = DATA.type_labels;
  var SPAN = A.span, ENDS = A.ends;
  var root = getComputedStyle(document.documentElement);
  var RAMP = (root.getPropertyValue("--seq") || "#cde2fb, #9ec5f4, #6da7ec, #3987e5, #256abf, #184f95, #0d366b").split(",").map(function (s) { return s.trim(); });
  var LINE = (root.getPropertyValue("--map-zone-line") || "#5d6b76").trim();
  var INK = (root.getPropertyValue("--ink") || "#0c1a2a").trim();

  var slider = document.getElementById("amap-year");
  var label = document.getElementById("amap-label");
  var whenEl = document.getElementById("amap-when");
  var whoEl = document.getElementById("amap-who");
  var claimSel = document.getElementById("amap-claimant");
  var pointsBox = document.getElementById("amap-points");
  var detail = document.getElementById("amap-detail");
  var playBtn = document.getElementById("amap-play");
  slider.min = String(ENDS[0]);
  slider.max = String(ENDS[ENDS.length - 1]);
  slider.value = slider.max;

  // the legend is the ramp itself
  var rampEl = document.querySelector(".amap-ramp");
  if (rampEl) rampEl.style.background = "linear-gradient(to right, " + RAMP.join(", ") + ")";

  // the first screen: slim banner + menu + the map; the stage keeps that height when it sticks on scrolling
  var top = document.querySelector(".site-head");
  function sizeStage() { if (top) document.documentElement.style.setProperty("--top-h", top.offsetHeight + "px"); }
  sizeStage();

  var styleEl = document.getElementById("mapstyle");
  var STYLE = styleEl ? JSON.parse(styleEl.textContent) : { version: 8, sources: {}, layers: [] };
  function geoBounds(gj) {
    var w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
    function walk(c) {
      if (typeof c[0] === "number") { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]); }
      else c.forEach(walk);
    }
    gj.features.forEach(function (f) { walk(f.geometry.coordinates); });
    return [[w, s], [e, n]];
  }
  var BOUNDS = geoBounds(DATA.subregions);
  function padding() { return { top: 24, bottom: 64 + (top ? top.offsetHeight : 0), left: 24, right: 24 }; }   // the part above the fold, clear of the cue
  var map = new maplibregl.Map({
    container: "amap", style: STYLE, bounds: BOUNDS, fitBoundsOptions: { padding: padding() },
    minZoom: 3.5, maxZoom: 9, cooperativeGestures: true, attributionControl: false, dragRotate: false, pitchWithRotate: false
  });
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  function refit() { sizeStage(); map.resize(); map.fitBounds(BOUNDS, { padding: padding(), animate: false }); }
  var bannerImg = document.querySelector(".banner-img");
  if (bannerImg && !bannerImg.complete) bannerImg.addEventListener("load", refit);
  window.addEventListener("resize", refit);
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
  map.on("error", function (e) {
    var msg = e && e.error ? String(e.error.message || e.error) : "";
    if (!/tile|sprite|glyph|font|fetch|network|load|status|json|response/i.test(msg)) console.warn("amap: " + msg);
  });

  // ---- state -----------------------------------------------------------------------------------
  var state = { end: ENDS[ENDS.length - 1], who: "ALL", sel: null };
  function windowLabel(end) { return (end - SPAN + 1) + "–" + end; }
  function scores() { return A.scores[state.who][String(state.end)]; }
  function scaleMax() { return A.max[state.who] || 0; }
  function movesIn(sr) {
    var from = state.end - SPAN + 1;
    return A.moves.filter(function (m) {
      return m.y >= from && m.y <= state.end && (state.who === "ALL" || m.c === state.who) && (sr === null || m.sr.indexOf(sr) >= 0);
    });
  }

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
  function points() {
    var from = state.end - SPAN + 1;
    return { type: "FeatureCollection", features: DATA.events.filter(function (e) {
      var y = parseInt(e.ds.slice(0, 4), 10);
      return e.lat !== undefined && y >= from && y <= state.end && (state.who === "ALL" || e.c === state.who);
    }).map(function (e) { return { type: "Feature", geometry: { type: "Point", coordinates: [e.lon, e.lat] }, properties: { m: e.m } }; }) };
  }

  var loaded = false;
  map.on("load", function () {
    loaded = true;
    map.addSource("asr", { type: "geojson", data: shaded() });
    map.addLayer({ id: "asr-fill", type: "fill", source: "asr", paint: { "fill-color": rampExpr(), "fill-opacity": 0.9 } });
    map.addLayer({ id: "asr-line", type: "line", source: "asr", paint: { "line-color": LINE, "line-width": 1, "line-opacity": 0.7 } });
    map.addLayer({ id: "asr-sel", type: "line", source: "asr", filter: ["==", ["get", "n"], -1], paint: { "line-color": INK, "line-width": 2.5 } });
    map.addSource("apts", { type: "geojson", data: points() });
    map.addLayer({ id: "apts", type: "circle", source: "apts", layout: { visibility: "none" },
                   paint: { "circle-radius": 3.5, "circle-color": INK, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 } });
    var tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: "amap-tip", offset: 8 });
    map.on("mousemove", "asr-fill", function (ev) {
      var p = ev.features[0].properties;
      map.getCanvas().style.cursor = "pointer";
      var n = movesIn(p.n).length;
      tip.setLngLat(ev.lngLat).setText(p.n + " " + p.name + ": " + (n ? n + (n === 1 ? " move" : " moves") + ", score " + p.v : "no moves") + " in " + windowLabel(state.end)).addTo(map);
    });
    map.on("mouseleave", "asr-fill", function () { map.getCanvas().style.cursor = ""; tip.remove(); });
    map.on("click", "asr-fill", function (ev) { select(ev.features[0].properties.n); });
    render();
  });

  // ---- rendering -------------------------------------------------------------------------------
  function el(tag, cls, text, parent) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }
  function select(n) {
    state.sel = state.sel === n ? null : n;
    render();
    var panel = document.getElementById("amap-explore");
    if (state.sel !== null && panel && panel.getBoundingClientRect().top > window.innerHeight * 0.6) panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
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
  function renderDetail() {
    detail.textContent = "";
    var sr = state.sel, s = scores();
    var ms = movesIn(sr).sort(function (a, b) { return b.w - a.w || b.y - a.y || (a.m < b.m ? -1 : 1); });
    var head = el("h3", "amap-detail-head", sr === null ? "Across the sea, " + windowLabel(state.end) : sr + " " + SR_NAMES[sr] + ", " + windowLabel(state.end), detail);
    head.setAttribute("tabindex", "-1");
    if (!ms.length) {
      el("p", "amap-empty", sr === null ? "No moves in these five years." : "No moves in this sub-region in these five years.", detail);
      return;
    }
    var hard = ms.filter(function (m) { return m.w >= 3; }).length;
    var line = ms.length + (ms.length === 1 ? " move" : " moves") + (sr === null ? "" : ", score " + s[sr - 1]) + "; " + hard + " coercive or force.";
    el("p", "amap-sum", line, detail);
    if (sr === null) {
      var ranked = s.map(function (v, i) { return { n: i + 1, v: v }; }).filter(function (r) { return r.v > 0; }).sort(function (a, b) { return b.v - a.v; }).slice(0, 3);
      var p = el("p", "amap-top", "Most intense: ", detail);
      ranked.forEach(function (r, i) {
        var b = el("button", "amap-sr", r.n + " " + SR_NAMES[r.n], p);
        b.type = "button";
        b.addEventListener("click", function () { select(r.n); });
        if (i < ranked.length - 1) p.appendChild(document.createTextNode(", "));
      });
      el("p", "amap-hint", "Click a sub-region on the map for its moves.", detail);
      return;
    }
    var ol = el("ol", "event-list amap-moves", undefined, detail);
    ms.slice(0, 40).forEach(function (m) { moveRow(m, ol); });
    if (ms.length > 40) el("p", "popup-more", "and " + (ms.length - 40) + " more", detail);
    var back = el("button", "amap-sr", "Back to the whole sea", detail);
    back.type = "button";
    back.addEventListener("click", function () { select(state.sel); });
  }
  function render() {
    var wl = windowLabel(state.end);
    whenEl.textContent = wl;
    label.value = wl;
    slider.setAttribute("aria-valuetext", wl);
    whoEl.textContent = state.who === "ALL" ? "All claimants" : NAMES[state.who] || state.who;
    if (loaded) {
      map.getSource("asr").setData(shaded());
      map.getSource("apts").setData(points());
      map.setLayoutProperty("apts", "visibility", pointsBox.checked ? "visible" : "none");
      map.setFilter("asr-sel", ["==", ["get", "n"], state.sel === null ? -1 : state.sel]);
    }
    renderDetail();
  }

  slider.addEventListener("input", function () { state.end = parseInt(slider.value, 10); render(); });
  claimSel.addEventListener("change", function () { state.who = claimSel.value; render(); });
  pointsBox.addEventListener("change", render);

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
