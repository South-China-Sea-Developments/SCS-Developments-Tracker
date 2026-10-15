/* Event map: dated events as points (or as counts on their sub-region when unplaced), a time
   window scrubbed by month, and the same filter semantics as the case browser. Leaflet draws the
   map; the data is inline (data/events.json has the same content for reuse). */
(function () {
  "use strict";
  var src = document.getElementById("mapdata");
  if (!src || typeof L === "undefined") return;
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
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function monthIndex(iso) { return (parseInt(iso.slice(0, 4), 10) - FIRST) * 12 + parseInt(iso.slice(5, 7), 10) - 1; }
  function monthName(k) { return MONTHS[k % 12] + " " + (FIRST + Math.floor(k / 12)); }
  var lastMonth = Math.max((DATA.last_year - FIRST) * 12 + 11, Math.max.apply(null, EVENTS.map(function (e) { return monthIndex(e.ds); }).concat([0])));
  EVENTS.forEach(function (e) { e.ms = monthIndex(e.ds); e.me = Math.max(e.ms, monthIndex(e.de)); });
  slider.max = String(lastMonth);
  slider.value = String(lastMonth);
  windowSel.value = "0";

  // ---- map -------------------------------------------------------------------------------------
  var map = L.map("map", { minZoom: 4, maxZoom: 11, zoomSnap: 0.5, worldCopyJump: false, attributionControl: true, zoomControl: true });
  map.attributionControl.setPrefix("");
  // OpenStreetMap's standard tiles (ODbL data, attribution required, light use); in dark mode the
  // stylesheet re-tones them. Without network the polygons and events still draw on the page plane.
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  // the polygons are context, not controls: not focusable, labelled once each
  var polygons = L.geoJSON(DATA.subregions, {
    interactive: false,
    style: function () { return { className: "sr-poly", weight: 1, fill: true, fillOpacity: 0.06, opacity: 0.8 }; }
  }).addTo(map);
  map.fitBounds(polygons.getBounds(), { padding: [8, 8] });
  var srCenters = {};
  polygons.eachLayer(function (layer) {
    var n = String(layer.feature.properties.n), c = layer.getBounds().getCenter();
    srCenters[n] = c;
    L.marker(c, { interactive: false, keyboard: false, icon: L.divIcon({ className: "", iconSize: [120, 16], iconAnchor: [60, 30],
      html: '<span class="sr-label">' + n + " " + layer.feature.properties.name + "</span>" }) }).addTo(map);
  });

  var pointLayer = L.layerGroup().addTo(map);
  var countLayer = L.layerGroup().addTo(map);

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
             target: document.getElementById("target").value, from: w ? Math.max(0, k - w + 1) : 0, to: k, w: w };
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
    pointLayer.clearLayers();
    countLayer.clearLayers();
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
      var cls = "evt" + (g.every(function (e) { return e.lp === "feature"; }) ? " feature" : "") + (codes.length > 1 ? " mixed" : "");
      var icon = L.divIcon({ className: "", iconSize: [size, size], iconAnchor: [size / 2, size / 2],
        html: '<span class="' + cls + '" data-code="' + (codes.length === 1 ? codes[0] : "") + '">' + (g.length > 1 ? g.length : "") + "</span>" });
      var title = g.length === 1 ? (NAMES[g[0].c] || g[0].c) + ", " + dateLabel(g[0]) + (g[0].n ? ", " + g[0].n : "") : g.length + " events" + (g[0].n ? " at " + g[0].n : "");
      L.marker([g[0].lat, g[0].lon], { icon: icon, title: title, alt: title, keyboard: true, riseOnHover: true })
        .bindPopup(function () { return popupFor(g); }, { maxWidth: 360, className: "evt-popup" }).addTo(pointLayer);
    });
    Object.keys(srCounts).forEach(function (s) {
      if (!srCenters[s]) return;
      var n = srCounts[s];
      var icon = L.divIcon({ className: "", iconSize: [30, 22], iconAnchor: [15, 11], html: '<span class="sr-count">' + n + "</span>" });
      var title = n + (n === 1 ? " event" : " events") + " known only to sub-region " + s + " " + SR_NAMES[s];
      var inSr = hits.filter(function (e) { return e.lat === undefined && e.sr.indexOf(s) >= 0; });
      L.marker(srCenters[s], { icon: icon, title: title, alt: title, keyboard: true })
        .bindPopup(function () { return popupFor(inSr); }, { maxWidth: 360, className: "evt-popup" }).addTo(countLayer);
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
  document.getElementById("reset").addEventListener("click", function () {
    form.querySelectorAll('input[type="checkbox"]').forEach(function (i) { i.checked = i.name === "claimant"; });
    document.getElementById("target").value = "";
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
