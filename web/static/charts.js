/* Charts for the overview page. Plain SVG, no dependencies.
   Data comes from the inline JSON written by the build (so the page also works from disk). */
(function () {
  "use strict";

  var aggEl = document.getElementById("agg");
  if (!aggEl) return;
  var AGG = JSON.parse(aggEl.textContent);
  var YEARS = AGG.years;
  var TYPES = AGG.types;
  var CLAIMANTS = AGG.claimants;
  var NAMES = AGG.claimant_names || {};
  var TYPE_LABELS = AGG.type_labels || {};

  var CSS = getComputedStyle(document.documentElement);
  function token(name) { return CSS.getPropertyValue(name).trim(); }
  function claimantColor(code) { return token("--" + code.toLowerCase()); }
  function typeColor(t) { return token("--t-" + t); }

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

  // ---- state -------------------------------------------------------------
  var selected = {};
  CLAIMANTS.forEach(function (c) { selected[c] = true; });

  // ---- tooltip (one for the page) ---------------------------------------
  var tip = html("div", "tooltip");
  tip.hidden = true;
  document.body.appendChild(tip);
  function showTip(x, y, title, rows, total) {
    tip.textContent = "";
    html("div", "tt-title", title, tip);
    rows.forEach(function (r) {
      var row = html("div", "tt-row", null, tip);
      var key = html("i", null, null, row);
      key.style.setProperty("--c", r.color);
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
  // series: [{key, label, color, values: {year: n}}] in stack order (first at the bottom)
  function stackedColumns(container, series, opts) {
    container.textContent = "";
    var avail = Math.max(280, container.clientWidth || 600);
    var small = !!opts.small;
    var height = small ? 180 : 300;
    var m = { top: 12, right: 8, bottom: 26, left: 30 };
    var n = YEARS.length;
    // Never let a year band drop below 8px: the chart grows and the container scrolls instead.
    var minBand = 8;
    var width = Math.max(avail, n * minBand + m.left + m.right);
    var pw = width - m.left - m.right, ph = height - m.top - m.bottom;
    var band = pw / n;
    var gap = band >= 12 ? 2 : 1;               // the surface gap between segments and neighbours
    var bar = Math.min(24, Math.max(3, band - gap));

    var totals = YEARS.map(function (y) {
      return series.reduce(function (s, sr) { return s + (sr.values[y] || 0); }, 0);
    });
    var maxV = Math.max(1, Math.max.apply(null, totals));
    var step = niceStep(maxV, small ? 3 : 5);
    var yMax = Math.ceil(maxV / step) * step;
    function yScale(v) { return m.top + ph - (v / yMax) * ph; }
    function xPos(i) { return m.left + i * band + (band - bar) / 2; }

    var svg = el("svg", { viewBox: "0 0 " + width + " " + height, role: "img", "aria-label": opts.ariaLabel || "" }, container);
    if (width > avail) { svg.style.width = width + "px"; svg.style.maxWidth = "none"; }

    // gridlines and y ticks
    for (var v = 0; v <= yMax; v += step) {
      var y = yScale(v);
      el("line", { x1: m.left, x2: width - m.right, y1: y, y2: y, "class": v === 0 ? "baseline" : "gridline" }, svg);
      if (v > 0) el("text", { x: m.left - 6, y: y + 4, "text-anchor": "end", "class": "tick" }, svg).textContent = String(v);
    }
    // x ticks: every 5 years, or 10 when narrow
    var every = band < 9 ? 10 : 5;
    YEARS.forEach(function (yr, i) {
      if (yr % every === 0 || i === n - 1 && yr % 5 !== 0 && n < 8) {
        el("text", { x: m.left + i * band + band / 2, y: height - 8, "text-anchor": "middle", "class": "tick" }, svg)
          .textContent = String(yr);
      }
    });

    // columns, one group per year; the 2px surface gap is the segment stroke
    YEARS.forEach(function (yr, i) {
      var acc = 0, x = xPos(i), top = null;
      var segs = [];
      series.forEach(function (sr) {
        var v = sr.values[yr] || 0;
        if (!v) return;
        var y1 = yScale(acc + v), y0 = yScale(acc);
        segs.push({ sr: sr, v: v, y: y1, h: Math.max(0, y0 - y1) });
        acc += v;
      });
      var g = el("g", { "class": "col" }, svg);
      segs.forEach(function (s, k) {
        var last = k === segs.length - 1;
        var r = last ? Math.min(4, bar / 2, s.h / 2) : 0;
        var d = roundedTop(x, s.y, bar, s.h, r);
        el("path", { d: d, fill: s.sr.color, "class": "seg", "stroke-width": gap, "data-key": s.sr.key }, g);
      });
      // one hit target per column (never a pinpoint), covering the whole band
      var hit = el("rect", { x: m.left + i * band, y: m.top, width: band, height: ph, "class": "hit", tabindex: "0" }, g);
      hit.setAttribute("aria-label", yr + ": " + acc + " moves");
      var rows = segs.slice().reverse().map(function (s) { return { color: s.sr.color, value: s.v, label: s.sr.label }; });
      var title = segs.length ? String(yr) : yr + ": no moves";
      function onEnter(ev) {
        var p = ev.touches ? ev.touches[0] : ev;
        showTip(p.clientX || 0, p.clientY || 0, title, rows, segs.length ? acc : undefined);
      }
      hit.addEventListener("pointermove", onEnter);
      hit.addEventListener("pointerleave", hideTip);
      hit.addEventListener("focus", function () {
        var b = hit.getBoundingClientRect();
        showTip(b.left + b.width / 2, b.top, title, rows, segs.length ? acc : undefined);
      });
      hit.addEventListener("blur", hideTip);
    });
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
    var raw = maxV / targetTicks;
    var pow = Math.pow(10, Math.floor(Math.log10(raw)));
    var candidates = [1, 2, 5, 10];
    for (var i = 0; i < candidates.length; i++) {
      if (candidates[i] * pow >= raw) return candidates[i] * pow;
    }
    return 10 * pow;
  }

  function legend(container, series) {
    var lg = html("div", "legend", null, container);
    series.forEach(function (sr) {
      var key = html("span", "key", null, lg);
      html("i", null, null, key).style.setProperty("--c", sr.color);
      html("span", null, sr.label, key);
    });
    return lg;
  }

  function table(container, series, caption) {
    container.textContent = "";
    var t = html("table", null, null, container);
    html("caption", "sr-only", caption, t);
    var thead = html("thead", null, null, t), tr = html("tr", null, null, thead);
    html("th", null, "Year", tr);
    series.forEach(function (sr) { html("th", null, sr.label, tr); });
    html("th", null, "Total", tr);
    var tbody = html("tbody", null, null, t);
    YEARS.forEach(function (yr) {
      var row = html("tr", null, null, tbody), tot = 0;
      html("td", null, String(yr), row);
      series.forEach(function (sr) { var v = sr.values[yr] || 0; tot += v; html("td", null, String(v), row); });
      html("td", null, String(tot), row);
    });
    var foot = html("tfoot", null, null, t), fr = html("tr", null, null, foot), all = 0;
    html("th", null, "All years", fr);
    series.forEach(function (sr) {
      var s = YEARS.reduce(function (a, yr) { return a + (sr.values[yr] || 0); }, 0);
      all += s; html("td", null, String(s), fr);
    });
    html("td", null, String(all), fr);
  }

  // ---- series builders ---------------------------------------------------
  function allClaimantsSeries() {
    return CLAIMANTS.filter(function (c) { return selected[c]; }).map(function (c) {
      var vals = {};
      YEARS.forEach(function (y) { vals[y] = AGG.by_claimant[c].years[String(y)].total; });
      return { key: c, label: NAMES[c] || c, color: claimantColor(c), values: vals };
    });
  }
  function byTypeSeries(code) {
    return TYPES.map(function (t) {
      var vals = {};
      YEARS.forEach(function (y) { vals[y] = AGG.by_claimant[code].years[String(y)][t]; });
      return { key: t, label: TYPE_LABELS[t] || t, color: typeColor(t), values: vals };
    });
  }

  // ---- render all --------------------------------------------------------
  function renderAll() {
    var all = document.querySelector('[data-chart="all-claimants"]');
    if (all) {
      var series = allClaimantsSeries();
      var fig = all.closest(".figure");
      var old = fig.querySelector(".legend"); if (old) old.remove();
      if (!series.length) {
        all.textContent = "";
        html("p", "empty", "No claimants selected. Pick at least one above.", all);
      } else {
        stackedColumns(all, series, { ariaLabel: "Assertive moves per year by claimant" });
        legend(fig, series).insertAdjacentElement("afterend", fig.querySelector(".table-view"));
        var tv = fig.querySelector(".table-view");
        table(tv, series, "Assertive moves per year by claimant");
      }
    }
    document.querySelectorAll('[data-chart="by-type"]').forEach(function (c) {
      var code = c.getAttribute("data-claimant");
      var fig = c.closest(".figure");
      fig.hidden = !selected[code];
      if (fig.hidden) return;
      var series = byTypeSeries(code);
      var total = AGG.by_claimant[code].totals.total;
      var old = fig.querySelector(".legend"); if (old) old.remove();
      if (!total) {
        c.textContent = "";
        html("p", "empty", "No coded moves yet for " + (NAMES[code] || code) + ". Coding for this claimant is in progress.", c);
        fig.querySelector(".table-view").textContent = "";
        return;
      }
      stackedColumns(c, series, { small: true, ariaLabel: "Assertive moves per year by type, " + (NAMES[code] || code) });
      legend(fig, series);
      table(fig.querySelector(".table-view"), series, "Assertive moves per year by type, " + (NAMES[code] || code));
    });
    var note = document.getElementById("filters-note");
    if (note) {
      var shown = CLAIMANTS.filter(function (c) { return selected[c]; });
      var sum = shown.reduce(function (s, c) { return s + AGG.by_claimant[c].totals.total; }, 0);
      note.textContent = shown.length === CLAIMANTS.length
        ? sum + " moves across all claimants"
        : sum + " moves across " + shown.length + " of " + CLAIMANTS.length + " claimants";
    }
  }

  // ---- controls ----------------------------------------------------------
  document.querySelectorAll("#claimant-filter input").forEach(function (box) {
    box.addEventListener("change", function () {
      selected[box.value] = box.checked;
      renderAll();
    });
  });
  document.querySelectorAll("[data-toggle-table]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var fig = document.getElementById(btn.getAttribute("data-toggle-table"));
      var on = btn.getAttribute("aria-pressed") !== "true";
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = on ? "Chart" : "Table";
      fig.querySelector(".chart").classList.toggle("is-hidden", on);
      var lg = fig.querySelector(".legend"); if (lg) lg.hidden = on;
      fig.querySelector(".table-view").hidden = !on;
    });
  });

  var resizeTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(renderAll, 120);
  });
  document.addEventListener("scroll", hideTip, { passive: true });

  renderAll();
})();
