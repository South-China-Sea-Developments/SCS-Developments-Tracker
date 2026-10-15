/* Case browser: client-side filtering of the inline case index. */
(function () {
  "use strict";
  var src = document.getElementById("cases");
  if (!src) return;
  var CASES = JSON.parse(src.textContent);
  var NAMES = { CN: "China", VN: "Vietnam", PH: "Philippines", MY: "Malaysia", ID: "Indonesia", TW: "Taiwan" };
  var TYPE_LABELS = { declarative: "Declarative", demonstrative: "Demonstrative", coercive: "Coercive", force: "Use of force" };

  var list = document.getElementById("case-list");
  var count = document.getElementById("count");
  var noMatch = document.getElementById("no-match");
  var form = document.getElementById("case-filters");

  function checked(name) {
    return Array.prototype.map.call(form.querySelectorAll('input[name="' + name + '"]:checked'), function (i) { return i.value; });
  }
  function readFilters() {
    var y0 = parseInt(document.getElementById("y0").value, 10), y1 = parseInt(document.getElementById("y1").value, 10);
    return {
      q: document.getElementById("q").value.trim().toLowerCase(),
      claimants: checked("claimant"),
      y0: isNaN(y0) ? -Infinity : y0, y1: isNaN(y1) ? Infinity : y1,
      types: checked("t"), domains: checked("d"), issues: checked("i"),
      target: document.getElementById("target").value,
      subregion: document.getElementById("subregion").value
    };
  }
  function anyOf(selected, have) {            // a checked group matches if the move has ANY of the checked values
    if (!selected.length) return true;
    return selected.some(function (v) { return have.indexOf(v) >= 0; });
  }
  function matches(c, f) {
    if (f.claimants.indexOf(c.c) < 0) return false;
    if (c.y < f.y0 || c.y > f.y1) return false;
    if (!anyOf(f.types, c.t) || !anyOf(f.domains, c.d) || !anyOf(f.issues, c.i)) return false;
    if (f.target && c.g.indexOf(f.target) < 0) return false;
    if (f.subregion && c.s.indexOf(parseInt(f.subregion, 10)) < 0) return false;
    if (f.q && (c.x.toLowerCase().indexOf(f.q) < 0 && c.id.toLowerCase().indexOf(f.q) < 0)) return false;
    return true;
  }

  function excerpt(text, q) {
    var max = 220;
    if (text.length <= max) return text;
    if (q) {
      var i = text.toLowerCase().indexOf(q);
      if (i > 60) {
        var start = text.lastIndexOf(" ", i - 60);
        return "… " + text.slice(start + 1, start + 1 + max).replace(/\s+\S*$/, "") + " …";
      }
    }
    return text.slice(0, max).replace(/\s+\S*$/, "") + " …";
  }

  function el(tag, cls, text, parent) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }

  function render() {
    var f = readFilters();
    var hits = CASES.filter(function (c) { return matches(c, f); });
    list.textContent = "";
    hits.forEach(function (c) {
      var li = el("li", "case-row" + (c.st !== "accepted" ? " is-pending" : ""), undefined, list);
      var head = el("div", "case-row-head", undefined, li);
      var a = el("a", "case-link", undefined, head);
      a.href = "cases/" + c.id + ".html";
      el("span", "case-claimant", NAMES[c.c] || c.c, a).setAttribute("data-code", c.c);
      el("span", "case-year", String(c.y), a);
      var pills = el("span", "case-types", undefined, head);
      c.t.forEach(function (t) { el("span", "type-pill", TYPE_LABELS[t] || t, pills).setAttribute("data-type", t); });
      if (c.st !== "accepted") el("span", "pending-pill", "pending", pills);
      el("span", "case-id", c.id, head);
      el("p", "case-excerpt", excerpt(c.x, f.q), li);
    });
    noMatch.hidden = hits.length > 0;
    count.textContent = hits.length === CASES.length
      ? CASES.length + " moves"
      : hits.length + " of " + CASES.length + " moves";
  }

  var timer = null;
  form.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(render, 80); });
  form.addEventListener("change", render);
  document.getElementById("reset").addEventListener("click", function () {
    form.querySelectorAll('input[type="checkbox"]').forEach(function (i) { i.checked = i.name === "claimant"; });
    document.getElementById("q").value = "";
    document.getElementById("y0").value = document.getElementById("y0").min;
    document.getElementById("y1").value = document.getElementById("y1").max;
    document.getElementById("target").value = "";
    document.getElementById("subregion").value = "";
    render();
  });

  // a query string pre-fills the search box so a search can be linked to
  var params = new URLSearchParams(window.location.search);
  if (params.get("q")) document.getElementById("q").value = params.get("q");
  render();
})();
