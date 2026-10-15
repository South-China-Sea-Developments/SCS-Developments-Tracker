/* Charts for the overview, issues/domains and sub-regions pages. Plain SVG, no dependencies.
   Figures are declared in the HTML with data-chart attributes; this script projects one view state
   onto them. Data comes from the inline JSON written by the build (so pages also work from disk). */
(function () {
  "use strict";

  var aggEl = document.getElementById("agg");
  if (!aggEl) return;
  var AGG = JSON.parse(aggEl.textContent);
  var YEARS = AGG.years;
  var CLAIMANTS = AGG.claimants;
  var NAMES = AGG.claimant_names || {};
  var DIMS = {
    types: { keys: AGG.types, labels: AGG.type_labels || {}, prefix: "--t-" },
    domains: { keys: AGG.domains || [], labels: AGG.domain_labels || {}, prefix: "--d-" },
    issues: { keys: AGG.issues || [], labels: AGG.issue_labels || {}, prefix: "--i-" }
  };
  var DIM_WORD = { types: "Type", domains: "Domain", issues: "Issue" };
  var LOCS = (AGG.subregions || []).map(function (flag, i) {
    return { flag: flag, n: String(i + 1), name: (AGG.subregion_names || {})[String(i + 1)] || String(i + 1) };
  });

  var CSS = getComputedStyle(document.documentElement);
  function token(name) { return CSS.getPropertyValue(name).trim(); }
  function claimantColor(code) { return token("--" + code.toLowerCase()); }

  var SVG_NS = "http://www.w3.org/2000/svg";
  function el(name, attrs, parent) {
    var node = document.createElementNS(SVG_NS, name);
    for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }
  function html(tag, cls, text, parent) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    if (parent) parent.appendChild(node);
    return node;
  }
  function sum(arr) { return arr.reduce(function (a, b) { return a + b; }, 0); }

  // ---- view state (the DOM is a projection of this, never the source) -----
  var state = {
    selected: {},          // claimant code -> shown? (chip filter pages)
    stackBy: "claimant",   // overview main chart: "claimant" | "type"
    mapClaimant: "ALL",    // sub-regions page: one claimant or ALL
    bin: "all",            // sub-regions map: period key
    tableOn: {},           // figure id -> table view on?
    width: window.innerWidth
  };
  CLAIMANTS.forEach(function (c) { state.selected[c] = true; });

  var BINS = AGG.periods || [{ key: "all", label: "All years", years: YEARS.slice() }];

  // ---- tooltip (one for the page) ---------------------------------------
  var tip = html("div", "tooltip");
  tip.hidden = true;
  document.body.appendChild(tip);
  function showTip(x, y, title, rows, total) {
    tip.textContent = "";
    html("div", "tt-title", title, tip);
    rows.forEach(function (r) {
      var row = html("div", "tt-row", null, tip);
      html("i", null, null, row).style.setProperty("--c", r.color);
      html("b", null, String(r.value), row);
      html("span", null, r.label, row);
    });
    if (total !== undefined) {
      var row = html("div", "tt-row total", null, tip);
      html("i", null, null, row).style.visibility = "hidden";
      html("b", null, String(total), row);
      html("span", null, "total", row);
    }
    tip.hidden = false;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var left = x + 14, top = y + 14;
    if (left + w > window.innerWidth - 8) left = x - w - 14;
    if (top + h > window.innerHeight - 8) top = y - h - 14;
    tip.style.left = (left + window.scrollX) + "px";
    tip.style.top = (top + window.scrollY) + "px";
  }
  function hideTip() { tip.hidden = true; }

  // ---- stacked column chart ---------------------------------------------
  // categories: [{key, label, short}]; series: [{key, label, color, values: {catKey: n}}], first at the bottom.
  function stackedColumns(container, categories, series, opts) {
    container.textContent = "";
    container.classList.remove("is-scrollable");
    var avail = container.clientWidth;
    if (!avail) return null;                         // hidden: render when revealed
    var small = !!opts.small;
    var height = small ? 180 : 300;
    var m = { top: 12, right: 8, bottom: 26, left: 30 };
    var n = categories.length;
    var minBand = opts.yearAxis ? 5 : 28;
    var width = Math.max(avail, n * minBand + m.left + m.right);
    var pw = width - m.left - m.right, ph = height - m.top - m.bottom;
    var band = pw / n;
    var gap = band >= 12 ? 2 : 1;                     // the surface gap between segments and neighbours
    var bar = Math.min(opts.yearAxis ? 24 : 40, Math.max(3, band - gap));

    var totals = categories.map(function (c) { return sum(series.map(function (sr) { return sr.values[c.key] || 0; })); });
    var maxV = Math.max(1, Math.max.apply(null, totals));
    var step = niceStep(maxV, small ? 3 : 5);
    var yMax = Math.ceil(maxV / step) * step;
    function yScale(v) { return m.top + ph - (v / yMax) * ph; }

    var svg = el("svg", { viewBox: "0 0 " + width + " " + height, role: "img", "aria-label": opts.ariaLabel || "" }, container);
    if (opts.describedBy) svg.setAttribute("aria-describedby", opts.describedBy);
    if (width > avail) { svg.style.width = width + "px"; svg.style.maxWidth = "none"; container.classList.add("is-scrollable"); }

    for (var v = 0; v <= yMax; v += step) {
      var y = yScale(v);
      el("line", { x1: m.left, x2: width - m.right, y1: y, y2: y, "class": v === 0 ? "baseline" : "gridline" }, svg);
      if (v > 0) el("text", { x: m.left - 6, y: y + 4, "text-anchor": "end", "class": "tick" }, svg).textContent = String(v);
    }
    var every = opts.yearAxis ? (band < 9 ? 10 : 5) : 1;
    categories.forEach(function (c, i) {
      var show = opts.yearAxis ? (parseInt(c.key, 10) % every === 0) : true;
      if (!show) return;
      var label = opts.yearAxis ? c.label : (band < 64 ? c.short : c.label);
      el("text", { x: m.left + i * band + band / 2, y: height - 8, "text-anchor": "middle", "class": "tick" }, svg).textContent = label;
    });

    categories.forEach(function (c, i) {
      var acc = 0, x = m.left + i * band + (band - bar) / 2, segs = [];
      series.forEach(function (sr) {
        var val = sr.values[c.key] || 0;
        if (!val) return;
        var y1 = yScale(acc + val), y0 = yScale(acc);
        segs.push({ sr: sr, v: val, y: y1, h: Math.max(0, y0 - y1) });
        acc += val;
      });
      var g = el("g", { "class": "col" }, svg);
      segs.forEach(function (s, k) {
        var last = k === segs.length - 1;
        var r = last ? Math.min(4, bar / 2, s.h / 2) : 0;
        el("path", { d: roundedTop(x, s.y, bar, s.h, r), fill: s.sr.color, "class": "seg", "stroke-width": gap }, g);
      });
      // one pointer hit target per category covering the whole band; the table view is the keyboard route
      var hit = el("rect", { x: m.left + i * band, y: m.top, width: band, height: ph, "class": "hit" }, g);
      var rows = segs.slice().reverse().map(function (s) { return { color: s.sr.color, value: s.v, label: s.sr.label }; });
      var title = segs.length ? c.label : c.label + ": none";
      hit.addEventListener("pointerenter", function () { g.classList.add("is-hover"); });
      hit.addEventListener("pointermove", function (ev) { showTip(ev.clientX, ev.clientY, title, rows, segs.length && opts.partsOfWhole ? acc : undefined); });
      hit.addEventListener("pointerleave", function () { g.classList.remove("is-hover"); hideTip(); });
    });
    if (width > avail) container.scrollLeft = width;   // open at the latest categories
    return svg;
  }

  function roundedTop(x, y, w, h, r) {
    if (r <= 0 || h <= 0) return "M" + x + " " + y + "h" + w + "v" + h + "h" + (-w) + "z";
    return "M" + x + " " + (y + r) +
      "a" + r + " " + r + " 0 0 1 " + r + " " + (-r) +
      "h" + (w - 2 * r) +
      "a" + r + " " + r + " 0 0 1 " + r + " " + r +
      "v" + (h - r) + "h" + (-w) + "z";
  }

  function niceStep(maxV, targetTicks) {
    var raw = Math.max(1, maxV / targetTicks);         // counts: never a fractional tick
    var pow = Math.pow(10, Math.floor(Math.log10(raw)));
    var candidates = [1, 2, 5, 10];
    for (var i = 0; i < candidates.length; i++) {
      if (candidates[i] * pow >= raw) return candidates[i] * pow;
    }
    return 10 * pow;
  }

  function legend(series) {
    var lg = html("div", "legend");
    series.forEach(function (sr) {
      var key = html("span", "key", null, lg);
      html("i", null, null, key).style.setProperty("--c", sr.color);
      html("span", null, sr.label, key);
    });
    return lg;
  }

  // table twin: rows = categories, columns = series (+ total when the series are parts of a whole;
  // + a footer when summing down a column is meaningful, i.e. the categories do not overlap)
  function table(container, categories, series, caption, firstHeader, withTotal, withFooter) {
    container.textContent = "";
    var t = html("table", null, null, container);
    html("caption", "sr-only", caption, t);
    var thead = html("thead", null, null, t), tr = html("tr", null, null, thead);
    html("th", null, firstHeader, tr);
    series.forEach(function (sr) { html("th", null, sr.label, tr); });
    if (withTotal) html("th", null, "Total", tr);
    var tbody = html("tbody", null, null, t);
    categories.forEach(function (c) {
      var row = html("tr", null, null, tbody), tot = 0;
      html("td", null, c.label, row);
      series.forEach(function (sr) { var v = sr.values[c.key] || 0; tot += v; html("td", null, String(v), row); });
      if (withTotal) html("td", null, String(tot), row);
    });
    if (withFooter === false) return;
    var foot = html("tfoot", null, null, t), fr = html("tr", null, null, foot), all = 0;
    html("th", null, firstHeader === "Year" ? "All years" : "All", fr);
    series.forEach(function (sr) {
      var s = sum(categories.map(function (c) { return sr.values[c.key] || 0; }));
      all += s; html("td", null, String(s), fr);
    });
    if (withTotal) html("td", null, String(all), fr);
  }

  // ---- data access -------------------------------------------------------
  var YEAR_CATS = YEARS.map(function (y) { return { key: String(y), label: String(y), short: String(y) }; });
  var LOC_CATS = LOCS.map(function (l) { return { key: l.n, label: l.n + " " + l.name, short: l.n }; });
  function shownClaimants() { return CLAIMANTS.filter(function (c) { return state.selected[c]; }); }
  function mapClaimants() { return state.mapClaimant === "ALL" ? CLAIMANTS : [state.mapClaimant]; }
  function perYear(codes, field) {        // {year: sum over codes}
    var out = {};
    YEARS.forEach(function (y) { out[String(y)] = sum(codes.map(function (c) { return AGG.by_claimant[c].years[String(y)][field]; })); });
    return out;
  }
  function perLoc(codes, field) {         // {locNo: sum over codes}
    var out = {};
    LOCS.forEach(function (l) { out[l.n] = sum(codes.map(function (c) { return AGG.by_claimant[c].subregions[l.n][field]; })); });
    return out;
  }
  function dimSeries(dim, valuesFor) {
    var d = DIMS[dim];
    return d.keys.map(function (k) { return { key: k, label: d.labels[k] || k, color: token(d.prefix + k), values: valuesFor(k) }; });
  }
  function claimantSeries(codes) {
    return codes.map(function (c) { return { key: c, label: NAMES[c] || c, color: claimantColor(c), values: perYear([c], "total") }; });
  }

  // ---- figure rendering --------------------------------------------------
  function renderFigure(fig, categories, series, opts) {
    var chart = fig.querySelector(".chart");
    var tv = fig.querySelector(".table-view");
    var btn = fig.querySelector("[data-toggle-table]");
    var old = fig.querySelector(".legend"); if (old) old.remove();
    var tableOn = !!state.tableOn[fig.id];
    chart.classList.toggle("is-hidden", tableOn);
    tv.hidden = !tableOn;
    if (btn) btn.setAttribute("aria-pressed", tableOn ? "true" : "false");
    if (opts.empty) {
      chart.textContent = "";
      html("p", "empty", opts.empty, chart);
      tv.textContent = "";
      if (btn) btn.hidden = true;
      return;
    }
    if (btn) btn.hidden = false;
    table(tv, categories, series, opts.ariaLabel, opts.firstHeader || "Year", !!opts.partsOfWhole, opts.footer !== false);
    if (tableOn) {
      chart.textContent = "";
    } else {
      stackedColumns(chart, categories, series, opts);
      if (series.length > 1) chart.insertAdjacentElement("afterend", legend(series));
    }
  }

  function renderChartFigure(fig) {
    var chart = fig.querySelector(".chart");
    var kind = chart.getAttribute("data-chart");
    var dim = chart.getAttribute("data-dim");
    var scope = chart.getAttribute("data-scope");
    var code = chart.getAttribute("data-claimant") || fig.getAttribute("data-claimant");
    var codes = scope === "map" ? mapClaimants() : code ? [code] : shownClaimants();
    var who = scope === "map" ? (state.mapClaimant === "ALL" ? "all claimants" : NAMES[state.mapClaimant]) : code ? NAMES[code] : "shown claimants";
    var small = fig.classList.contains("small");
    if (code && !state.selected[code] && scope !== "map") { fig.hidden = true; return; }
    fig.hidden = false;
    var total = sum(codes.map(function (c) { return AGG.by_claimant[c].totals.total; }));
    var empty = !codes.length ? "No claimants selected. Pick at least one above."
              : !total ? "No coded moves yet for " + who + "." + (codes.length === 1 ? " Coding for this claimant is in progress." : "") : null;

    if (kind === "all-claimants") {
      var series = state.stackBy === "type"
        ? dimSeries("types", function (k) { return perYear(codes, k); })
        : claimantSeries(codes);
      renderFigure(fig, YEAR_CATS, series, { yearAxis: true, partsOfWhole: true, empty: empty, describedBy: "fig-all-desc",
        ariaLabel: state.stackBy === "type" ? "Assertive moves per year by type, all shown claimants" : "Assertive moves per year by claimant" });
    } else if (kind === "by-type") {
      renderFigure(fig, YEAR_CATS, dimSeries("types", function (k) { return perYear(codes, k); }),
        { yearAxis: true, partsOfWhole: true, small: small, empty: empty, ariaLabel: "Assertive moves per year by type, " + who });
    } else if (kind === "years" && dim === "subregion") {
      var loc = chart.getAttribute("data-loc");
      var name = (AGG.subregion_names || {})[loc] || loc;
      var vals = {};
      YEARS.forEach(function (y) {
        vals[String(y)] = sum(codes.map(function (c) { var cell = AGG.by_claimant[c].subregion_years[loc][String(y)]; return cell ? cell.total : 0; }));
      });
      // one series: the selected claimant's colour, or the default single-series slot when all are shown
      var colour = codes.length === 1 ? claimantColor(codes[0]) : token("--series-1");
      renderFigure(fig, YEAR_CATS, [{ key: loc, label: name, color: colour, values: vals }],
        { yearAxis: true, small: small, empty: empty, ariaLabel: "Moves per year in " + name + ", " + who });
    } else if (kind === "years") {
      renderFigure(fig, YEAR_CATS, dimSeries(dim, function (k) { return perYear(codes, k); }),
        { yearAxis: true, small: small, empty: empty, ariaLabel: DIM_WORD[dim] + " mentions per year, " + who });
    } else if (kind === "subregions") {
      renderFigure(fig, LOC_CATS, dimSeries(dim, function (k) { return perLoc(codes, k); }),
        { small: small, empty: empty, firstHeader: "Sub-region", partsOfWhole: dim === "types", footer: false,
          ariaLabel: (dim === "types" ? "Moves" : DIM_WORD[dim] + " mentions") + " by sub-region, " + who });
    }
  }

  // ---- choropleth --------------------------------------------------------
  // moves in a sub-region over a period, by type, summed over claimants (sparse per-year cells)
  function binCounts(codes, loc, bin) {
    var out = { total: 0 };
    AGG.types.forEach(function (t) { out[t] = 0; });
    bin.years.forEach(function (y) {
      codes.forEach(function (c) {
        var cell = AGG.by_claimant[c].subregion_years[loc.n][String(y)];
        if (!cell) return;
        out.total += cell.total;
        AGG.types.forEach(function (t) { out[t] += cell[t]; });
      });
    });
    return out;
  }
  function ramp() {
    return token("--seq").split(",").map(function (s) { return s.trim(); });
  }
  function luminance(hex) {               // relative luminance of a #rrggbb colour
    var m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
    if (!m) return 1;
    var n = parseInt(m[1], 16);
    var f = function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(n >> 16) + 0.7152 * f((n >> 8) & 255) + 0.0722 * f(n & 255);
  }
  function renderChoropleth(fig) {
    var chart = fig.querySelector(".chart");
    var tv = fig.querySelector(".table-view");
    var btn = fig.querySelector("[data-toggle-table]");
    var tableOn = !!state.tableOn[fig.id];
    chart.classList.toggle("is-hidden", tableOn);
    tv.hidden = !tableOn;
    if (btn) btn.setAttribute("aria-pressed", tableOn ? "true" : "false");
    var codes = mapClaimants();
    var who = state.mapClaimant === "ALL" ? "all claimants" : NAMES[state.mapClaimant];
    var bin = BINS.filter(function (b) { return b.key === state.bin; })[0] || BINS[0];

    // table twin: sub-regions x periods for the chosen claimant(s)
    var periodCats = BINS.slice(1).map(function (b) { return { key: b.key, label: b.label, short: b.label }; });
    var locSeries = LOCS.map(function (l) {
      var vals = {};
      BINS.slice(1).forEach(function (b) { vals[b.key] = binCounts(codes, l, b).total; });
      return { key: l.n, label: l.n + " " + l.name, color: "", values: vals };
    });
    table(tv, periodCats, locSeries, "Moves by sub-region and period, " + who, "Period", false, false);
    var old = fig.querySelector(".legend"); if (old) old.remove();
    if (tableOn) { chart.textContent = ""; return; }

    chart.textContent = "";
    var view = AGG.view || [240, 338];
    var svg = el("svg", { viewBox: "0 0 " + view[0] + " " + view[1], role: "img",
      "aria-label": "Map of the ten sub-regions shaded by moves in " + bin.label + ", " + who }, chart);
    var cells = LOCS.map(function (l) { return binCounts(codes, l, bin); });
    var counts = cells.map(function (c) { return c.total; });
    var maxV = Math.max.apply(null, counts);
    var steps = ramp();
    LOCS.forEach(function (l, i) {
      var v = counts[i];
      var fill = v === 0 || maxV === 0 ? token("--surface") : steps[Math.max(0, Math.ceil((v / maxV) * steps.length) - 1)];
      var p = el("path", { d: AGG.subregion_paths[l.n], "class": "zone", fill: fill }, svg);
      p.setAttribute("data-fill-dark", luminance(fill) < 0.45 ? "1" : "0");
      var rows = AGG.types.map(function (t) { return { color: token("--t-" + t), label: DIMS.types.labels[t] || t, value: cells[i][t] }; })
        .filter(function (r) { return r.value > 0; }).reverse();
      var periodWord = bin.key === "all" ? "all years" : bin.label;
      p.addEventListener("pointerenter", function () { p.classList.add("is-hover"); });
      p.addEventListener("pointermove", function (ev) {
        if (ev.pointerType === "touch") return;
        showTip(ev.clientX, ev.clientY, l.n + " " + l.name + ", " + periodWord, rows, v);
      });
      p.addEventListener("pointerdown", function (ev) {   // a tap keeps the tooltip until the next tap elsewhere
        if (ev.pointerType !== "touch") return;
        ev.stopPropagation();
        showTip(ev.clientX, ev.clientY, l.n + " " + l.name + ", " + periodWord, rows, v);
      });
      p.addEventListener("pointerleave", function (ev) { p.classList.remove("is-hover"); if (ev.pointerType !== "touch") hideTip(); });
    });
    // labels: the sub-region number at the polygon's centroid-ish position (bbox centre)
    LOCS.forEach(function (l, i) {
      var box = svg.querySelectorAll(".zone")[i].getBBox();
      var t = el("text", { x: box.x + box.width / 2, y: box.y + box.height / 2 + 4, "text-anchor": "middle", "class": "zone-label" }, svg);
      t.textContent = l.n;
      if (svg.querySelectorAll(".zone")[i].getAttribute("data-fill-dark") === "1") t.classList.add("on-dark");
    });
    // scale legend: a surface swatch for zero, then the steps up to the busiest sub-region
    var lg = html("div", "legend seq");
    html("span", "seq-end", "0", lg);
    html("i", "zero", null, lg).style.setProperty("--c", token("--surface"));
    steps.forEach(function (s) { html("i", null, null, lg).style.setProperty("--c", s); });
    html("span", "seq-end", String(maxV), lg);
    html("span", "seq-caption", "moves in " + (bin.key === "all" ? "all years" : bin.label) + ", " + who, lg);
    var side = fig.querySelector(".map-side");
    if (side) side.insertAdjacentElement("afterbegin", lg); else chart.insertAdjacentElement("afterend", lg);
  }

  function renderBins() {
    var box = document.getElementById("map-bin");
    if (!box || box.children.length > 1) return;
    BINS.forEach(function (b) {
      var label = html("label", null, null, box);
      var input = html("input", null, null, label);
      input.type = "radio"; input.name = "map-bin"; input.value = b.key; input.checked = b.key === state.bin;
      html("span", null, b.label, label);
      input.addEventListener("change", function () { if (input.checked) { state.bin = b.key; renderAll(); } });
    });
  }

  function renderAll() {
    document.querySelectorAll(".figure").forEach(function (fig) {
      var chart = fig.querySelector(".chart");
      if (!chart) return;
      if (chart.getAttribute("data-chart") === "choropleth") renderChoropleth(fig); else renderChartFigure(fig);
    });
    var note = document.getElementById("filters-note");
    if (note) {
      var sel = shownClaimants();
      var s = sum(sel.map(function (c) { return AGG.by_claimant[c].totals.total; }));
      note.textContent = sel.length === CLAIMANTS.length
        ? s + " moves across all claimants"
        : s + " moves across " + sel.length + " of " + CLAIMANTS.length + " claimants";
    }
  }

  // ---- controls ----------------------------------------------------------
  document.querySelectorAll("#claimant-filter input").forEach(function (box) {
    box.addEventListener("change", function () { state.selected[box.value] = box.checked; renderAll(); });
  });
  document.querySelectorAll("#stack-by input").forEach(function (radio) {
    radio.addEventListener("change", function () { if (radio.checked) { state.stackBy = radio.value; renderAll(); } });
  });
  document.querySelectorAll("#map-claimant input").forEach(function (radio) {
    radio.addEventListener("change", function () { if (radio.checked) { state.mapClaimant = radio.value; renderAll(); } });
  });
  document.querySelectorAll("[data-toggle-table]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-toggle-table");
      state.tableOn[id] = !state.tableOn[id];
      renderAll();
    });
  });
  renderBins();

  var resizeTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      if (window.innerWidth === state.width) return;   // height-only changes (mobile URL bar) need no re-render
      state.width = window.innerWidth;
      renderAll();
    }, 120);
  });
  document.addEventListener("scroll", hideTip, { passive: true });
  document.addEventListener("pointerdown", function (ev) { if (ev.pointerType === "touch") hideTip(); });

  renderAll();
})();
