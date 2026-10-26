/* Event map: dated events as points (or as counts on their sub-region when unplaced), a time
   window scrubbed by month, and the same filter semantics as the case browser. MapLibre draws the
   map; the data is inline (data/events.json has the same content for reuse). */
(function () {
  "use strict";
  var src = document.getElementById("mapdata");
  if (!src || typeof maplibregl === "undefined") return;
  var DATA = JSON.parse(src.textContent);
  var EVENTS = DATA.events;
  var NAMES = DATA.names;
  var TYPE_LABELS = DATA.type_labels;
  var SR_NAMES = DATA.subregion_names;
  var FIRST = DATA.first_year;
  var form = document.getElementById("map-filters");
  var slider = document.getElementById("month");
  var windowSel = document.getElementById("window");
  var timeLabel = document.getElementById("time-label");
  var countEl = document.getElementById("map-count");
  var listEl = document.getElementById("event-list");
  var targetSel = document.getElementById("target");   // absent on the home page's compact filter row
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function monthIndex(iso) { return (parseInt(iso.slice(0, 4), 10) - FIRST) * 12 + parseInt(iso.slice(5, 7), 10) - 1; }
  function monthName(k) { return MONTHS[k % 12] + " " + (FIRST + Math.floor(k / 12)); }
  var lastMonth = Math.max((DATA.last_year - FIRST) * 12 + 11, Math.max.apply(null, EVENTS.map(function (e) { return monthIndex(e.ds); }).concat([0])));
  EVENTS.forEach(function (e) { e.ms = monthIndex(e.ds); e.me = Math.max(e.ms, monthIndex(e.de)); });
  slider.max = String(lastMonth);
  slider.value = String(lastMonth);
  windowSel.value = "0";

  // ---- map -------------------------------------------------------------------------------------
  // MapLibre over OpenFreeMap vector tiles with an English-first label style (vendored, inlined by
  // the build). Tiles, fonts and sprites are the only network requests; without them the sub-regions
  // and events still draw on the page plane.
  var styleEl = document.getElementById("mapstyle");
  var STYLE = styleEl ? JSON.parse(styleEl.textContent) : { version: 8, sources: {}, layers: [] };
  var bounds = geoBounds(DATA.subregions);
  var map = new maplibregl.Map({
    container: "map", style: STYLE, bounds: bounds, fitBoundsOptions: { padding: 12 },
    minZoom: 3.5, maxZoom: 11, cooperativeGestures: true, attributionControl: false, dragRotate: false, pitchWithRotate: false
  });
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
  map.addControl(new maplibregl.AttributionControl({ compact: false }));   // the style carries OpenFreeMap, OpenMapTiles and OSM
  map.on("error", function (e) {   // a missing tile, font or sprite is the offline case, not a fault
    var msg = e && e.error ? String(e.error.message || e.error) : "";
    if (!/tile|sprite|glyph|font|fetch|network|load|status|json|response/i.test(msg)) console.warn("map: " + msg);
  });

  function geoBounds(gj) {
    var w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
    function walk(c) {
      if (typeof c[0] === "number") { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]); }
      else c.forEach(walk);
    }
    gj.features.forEach(function (f) { walk(f.geometry.coordinates); });
    return [[w, s], [e, n]];
  }
  function center(f) {
    var b = geoBounds({ features: [f] });
    return [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2];
  }
  // the polygons are context, not controls. Their colours are the stylesheet's --map-zone tokens,
  // stated in light-mode terms whatever the scheme: in dark mode the stylesheet inverts the whole
  // canvas, basemap and polygons together.
  var rootStyle = getComputedStyle(document.documentElement);
  var ZONE_FILL = (rootStyle.getPropertyValue("--map-zone") || "#1a4f7e").trim();
  var ZONE_LINE = (rootStyle.getPropertyValue("--map-zone-line") || "#5f6d77").trim();
  map.on("load", function () {
    map.addSource("subregions", { type: "geojson", data: DATA.subregions });
    map.addLayer({ id: "sr-fill", type: "fill", source: "subregions", paint: { "fill-color": ZONE_FILL, "fill-opacity": 0.07 } });
    map.addLayer({ id: "sr-line", type: "line", source: "subregions", paint: { "line-color": ZONE_LINE, "line-width": 1, "line-opacity": 0.9 } });
  });

  var srCenters = {};
  DATA.subregions.features.forEach(function (f) {
    var n = String(f.properties.n), c = center(f);
    srCenters[n] = c;
    var label = document.createElement("span");
    label.className = "sr-label";
    label.textContent = n + " " + f.properties.name;
    new maplibregl.Marker({ element: label, anchor: "bottom", offset: [0, -14] }).setLngLat(c).addTo(map);
    label.removeAttribute("role"); label.removeAttribute("tabindex"); label.setAttribute("aria-hidden", "true");   // decoration, not a control
  });

  var live = [];   // markers of the current render
  function clearMarkers() { live.forEach(function (m) { m.remove(); }); live = []; }
  function addMarker(lnglat, el, title, popupBuilder) {
    el.setAttribute("tabindex", "0");
    el.setAttribute("role", "button");
    el.setAttribute("aria-label", title);
    el.title = title;
    var popup = new maplibregl.Popup({ maxWidth: "360px", className: "evt-popup", offset: 14, focusAfterOpen: true });
    popup.on("open", function () { popup.setDOMContent(popupBuilder()); });
    var m = new maplibregl.Marker({ element: el }).setLngLat(lnglat).setPopup(popup).addTo(map);
    el.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); m.togglePopup(); }
    });
    live.push(m);
    return m;
  }

  // ---- filters ---------------------------------------------------------------------------------
  function checked(name) {
    return Array.prototype.map.call(form.querySelectorAll('input[name="' + name + '"]:checked'), function (i) { return i.value; });
  }
  function anyOf(selected, have) {
    if (!selected.length) return true;
    return selected.some(function (v) { return have.indexOf(v) >= 0; });
  }
  function readFilters() {
    var w = parseInt(windowSel.value, 10), k = parseInt(slider.value, 10);
    return { claimants: checked("claimant"), types: checked("t"), domains: checked("d"), issues: checked("i"),
             target: targetSel ? targetSel.value : "", from: w ? Math.max(0, k - w + 1) : 0, to: k, w: w };
  }
  function matches(e, f) {
    if (f.claimants.indexOf(e.c) < 0) return false;
    if (!anyOf(f.types, e.t) || !anyOf(f.domains, e.d) || !anyOf(f.issues, e.i)) return false;
    if (f.target && e.g.indexOf(f.target) < 0) return false;
    return e.ms <= f.to && e.me >= f.from;
  }

  // ---- rendering -------------------------------------------------------------------------------
  function el(tag, cls, text, parent) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }
  function dateLabel(e) {
    if (e.dp === "year") return e.ds.slice(0, 4);
    if (e.dp === "month") return MONTHS[parseInt(e.ds.slice(5, 7), 10) - 1] + " " + e.ds.slice(0, 4);
    return e.ds + (e.de && e.de !== e.ds ? " to " + e.de : "");
  }
  function eventRow(e, parent) {
    var li = el("li", "event-row", undefined, parent);
    var head = el("div", "event-row-head", undefined, li);
    el("span", "case-claimant", NAMES[e.c] || e.c, head).setAttribute("data-code", e.c);
    el("span", "event-date", dateLabel(e), head);
    var a = el("a", "case-id", e.m, head);
    a.href = "cases/" + e.m + ".html";
    var pills = el("span", "case-types", undefined, head);
    e.t.forEach(function (t) { el("span", "type-pill", TYPE_LABELS[t] || t, pills).setAttribute("data-type", t); });
    el("p", "event-summary", (e.n ? e.n + ". " : "") + (e.s || "(no summary)"), li);
    var meta = el("p", "event-meta", undefined, li);
    meta.textContent = (e.lat !== undefined ? (e.lp === "feature" ? "At a named feature" : "Position known") : "Sub-region " + e.sr.map(function (s) { return s + " " + SR_NAMES[s]; }).join(", ")) +
      (e.src ? " · " + e.src + (e.src === 1 ? " source" : " sources") : "") + (e.seed ? " · from MATS" : "");
    return li;
  }
  function popupFor(group) {
    var box = el("div", "event-popup");
    if (group.length > 1) el("p", "popup-head", group.length + " events here", box);
    var ol = el("ol", "event-list popup-list", undefined, box);
    group.slice(0, 12).forEach(function (e) { eventRow(e, ol); });
    if (group.length > 12) el("p", "popup-more", "and " + (group.length - 12) + " more; narrow the time window", box);
    return box;
  }
  function render() {
    var f = readFilters();
    var hits = EVENTS.filter(function (e) { return matches(e, f); });
    clearMarkers();
    var stacks = {}, order = [];
    var srCounts = {}, placed = 0;
    hits.forEach(function (e) {
      if (e.lat !== undefined) {
        placed++;
        var key = e.lat + "," + e.lon;
        if (!stacks[key]) { stacks[key] = []; order.push(key); }
        stacks[key].push(e);
      } else {
        e.sr.forEach(function (s) { srCounts[s] = (srCounts[s] || 0) + 1; });
      }
    });
    order.forEach(function (key) {
      var g = stacks[key];
      var codes = g.map(function (e) { return e.c; }).filter(function (c, i, a) { return a.indexOf(c) === i; });
      var size = Math.min(34, 14 + Math.round(5 * Math.sqrt(g.length - 1)));
      var el = document.createElement("span");
      el.className = "evt" + (g.every(function (e) { return e.lp === "feature"; }) ? " feature" : "") + (codes.length > 1 ? " mixed" : "");
      el.setAttribute("data-code", codes.length === 1 ? codes[0] : "");
      el.style.width = el.style.height = size + "px";
      el.textContent = g.length > 1 ? String(g.length) : "";
      var title = g.length === 1 ? (NAMES[g[0].c] || g[0].c) + ", " + dateLabel(g[0]) + (g[0].n ? ", " + g[0].n : "") : g.length + " events" + (g[0].n ? " at " + g[0].n : "");
      addMarker([g[0].lon, g[0].lat], el, title, function () { return popupFor(g); });
    });
    Object.keys(srCounts).forEach(function (s) {
      if (!srCenters[s]) return;
      var n = srCounts[s];
      var el = document.createElement("span");
      el.className = "sr-count";
      el.textContent = String(n);
      var title = n + (n === 1 ? " event" : " events") + " in sub-region " + s + " " + SR_NAMES[s] + " without a point";
      var inSr = hits.filter(function (e) { return e.lat === undefined && e.sr.indexOf(s) >= 0; });
      addMarker(srCenters[s], el, title, function () { return popupFor(inSr); });
    });
    var when = f.w ? (f.w === 1 ? monthName(f.to) : monthName(f.from) + " – " + monthName(f.to)) : "through " + monthName(f.to);
    timeLabel.value = when;
    slider.setAttribute("aria-valuetext", when);
    countEl.textContent = hits.length + (hits.length === 1 ? " event " : " events ") + when + ": " + placed + " placed, " + (hits.length - placed) + " by sub-region" +
      (hits.length < EVENTS.length ? " (of " + EVENTS.length + " in all)" : "");
    listEl.textContent = "";
    if (!listEl.hidden) hits.slice(0, 400).forEach(function (e) { eventRow(e, listEl); });
    if (!listEl.hidden && hits.length > 400) el("li", "popup-more", "showing the first 400; narrow the filters", listEl);
  }

  var timer = null;
  function schedule() { clearTimeout(timer); timer = setTimeout(render, 60); }
  form.addEventListener("change", schedule);
  slider.addEventListener("input", schedule);
  windowSel.addEventListener("change", schedule);
  var resetBtn = document.getElementById("reset");   // the home page's compact row has none
  if (resetBtn) resetBtn.addEventListener("click", function () {
    form.querySelectorAll('input[type="checkbox"]').forEach(function (i) { i.checked = i.name === "claimant"; });
    if (targetSel) targetSel.value = "";
    windowSel.value = "0";
    slider.value = slider.max;
    stopPlay();
    render();
  });
  var listToggle = document.getElementById("list-toggle");
  listToggle.addEventListener("click", function () {
    listEl.hidden = !listEl.hidden;
    listToggle.setAttribute("aria-pressed", String(!listEl.hidden));
    render();
  });

  // ---- play ------------------------------------------------------------------------------------
  var playBtn = document.getElementById("play"), playTimer = null;
  function stopPlay() { clearInterval(playTimer); playTimer = null; playBtn.setAttribute("aria-pressed", "false"); playBtn.textContent = "Play"; }
  playBtn.addEventListener("click", function () {
    if (playTimer) { stopPlay(); return; }
    var w = parseInt(windowSel.value, 10);
    if (w === 0) { windowSel.value = "12"; w = 12; }
    var step = w >= 12 ? 12 : 1;
    if (parseInt(slider.value, 10) >= lastMonth) slider.value = String(Math.min(lastMonth, w - 1));
    playBtn.setAttribute("aria-pressed", "true"); playBtn.textContent = "Pause";
    render();
    playTimer = setInterval(function () {
      var k = parseInt(slider.value, 10) + step;
      if (k > lastMonth) { stopPlay(); return; }
      slider.value = String(k);
      render();
    }, 450);
  });

  render();
})();
