/* Between claimants (ticket 44): how claimants direct their moves at one another, on the homepage's
   measure. A five-year window (or all years); each move weighted by its highest type, declarative 1,
   demonstrative 2, coercive 3, force 4; scales fixed across every window, shown on a square-root ramp; an
   arrow for a change of a fifth or more against the five years before. A move counts for a pair when its
   dyads name the other claimant; moves aimed at all claimants are counted in the lists (in grey) but left
   out of the share coded coercive or force and off the map. Under SMALL_N moves no share is given.
   The page of all pairs (mode "all") draws a line per pair, or a chosen claimant's arrows; a pair's page
   (mode "pair") shades the ten sub-regions and fills the tabs below the map. */
(function () {
  "use strict";
  var src = document.getElementById("bcdata");
  if (!src || !document.getElementById("bc-map")) return;
  var D = JSON.parse(src.textContent);
  // a pair's page can be read either way round: "-rev" puts the second claimant first (the swap button)
  var REV = D.mode === "pair" && /-rev(?:-|$)/.test(location.hash);
  if (REV) { var t0 = D.pair.a; D.pair.a = D.pair.b; D.pair.b = t0; }
  var NAMES = D.names, SPAN = D.span, ENDS = D.ends, FIRST = ENDS[0], LAST = ENDS[ENDS.length - 1], FIRST_YEAR = FIRST - SPAN + 1;
  var MOVES = D.moves, PAIR = D.mode === "pair" ? D.pair : null, SMALL = D.small_n || 10, MATS_END = D.mats_last_year;
  var TYPES = ["declarative", "demonstrative", "coercive", "force"], TL = D.type_labels || {};
  var CHANGE = 0.2;
  var CODES = Object.keys(NAMES);
  var css = getComputedStyle(document.documentElement);
  var RAMP = (css.getPropertyValue("--seq") || "#cde2fb, #9ec5f4, #6da7ec, #3987e5, #256abf, #184f95, #0d366b").split(",").map(function (s) { return s.trim(); });
  var COL = {};
  CODES.forEach(function (c) { COL[c] = (css.getPropertyValue("--" + c.toLowerCase()) || "#5d6b76").trim() || "#5d6b76"; });
  var ROOT = PAIR ? "../" : "";

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function key(a, b) { return a < b ? a + "|" + b : b + "|" + a; }
  function fmt(v) { return Math.round(v * 10) / 10 === Math.round(v) ? String(Math.round(v)) : (Math.round(v * 10) / 10).toFixed(1); }
  var APART = {}, SLUG = {}, TITLE = {};
  D.pairs.forEach(function (p) { var k = key(p.a, p.b); if (p.apart) APART[k] = 1; SLUG[k] = p.slug; TITLE[k] = p.title; });

  // ---- colours: the homepage's ramp ------------------------------------------------------------------
  function hex(h) { h = h.replace("#", ""); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; }
  var RGB = RAMP.map(hex);
  function rampAt(t) {
    t = Math.max(0, Math.min(1, t)) * (RGB.length - 1);
    var i = Math.min(Math.floor(t), RGB.length - 2), f = t - i, a = RGB[i], b = RGB[i + 1];
    return "rgb(" + [0, 1, 2].map(function (k) { return Math.round(a[k] + (b[k] - a[k]) * f); }).join(",") + ")";
  }
  document.querySelectorAll(".bc-ramp").forEach(function (r) { r.style.background = "linear-gradient(to right, " + RAMP.join(", ") + ")"; });

  // ---- the moves, per year, per direction -------------------------------------------------------------
  // DIR[a][b][y] = {w, n, d, m, c, f} for moves by a directed at b; ALLC[a][y] = {n, ...} for a's moves aimed at all
  var DIR = {}, ALLC = {};
  CODES.forEach(function (a) { DIR[a] = {}; ALLC[a] = {}; CODES.forEach(function (b) { if (a !== b) DIR[a][b] = {}; }); });
  function bump(o, y, m) {
    var r = o[y] || (o[y] = { w: 0, n: 0, declarative: 0, demonstrative: 0, coercive: 0, force: 0 });
    r.w += m.w; r.n += 1; r[m.t] += 1;
  }
  MOVES.forEach(function (m) {
    if (!DIR[m.c]) return;
    m.to.forEach(function (b) { if (DIR[m.c][b]) bump(DIR[m.c][b], m.y, m); });
    if (m.a) bump(ALLC[m.c], m.y, m);
  });
  // the page opens on the latest five years with moves in them (for a pair, moves between the two); a pair
  // with none yet opens on the latest years
  var OWN = PAIR ? MOVES.filter(function (m) { return (m.c === PAIR.a && m.to.indexOf(PAIR.b) >= 0) || (m.c === PAIR.b && m.to.indexOf(PAIR.a) >= 0); }) : MOVES;
  var LAST_WITH = OWN.length ? Math.max.apply(null, OWN.map(function (m) { return m.y; })) : LAST;
  var START = Math.min(Math.max(LAST_WITH, FIRST), LAST);

  var state = { end: START, all: false, who: "ALL", dir: "to", pdir: "both", coer: false, shared: true, tab: "time" };
  function from(end) { return state.all ? FIRST_YEAR : end - SPAN + 1; }
  function sumYears(o, lo, hi) {
    var s = { w: 0, n: 0, declarative: 0, demonstrative: 0, coercive: 0, force: 0 };
    for (var y = lo; y <= hi; y++) { var r = o[y]; if (r) { s.w += r.w; s.n += r.n; TYPES.forEach(function (t) { s[t] += r[t]; }); } }
    return s;
  }
  function dirWin(a, b, end) { return sumYears(DIR[a][b], from(end), end); }
  function allWin(a, end, b) {   // a's moves aimed at all claimants, not already directed at b
    var lo = from(end), s = { n: 0, declarative: 0, demonstrative: 0, coercive: 0, force: 0 };
    MOVES.forEach(function (m) {
      if (m.c === a && m.a && m.y >= lo && m.y <= end && m.to.indexOf(b) < 0) { s.n += 1; s[m.t] += 1; }
    });
    return s;
  }
  function add(x, y) { var s = { w: x.w + y.w, n: x.n + y.n }; TYPES.forEach(function (t) { s[t] = x[t] + y[t]; }); return s; }
  function pairWin(a, b, end) { return add(dirWin(a, b, end), dirWin(b, a, end)); }
  function share(s) { return s.n >= SMALL ? Math.round(100 * (s.coercive + s.force) / s.n) + "% coercive or force" : (s.n ? "few moves" : "no moves"); }
  function shareShort(s) { return s.n >= SMALL ? Math.round(100 * (s.coercive + s.force) / s.n) + "%" : (s.n ? "few moves" : "–"); }
  function arrow(now, prev) {
    if (state.all || prev == null) return "";
    return now > prev * (1 + CHANGE) && now - prev >= 1 ? "▲" : now < prev * (1 - CHANGE) && prev - now >= 1 ? "▼" : "";
  }
  function prevEnd() { return state.all || state.end - SPAN < FIRST ? null : state.end - SPAN; }
  function windowText() { return state.all ? FIRST_YEAR + "–" + LAST : (state.end - SPAN + 1) + "–" + state.end; }
  // fixed scales: the highest score over every window (and over all years, for that switch)
  var MAXP = 0, MAXD = 0, MAXALLP = 0, MAXALLD = 0;
  (function () {
    var keep = state.all;
    state.all = false;
    CODES.forEach(function (a) {
      CODES.forEach(function (b) {
        if (a === b) return;
        ENDS.forEach(function (e) { var d = dirWin(a, b, e).w; if (d > MAXD) MAXD = d; if (a < b) { var p = pairWin(a, b, e).w; if (p > MAXP) MAXP = p; } });
      });
    });
    state.all = true;
    CODES.forEach(function (a) {
      CODES.forEach(function (b) {
        if (a === b) return;
        var d = dirWin(a, b, LAST).w; if (d > MAXALLD) MAXALLD = d;
        if (a < b) { var p = pairWin(a, b, LAST).w; if (p > MAXALLP) MAXALLP = p; }
      });
    });
    state.all = keep;
  })();

  // ---- the map -----------------------------------------------------------------------------------------
  var styleEl = $("mapstyle");
  var STYLE = styleEl ? JSON.parse(styleEl.textContent) : { version: 8, sources: {}, layers: [] };
  function bounds() {
    var w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
    function walk(c) { if (typeof c[0] === "number") { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]); } else c.forEach(walk); }
    D.subregions.features.forEach(function (f) { walk(f.geometry.coordinates); });
    (PAIR ? [PAIR.a, PAIR.b] : CODES).forEach(function (c) { var p = D.anchors[c]; if (p) walk(p); });
    return [[w - 0.5, s - 0.5], [e + 0.5, n + 0.5]];
  }
  var SEA = bounds();
  function framing() {   // keep the claimants clear of the card (top right) and the legend (bottom left)
    var wide = window.matchMedia("(min-width: 801px)").matches;
    return wide && !PAIR ? { top: 30, bottom: 60, left: 40, right: 340 } : { top: 30, bottom: 70, left: 30, right: 30 };
  }
  var map = typeof maplibregl === "undefined" ? null : new maplibregl.Map({
    container: "bc-map", style: STYLE, bounds: SEA, fitBoundsOptions: { padding: framing() },
    minZoom: 3, maxZoom: 9, cooperativeGestures: true, attributionControl: false, dragRotate: false, pitchWithRotate: false
  });
  if (map) {
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    map.on("error", function (e) {
      var msg = e && e.error ? String(e.error.message || e.error) : "";
      if (!/tile|sprite|glyph|font|fetch|network|load|status|json|response/i.test(msg)) console.warn("between: " + msg);
    });
    window.addEventListener("resize", function () { map.resize(); map.fitBounds(SEA, { padding: framing(), animate: false }); });
  }
  var ready = false, markers = [];
  function clearMarkers() { markers.forEach(function (m) { m.remove(); }); markers = []; }
  function marker(lnglat, node, anchor, offset) {
    if (!map) return;
    markers.push(new maplibregl.Marker({ element: node, anchor: anchor || "center", offset: offset || [0, 0] }).setLngLat(lnglat).addTo(map));
  }
  function curve(p, q, bend) {   // a gentle arc from p to q, as points
    var dx = q[0] - p[0], dy = q[1] - p[1], L = Math.sqrt(dx * dx + dy * dy) || 1;
    var c = [(p[0] + q[0]) / 2 - dy / L * bend * L, (p[1] + q[1]) / 2 + dx / L * bend * L], pts = [];
    for (var i = 0; i <= 24; i++) { var t = i / 24, u = 1 - t; pts.push([u * u * p[0] + 2 * u * t * c[0] + t * t * q[0], u * u * p[1] + 2 * u * t * c[1] + t * t * q[1]]); }
    return pts;
  }
  function shorten(pts, by) {   // stop an arrow short of its target's dot
    var q = pts[pts.length - 1], out = pts.slice();
    while (out.length > 2) { var r = out[out.length - 2]; if (Math.hypot(r[0] - q[0], r[1] - q[1]) > by) break; out.pop(); }
    return out;
  }
  function head(pts, size) {     // an arrowhead at the end of a line, as a small triangle
    var q = pts[pts.length - 1], r = pts[pts.length - 2], dx = q[0] - r[0], dy = q[1] - r[1], L = Math.sqrt(dx * dx + dy * dy) || 1, ux = dx / L, uy = dy / L;
    var tip = [q[0] + ux * size * 0.7, q[1] + uy * size * 0.7];
    return [[tip, [q[0] - ux * size * 0.5 - uy * size * 0.6, q[1] - uy * size * 0.5 + ux * size * 0.6], [q[0] - ux * size * 0.5 + uy * size * 0.6, q[1] - uy * size * 0.5 - ux * size * 0.6], tip]];
  }
  var EMPTY = { type: "FeatureCollection", features: [] };
  if (map) map.on("load", function () {
    map.addSource("bc-sr", { type: "geojson", data: D.subregions });
    map.addSource("bc-lines", { type: "geojson", data: EMPTY });
    map.addSource("bc-heads", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "bc-sr-fill", type: "fill", source: "bc-sr", paint: { "fill-color": ["coalesce", ["get", "col"], "rgba(0,0,0,0)"], "fill-opacity": PAIR ? 0.85 : 0 } });
    map.addLayer({ id: "bc-sr-line", type: "line", source: "bc-sr", paint: { "line-color": "#8fa3b4", "line-width": 0.8, "line-opacity": PAIR ? 0.9 : 0.45 } });
    map.addLayer({ id: "bc-lines", type: "line", source: "bc-lines", filter: ["!=", ["get", "apart"], 1], layout: { "line-cap": "round", "line-join": "round" },
                   paint: { "line-color": ["get", "col"], "line-width": ["get", "w"], "line-opacity": 0.9 } });
    map.addLayer({ id: "bc-lines-apart", type: "line", source: "bc-lines", filter: ["==", ["get", "apart"], 1], layout: { "line-cap": "round" },
                   paint: { "line-color": "#9aa6b1", "line-width": ["get", "w"], "line-dasharray": [2, 2], "line-opacity": 0.9 } });
    map.addLayer({ id: "bc-heads", type: "fill", source: "bc-heads", paint: { "fill-color": ["get", "col"], "fill-opacity": 0.95 } });
    ready = true;
    render();
  });

  // ---- bars by type ------------------------------------------------------------------------------------
  function bar(s, na, scale) {
    var b = el("span", "bc-bar");
    TYPES.forEach(function (t) { if (s[t]) { var i = el("i", "t-" + t); i.style.width = (s[t] * scale) + "px"; i.title = s[t] + " " + (TL[t] || t).toLowerCase(); b.appendChild(i); } });
    if (na) { var g = el("i", "t-all"); g.style.width = (na * scale) + "px"; g.title = na + " aimed at all claimants"; b.appendChild(g); }
    return b;
  }
  function row(label, s, na, scale) {
    var r = el("div", "bc-row"), h = el("div", "bc-row-head");
    h.appendChild(el("span", "", label));
    h.appendChild(el("span", "", (s.n + (na ? " +" + na : "")) + " · " + shareShort(s)));
    r.appendChild(h); r.appendChild(bar(s, na, scale));
    return r;
  }

  // ---- the page of all pairs -----------------------------------------------------------------------------
  function renderAll() {
    var lines = [], heads = [], prev = prevEnd();
    clearMarkers();
    var card = $("bc-card"); card.textContent = "";
    var maxP = state.all ? MAXALLP : MAXP, maxD = state.all ? MAXALLD : MAXD;
    var shown = state.who === "ALL" ? CODES : [state.who].concat(CODES.filter(function (c) { return c !== state.who; }));
    shown.forEach(function (c) {
      var p = D.anchors[c]; if (!p) return;
      var n = el("div", "bc-node"), dot = el("i"); dot.style.background = COL[c]; n.appendChild(dot); n.appendChild(el("b", "", NAMES[c]));
      marker(p, n, "left", [-8, 0]);
    });
    if (state.who === "ALL") {
      var ranked = [];
      CODES.forEach(function (a, i) {
        CODES.slice(i + 1).forEach(function (b) {
          var s = pairWin(a, b, state.end); if (s.w <= 0) return;
          var k = key(a, b), t = Math.sqrt(s.w / (maxP || 1)), pts = curve(D.anchors[a], D.anchors[b], 0.14);
          var pv = prev == null ? null : pairWin(a, b, prev).w;
          lines.push({ type: "Feature", properties: { w: 1.2 + 6 * t, col: rampAt(0.15 + 0.85 * t), apart: APART[k] ? 1 : 0 }, geometry: { type: "LineString", coordinates: pts } });
          if (!APART[k]) ranked.push({ a: a, b: b, k: k, s: s, ar: arrow(s.w, pv), mid: pts[12] });
        });
      });
      ranked.sort(function (x, y) { return y.s.w - x.s.w; });
      ranked.slice(0, 4).forEach(function (r) { marker(r.mid, el("span", "bc-lab", fmt(r.s.w) + (r.ar ? " " + r.ar : ""))); });
      card.appendChild(el("h2", "", "Highest scores, " + windowText()));
      if (!ranked.length) card.appendChild(el("p", "bc-note", "No moves between claimants in these years."));
      var ol = el("ol", "bc-rank");
      ranked.slice(0, 5).forEach(function (r) {
        var li = el("li"), a = el("a"); a.href = "between-claimants/" + SLUG[r.k] + ".html" + hashFor(true);
        a.appendChild(el("span", "", TITLE[r.k]));
        var right = el("span"); right.appendChild(el("strong", "", fmt(r.s.w) + (r.ar ? " " + r.ar : "")));
        right.appendChild(el("small", "", r.s.n + " move" + (r.s.n === 1 ? "" : "s") + " · " + share(r.s))); a.appendChild(right);
        li.appendChild(a); ol.appendChild(li);
      });
      card.appendChild(ol);
    } else {
      var c = state.who;
      CODES.forEach(function (x) {
        if (x === c) return;
        var a = state.dir === "to" ? c : x, b = state.dir === "to" ? x : c;
        var s = dirWin(a, b, state.end); if (s.w <= 0) return;
        var t = Math.sqrt(s.w / (maxD || 1)), w = 1.2 + 6 * t, col = rampAt(0.15 + 0.85 * t);
        var pts = shorten(curve(D.anchors[a], D.anchors[b], 0.12), 0.45);
        lines.push({ type: "Feature", properties: { w: w, col: col, apart: APART[key(a, b)] ? 1 : 0 }, geometry: { type: "LineString", coordinates: pts } });
        heads.push({ type: "Feature", properties: { col: APART[key(a, b)] ? "#9aa6b1" : col }, geometry: { type: "Polygon", coordinates: head(pts, 0.22 + 0.04 * w) } });
        if (s.n >= 5) marker(pts[Math.floor(pts.length / 2)], el("span", "bc-lab", s.n + " · " + shareShort(s)));
      });
      card.appendChild(el("h2", "", NAMES[c] + ", " + windowText()));
      card.appendChild(el("h3", "", NAMES[c] + "’s moves toward each claimant"));
      CODES.forEach(function (x) { if (x !== c) card.appendChild(row(NAMES[x], dirWin(c, x, state.end), allWin(c, state.end, x).n, 1.8)); });
      card.appendChild(el("h3", "", "Each claimant’s moves toward " + NAMES[c]));
      CODES.forEach(function (x) { if (x !== c) card.appendChild(row(NAMES[x], dirWin(x, c, state.end), allWin(x, state.end, c).n, 1.8)); });
      card.appendChild(el("p", "bc-note", "The figure after each name is the count of moves, + those aimed at all claimants (grey), then the share coded coercive or force (none under " + SMALL + " moves)."));
    }
    if (ready) { map.getSource("bc-lines").setData({ type: "FeatureCollection", features: lines }); map.getSource("bc-heads").setData({ type: "FeatureCollection", features: heads }); }
    var dirBox = $("bc-dir-box");
    if (dirBox) {
      dirBox.hidden = state.who === "ALL";
      if (state.who !== "ALL") { $("bc-dir-to").textContent = NAMES[state.who] + " toward the others"; $("bc-dir-from").textContent = "The others toward " + NAMES[state.who]; }
    }
    var intro = $("bc-intro");
    if (intro) intro.textContent = state.who === "ALL"
      ? "Each line joins two claimants. Its width and shade show the pair’s score over the years chosen: the moves either has directed at the other, weighted by type as on the homepage. ▲ ▼ mark a change of a fifth or more since the five years before."
      : "Arrows show the moves " + (state.dir === "to" ? NAMES[state.who] + " has directed at each claimant" : "each claimant has directed at " + NAMES[state.who]) + ": wider and darker for a higher score. Choose a pair to open its own page.";
    var box = $("bc-table-box"); if (box && box.open) renderTable();
  }
  function renderTable() {
    var host = $("bc-table"); if (!host) return;
    host.textContent = "";
    var t = el("table", "bc-grid"), hr = el("tr"), th0 = el("th"); th0.setAttribute("scope", "col"); hr.appendChild(th0);
    CODES.forEach(function (c) { var th = el("th", "", NAMES[c]); th.setAttribute("scope", "col"); hr.appendChild(th); });
    var thead = el("thead"); thead.appendChild(hr); t.appendChild(thead);
    var tb = el("tbody");
    CODES.forEach(function (a) {
      var tr = el("tr"), th = el("th", "", NAMES[a]); th.setAttribute("scope", "row"); tr.appendChild(th);
      CODES.forEach(function (b) {
        var td = el("td");
        if (a === b) { td.className = "self"; tr.appendChild(td); return; }
        var s = dirWin(a, b, state.end), na = allWin(a, state.end, b).n, link = el("a"); link.href = pairURL(a, b);
        link.appendChild(el("strong", "", String(s.n + na)));
        link.appendChild(bar(s, na, 0.42));
        link.appendChild(el("span", "", s.n >= SMALL ? shareShort(s) + " coercive" : (s.n ? "few moves" : (na ? "all-claimant only" : ""))));
        link.setAttribute("aria-label", NAMES[a] + " toward " + NAMES[b] + ": open the pair’s page");
        td.appendChild(link);
        td.title = NAMES[a] + " toward " + NAMES[b] + ", " + windowText() + ": " + s.n + " directed at " + NAMES[b] + (na ? ", " + na + " aimed at all claimants" : "") + "; " + share(s);
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb); host.appendChild(t);
  }

  // ---- one pair -----------------------------------------------------------------------------------------
  function pairMoves(lo, hi, withAll) {   // the pair's moves in years lo..hi, for the direction chosen
    var a = PAIR.a, b = PAIR.b;
    return MOVES.filter(function (m) {
      if (m.y < lo || m.y > hi) return false;
      var ab = m.c === a && m.to.indexOf(b) >= 0, ba = m.c === b && m.to.indexOf(a) >= 0;
      var dirOK = state.pdir === "both" ? (ab || ba) : state.pdir === "ab" ? ab : ba;
      if (!dirOK) {
        if (!withAll || !m.a) return false;
        var allOK = state.pdir === "both" ? (m.c === a || m.c === b) : state.pdir === "ab" ? m.c === a : m.c === b;
        if (!allOK) return false;
      }
      if (state.coer && m.t !== "coercive" && m.t !== "force") return false;
      return true;
    });
  }
  function isDirected(m) { return (m.c === PAIR.a && m.to.indexOf(PAIR.b) >= 0) || (m.c === PAIR.b && m.to.indexOf(PAIR.a) >= 0); }
  function srScores(lo, hi) {
    var s = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], n = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    pairMoves(lo, hi, false).forEach(function (m) {
      if (!m.sr.length) return;
      var w = state.shared ? m.w / m.sr.length : m.w;
      m.sr.forEach(function (i) { s[i - 1] += w; n[i - 1] += 1; });
    });
    return { s: s, n: n };
  }
  var srMax = { key: null, v: 0 };
  function srScale() {
    var k = [state.all, state.pdir, state.coer, state.shared].join("|");
    if (srMax.key === k) return srMax.v;
    var v = 0;
    if (state.all) v = Math.max.apply(null, srScores(FIRST_YEAR, LAST).s);
    else ENDS.forEach(function (e) { v = Math.max(v, Math.max.apply(null, srScores(e - SPAN + 1, e).s)); });
    srMax = { key: k, v: v };
    return v;
  }
  function counts(list) { var s = { w: 0, n: 0, declarative: 0, demonstrative: 0, coercive: 0, force: 0 }; list.forEach(function (m) { s.w += m.w; s.n += 1; s[m.t] += 1; }); return s; }
  function renderPair() {
    var a = PAIR.a, b = PAIR.b, lo = from(state.end), hi = state.end, pv = prevEnd();
    clearMarkers();
    [a, b].forEach(function (c) {
      var p = D.anchors[c]; if (!p) return;
      var n = el("div", "bc-node"), dot = el("i"); dot.style.background = COL[c]; n.appendChild(dot); n.appendChild(el("b", "", NAMES[c]));
      marker(p, n, "left", [-8, 0]);
    });
    var now = srScores(lo, hi), before = pv == null ? null : srScores(pv - SPAN + 1, pv), top = srScale() || 1;
    var fc = { type: "FeatureCollection", features: D.subregions.features.map(function (f) {
      var i = f.properties.n - 1, v = now.s[i], t = Math.sqrt(v / top);
      var g = JSON.parse(JSON.stringify(f)); g.properties.col = v > 0 ? rampAt(t) : null; return g;
    }) };
    if (ready) map.getSource("bc-sr").setData(fc);
    D.subregions.features.forEach(function (f) {
      var i = f.properties.n - 1, v = now.s[i], t = Math.sqrt(v / top), ar = before ? arrow(v, before.s[i]) : "";
      if (!now.n[i] && !ar) return;   // nothing to say about this sub-region in these years
      var lab = el("span", "bc-count" + (t > 0.6 ? " dark" : ""), now.n[i] + (ar ? " " + ar : ""));
      lab.title = D.subregion_names[String(i + 1)] + ": " + now.n[i] + " moves, score " + fmt(v);
      if (f.properties.lab) marker(f.properties.lab, lab);
    });
    // the side panel's figures
    var sum = $("bc-summary"); sum.textContent = "";
    var keep = state.pdir; state.pdir = "both";
    var both = counts(pairMoves(lo, hi, false));
    var prevBoth = pv == null ? null : counts(pairMoves(pv - SPAN + 1, pv, false));
    state.pdir = keep;
    if (!OWN.length) { sum.appendChild(el("div", "bc-sub", "No moves by either claimant directed at the other are recorded yet. See About the data, below the map.")); renderTab(); return; }
    sum.appendChild(el("div", "bc-big", "Score " + fmt(both.w) + " · " + both.n + " move" + (both.n === 1 ? "" : "s")));
    sum.appendChild(el("div", "bc-sub", windowText() + " · " + share(both) + (prevBoth ? " · " + fmt(prevBoth.w) + " in the five years before" : "")));
    [[a, b], [b, a]].forEach(function (d) {
      var s = dirWin(d[0], d[1], hi), na = allWin(d[0], hi, d[1]).n;
      sum.appendChild(row(NAMES[d[0]] + " → " + NAMES[d[1]], s, na, 3));
    });
    sum.appendChild(el("p", "bc-intro", "Bars run declarative to force, light to dark; grey (+) is moves aimed at all claimants, counted but left out of the share and the map. Under " + SMALL + " moves no share is given."));
    renderTab();
  }
  var SVGNS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs) { var e = document.createElementNS(SVGNS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); return e; }
  var TCOL = {}; TYPES.forEach(function (t) { TCOL[t] = (css.getPropertyValue("--t-" + t) || "#3987e5").trim(); });
  function renderTab() {
    var p = $("bc-p-" + state.tab); if (!p) return;
    if (state.tab === "time") timeTab(p);
    else if (state.tab === "long") longTab(p);
    else if (state.tab === "where") whereTab(p);
    else if (state.tab === "moves") movesTab(p);
  }
  function yearAxis(g, x0, bw, y, years) {
    years.forEach(function (yr, i) { if (yr % 10 === 0) { var t = svg("text", { x: x0 + i * bw, y: y, "font-size": 11, fill: "#5d6b76" }); t.textContent = yr; g.appendChild(t); } });
  }
  function timeTab(p) {
    p.textContent = "";
    var a = PAIR.a, b = PAIR.b, years = [], U = 6, BW = 14, X0 = 8, MID = 92;
    for (var y = FIRST_YEAR; y <= LAST; y++) years.push(y);
    var W = X0 + years.length * BW + 140, H = 200, s = svg("svg", { width: W, height: H, viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Moves per year by type: those " + NAMES[a] + " directed at " + NAMES[b] + " above the line, those " + NAMES[b] + " directed at " + NAMES[a] + " below; the years chosen are shaded" });
    var lo = from(state.end), hi = state.end;
    s.appendChild(svg("rect", { x: X0 + (lo - FIRST_YEAR) * BW - 1, y: 4, width: (hi - lo + 1) * BW + 1, height: H - 28, fill: "#e6f1f2" }));
    s.appendChild(svg("line", { x1: X0, y1: MID, x2: X0 + years.length * BW, y2: MID, stroke: "#0c1a2a" }));
    years.forEach(function (yr, i) {
      [[a, b, -1], [b, a, 1]].forEach(function (d) {
        var r = DIR[d[0]][d[1]][yr], h0 = 0, x = X0 + i * BW + 1;
        if (r) TYPES.forEach(function (t) {
          if (!r[t]) return; var h = r[t] * U;
          s.appendChild(svg("rect", { x: x, y: d[2] < 0 ? MID - h0 - h : MID + h0, width: BW - 2, height: h - 1, fill: TCOL[t], rx: 1.5 })); h0 += h;
        });
        var al = 0; MOVES.forEach(function (m) { if (m.c === d[0] && m.a && m.y === yr && m.to.indexOf(d[1]) < 0) al++; });
        for (var j = 0; j < al; j++) s.appendChild(svg("rect", { x: x, y: d[2] < 0 ? MID - h0 - (j + 1) * U : MID + h0 + j * U, width: BW - 2, height: U - 1, fill: "#d3d9de", rx: 1.5 }));
      });
      var hit = svg("rect", { x: X0 + i * BW, y: 0, width: BW, height: H - 20, fill: "transparent", style: "cursor:pointer" });
      var tt = svg("title", {}); tt.textContent = yr; hit.appendChild(tt);
      hit.addEventListener("click", function () { if (!state.all) { setEnd(Math.max(FIRST, Math.min(LAST, yr + 2))); } });
      s.appendChild(hit);
    });
    yearAxis(s, X0, BW, H - 6, years);
    var la = svg("text", { x: X0 + years.length * BW + 8, y: 20, "font-size": 12, fill: "#0c1a2a" }); la.textContent = NAMES[a] + " → " + NAMES[b]; s.appendChild(la);
    var lb = svg("text", { x: X0 + years.length * BW + 8, y: H - 30, "font-size": 12, fill: "#0c1a2a" }); lb.textContent = NAMES[b] + " → " + NAMES[a]; s.appendChild(lb);
    p.appendChild(s);
    if (!OWN.length) p.appendChild(el("p", "bc-note", "No moves between the two are recorded yet."));
    p.appendChild(el("p", "bc-note", "Each block is a move, coloured by type from declarative (light) to force (dark); grey blocks are moves aimed at all claimants. Choose a year to move the five years there."));
  }
  function longTab(p) {
    p.textContent = "";
    var a = PAIR.a, b = PAIR.b, years = [], BW = 14, X0 = 8, base = 170, H = 190;
    for (var y = FIRST_YEAR; y <= LAST; y++) years.push(y);
    function inForce(x, z, upper) {
      return years.map(function (yr) {
        var n = 0;
        MOVES.forEach(function (m) {
          if (m.c !== x || m.to.indexOf(z) < 0) return;
          var end = upper && m.cb === "chubb" && m.o === MATS_END ? LAST : m.o;
          if (m.y <= yr && yr <= end) n++;
        });
        return n;
      });
    }
    var series = [[a, b, inForce(a, b, false), inForce(a, b, true), "#1c5cab"], [b, a, inForce(b, a, false), inForce(b, a, true), "#5d6b76"]];
    var top = Math.max(1, Math.max.apply(null, series[0][3].concat(series[1][3]))), sc = (base - 20) / top;
    var W = X0 + years.length * BW + 150, s = svg("svg", { width: W, height: H, viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Moves each side had in force each year" });
    s.appendChild(svg("line", { x1: X0, y1: base, x2: X0 + years.length * BW, y2: base, stroke: "#c9d0d6" }));
    series.forEach(function (S, k) {
      function pts(v) { return v.map(function (n, i) { return (X0 + i * BW + BW / 2).toFixed(1) + "," + (base - n * sc).toFixed(1); }).join(" "); }
      s.appendChild(svg("polyline", { points: pts(S[3]), fill: "none", stroke: S[4], "stroke-width": 1.5, "stroke-dasharray": "5 4" }));
      s.appendChild(svg("polyline", { points: pts(S[2]), fill: "none", stroke: S[4], "stroke-width": 2 }));
      var t = svg("text", { x: X0 + years.length * BW + 8, y: 20 + k * 16, "font-size": 12, fill: S[4], "font-weight": 600 }); t.textContent = NAMES[S[0]] + " → " + NAMES[S[1]]; s.appendChild(t);
    });
    yearAxis(s, X0, BW, H - 4, years);
    p.appendChild(s);
    p.appendChild(el("p", "bc-note", "Solid: the moves each side had in force each year, from a move’s year to its last recorded year. Dashed: an upper bound, counting every move whose end is still to be re-checked as still running."));
  }
  function whereTab(p) {
    p.textContent = "";
    var lo = from(state.end), hi = state.end, a = PAIR.a, b = PAIR.b, rows = [];
    var now = srScores(lo, hi);
    for (var i = 1; i <= 10; i++) {
      var ab = 0, ba = 0, mix = { w: 0, n: 0, declarative: 0, demonstrative: 0, coercive: 0, force: 0 };
      pairMoves(lo, hi, false).forEach(function (m) { if (m.sr.indexOf(i) < 0) return; if (m.c === a) ab++; else ba++; mix.n++; mix[m.t]++; });
      rows.push({ i: i, ab: ab, ba: ba, mix: mix, s: now.s[i - 1] });
    }
    rows.sort(function (x, y) { return y.s - x.s || y.mix.n - x.mix.n || x.i - y.i; });
    var t = el("table", "bc-where"), hr = el("tr");
    ["Sub-region", NAMES[a] + " → " + NAMES[b], NAMES[b] + " → " + NAMES[a], "Score", "Mix by type", "Coercive or force"].forEach(function (h, k) {
      var th = el("th", k === 1 || k === 2 || k === 3 ? "num" : (k === 5 ? "num" : ""), h); th.setAttribute("scope", "col"); hr.appendChild(th);
    });
    var thead = el("thead"); thead.appendChild(hr); t.appendChild(thead);
    var tb = el("tbody");
    rows.forEach(function (r) {
      var tr = el("tr");
      tr.appendChild(el("td", "", r.i + " " + D.subregion_names[String(r.i)]));
      tr.appendChild(el("td", "num", String(r.ab))); tr.appendChild(el("td", "num", String(r.ba)));
      tr.appendChild(el("td", "num", fmt(r.s)));
      var c = el("td", "bar"); c.appendChild(bar(r.mix, 0, 2.4)); tr.appendChild(c);
      tr.appendChild(el("td", "num", shareShort(r.mix)));
      tb.appendChild(tr);
    });
    t.appendChild(tb); p.appendChild(t);
    p.appendChild(el("p", "bc-note", windowText() + ". A move can touch several sub-regions, so the counts can add up to more than the pair’s moves. The score " + (state.shared ? "shares each move’s weight among its sub-regions" : "counts each move in full on every sub-region") + ", as the switch beside the map sets."));
  }
  function movesTab(p) {
    p.textContent = "";
    var lo = from(state.end), hi = state.end, list = pairMoves(lo, hi, true).slice().sort(function (x, y) { return y.y - x.y || (x.m < y.m ? 1 : -1); });
    if (!list.length) { p.appendChild(el("p", "", "No moves in " + windowText() + ".")); return; }
    var ul = el("ul", "bc-moves");
    list.forEach(function (m) {
      var li = el("li"), a = el("a"); a.href = ROOT + "cases/" + m.m + ".html";
      var dot = el("i"); dot.style.background = isDirected(m) ? TCOL[m.t] : "#d3d9de"; a.appendChild(dot);
      var txt = el("span");
      var other = m.c === PAIR.a ? PAIR.b : PAIR.a;
      txt.appendChild(el("small", "", m.y + " · " + m.m + " · " + NAMES[m.c] + (isDirected(m) ? " → " + NAMES[other] : ", aimed at all claimants") + " · " + (TL[m.t] || m.t)));
      txt.appendChild(document.createTextNode(m.x + (m.x.length >= 220 ? "…" : "")));
      a.appendChild(txt); li.appendChild(a); ul.appendChild(li);
    });
    p.appendChild(ul);
  }
  function setTab(t) {
    state.tab = t;
    ["time", "long", "where", "moves", "episodes", "about"].forEach(function (k) {
      var b = $("bc-t-" + k), panel = $("bc-p-" + k); if (!b || !panel) return;
      b.setAttribute("aria-selected", k === t ? "true" : "false"); b.tabIndex = k === t ? 0 : -1; panel.hidden = k !== t;
    });
    renderTab(); remember();
  }
  ["time", "long", "where", "moves", "episodes", "about"].forEach(function (k, i, all) {
    var b = $("bc-t-" + k); if (!b) return;
    b.addEventListener("click", function () { setTab(k); });
    b.addEventListener("keydown", function (e) {
      var j = e.key === "ArrowRight" ? (i + 1) % all.length : e.key === "ArrowLeft" ? (i + all.length - 1) % all.length : -1;
      if (j >= 0) { e.preventDefault(); setTab(all[j]); $("bc-t-" + all[j]).focus(); }
    });
  });

  // ---- time controls -----------------------------------------------------------------------------------
  var slider = $("bc-year"), label = $("bc-label"), play = $("bc-play"), allBox = $("bc-all"), spark = $("bc-spark");
  slider.min = String(FIRST); slider.max = String(LAST); slider.value = String(state.end);
  function sparkScore(end) {
    var keep = state.all; state.all = false; var v = 0;
    if (PAIR) v = pairWin(PAIR.a, PAIR.b, end).w;
    else CODES.forEach(function (a, i) { CODES.slice(i + 1).forEach(function (b) { if (!APART[key(a, b)]) v += pairWin(a, b, end).w; }); });
    state.all = keep; return v;
  }
  var SPARK = ENDS.map(sparkScore), SPARK_MAX = Math.max.apply(null, SPARK.concat([1]));
  ENDS.forEach(function (e, i) {
    var b = el("button"); b.type = "button"; b.style.height = Math.max(2, Math.round(38 * SPARK[i] / SPARK_MAX)) + "px";
    b.setAttribute("aria-label", "Five years to " + e + ": score " + fmt(SPARK[i])); b.title = (e - SPAN + 1) + "–" + e;
    b.addEventListener("click", function () { state.all = false; allBox.checked = false; setEnd(e); });
    spark.appendChild(b);
  });
  function paintTime() {
    label.textContent = windowText();
    var lg = $("bc-time-legend"); if (lg) lg.textContent = state.all ? "All years" : "Five years to";
    slider.value = String(state.end); slider.disabled = state.all; play.disabled = state.all;
    Array.prototype.forEach.call(spark.children, function (b, i) { b.className = !state.all && ENDS[i] === state.end ? "on" : ""; });
  }
  function setEnd(e) { state.end = e; render(); }
  slider.addEventListener("input", function () { setEnd(parseInt(slider.value, 10)); });
  allBox.addEventListener("change", function () { state.all = allBox.checked; stopPlay(); render(); });
  var timer = null;
  function stopPlay() { if (timer) { clearInterval(timer); timer = null; } play.setAttribute("aria-pressed", "false"); play.textContent = "▶"; }
  play.addEventListener("click", function () {
    if (timer) { stopPlay(); return; }
    if (state.end >= LAST) state.end = FIRST;
    play.setAttribute("aria-pressed", "true"); play.textContent = "❚❚";
    timer = setInterval(function () { if (state.end >= LAST) { stopPlay(); return; } setEnd(state.end + 1); }, 700);
  });

  // ---- what is shown -------------------------------------------------------------------------------------
  // what is shown: two short choices and a swap (rounds 1-3 of the design). All claimants: every pair;
  // one claimant and "all others": its arrows; two claimants: their own page
  var first = $("bc-first"), second = $("bc-second"), swap = $("bc-swap");
  function pairURL(a, b) { return ROOT + "between-claimants/" + SLUG[key(a, b)] + ".html" + hashFor(true) + (SLUG[key(a, b)] && NAMES[a] > NAMES[b] ? "-rev" : ""); }
  function paintPick() {
    var a = PAIR ? PAIR.a : state.who, b = PAIR ? PAIR.b : "ALL";
    first.value = a; second.value = b;
    second.disabled = a === "ALL";
    Array.prototype.forEach.call(second.options, function (o) { o.disabled = o.value !== "ALL" && o.value === a; });
    swap.disabled = !PAIR;
  }
  function pick() {
    var a = first.value, b = second.value;
    if (a === "ALL") { if (PAIR) location.href = ROOT + "between-claimants.html" + hashFor(true); else { state.who = "ALL"; render(); } return; }
    if (b === "ALL" || b === a) { if (PAIR) location.href = ROOT + "between-claimants.html" + hashFor(true) + "-c-" + a.toLowerCase(); else { state.who = a; render(); } return; }
    location.href = pairURL(a, b);
  }
  first.addEventListener("change", function () { if (first.value === second.value) second.value = "ALL"; pick(); });
  second.addEventListener("change", pick);
  swap.addEventListener("click", function () { if (PAIR) { location.hash = hashFor(false).replace(/-rev/, "") + (REV ? "" : "-rev"); location.reload(); } });
  Array.prototype.forEach.call(document.querySelectorAll('input[name="bc-dir"]'), function (r) { r.addEventListener("change", function () { if (r.checked) { state.dir = r.value; render(); } }); });
  Array.prototype.forEach.call(document.querySelectorAll('input[name="bc-pdir"]'), function (r) { r.addEventListener("change", function () { if (r.checked) { state.pdir = r.value; render(); } }); });
  var coer = $("bc-coer"), shared = $("bc-shared");
  if (coer) coer.addEventListener("change", function () { state.coer = coer.checked; render(); });
  if (shared) shared.addEventListener("change", function () { state.shared = shared.checked; render(); });
  var tableBox = $("bc-table-box");
  if (tableBox) tableBox.addEventListener("toggle", function () { if (tableBox.open) renderTable(); });

  // ---- the view in the address: #y2026[-all][-c-cn][-from] on the page of all pairs, #y2026[-all][-d-ab][-co][-full][-tab-where] on a pair's
  function hashFor(timeOnly) {
    var h = "#y" + state.end + (state.all ? "-all" : "");
    if (timeOnly) return h;
    if (!PAIR) { if (state.who !== "ALL") h += "-c-" + state.who.toLowerCase() + (state.dir === "from" ? "-from" : ""); }
    else { if (state.pdir !== "both") h += "-d-" + state.pdir; if (state.coer) h += "-co"; if (!state.shared) h += "-full"; if (state.tab !== "time") h += "-tab-" + state.tab; if (REV) h += "-rev"; }
    return h;
  }
  function readHash() {
    var m = /^#y(\d{4})(-all)?(?:-c-([a-z]{2}))?(-from)?(?:-d-(ab|ba))?(-co)?(-full)?(?:-tab-(time|long|where|moves|episodes|about))?(-rev)?$/.exec(location.hash);
    if (!m) return;
    var y = parseInt(m[1], 10); if (y >= FIRST && y <= LAST) state.end = y;
    state.all = !!m[2];
    if (!PAIR && m[3] && NAMES[m[3].toUpperCase()]) { state.who = m[3].toUpperCase(); state.dir = m[4] ? "from" : "to"; }
    if (PAIR) { state.pdir = m[5] || "both"; state.coer = !!m[6]; state.shared = !m[7]; if (m[8]) state.tab = m[8]; }
  }
  function remember() {
    if (!history.replaceState) return;
    try { history.replaceState(null, "", hashFor(false)); } catch (e) { /* a sandboxed frame */ }
    var em = $("bc-embed");
    if (em) em.value = '<iframe src="' + location.href.split("#")[0].split("?")[0] + "?embed=1" + hashFor(false) + '" width="100%" height="560" style="border:0" title="' + (PAIR ? PAIR.title + ": " : "") + 'Between claimants, SCS Developments Tracker" loading="lazy"></iframe>';
  }
  var linkBtn = $("bc-link"), linkDone = $("bc-link-done");
  if (linkBtn) linkBtn.addEventListener("click", function () {
    var url = location.href;
    function ok() { linkDone.textContent = "Link copied"; setTimeout(function () { linkDone.textContent = ""; }, 2500); }
    try { navigator.clipboard.writeText(url).then(ok, function () { linkDone.textContent = url; }); } catch (e) { linkDone.textContent = url; }
  });

  function render() {
    paintTime();
    paintPick();
    if (PAIR) renderPair(); else renderAll();
    remember();
  }
  function sync() {   // the controls, from the state
    allBox.checked = state.all;
    paintPick();
    Array.prototype.forEach.call(document.querySelectorAll('input[name="bc-dir"]'), function (r) { r.checked = r.value === state.dir; });
    Array.prototype.forEach.call(document.querySelectorAll('input[name="bc-pdir"]'), function (r) { r.checked = r.value === state.pdir; });
    if (coer) coer.checked = state.coer;
    if (shared) shared.checked = state.shared;
  }
  window.addEventListener("hashchange", function () { readHash(); sync(); if (PAIR) setTab(state.tab); render(); });
  readHash();
  allBox.checked = state.all;
  Array.prototype.forEach.call(document.querySelectorAll('input[name="bc-dir"]'), function (r) { r.checked = r.value === state.dir; });
  Array.prototype.forEach.call(document.querySelectorAll('input[name="bc-pdir"]'), function (r) { r.checked = r.value === state.pdir; });
  if (coer) coer.checked = state.coer;
  if (shared) shared.checked = state.shared;
  if (PAIR) {
    var ab = $("bc-pdir-ab"), ba = $("bc-pdir-ba");
    if (ab) ab.textContent = NAMES[PAIR.a] + " → " + NAMES[PAIR.b];
    if (ba) ba.textContent = NAMES[PAIR.b] + " → " + NAMES[PAIR.a];
    setTab(state.tab);
  }
  paintPick();
  render();
})();
