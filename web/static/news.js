/* What's new: narrow the list to one claimant and point the feed link at that claimant's own feed (wave 1). */
(function () {
  "use strict";
  var box = document.getElementById("news-follow");
  if (!box) return;
  var feed = document.getElementById("news-feed"), none = document.getElementById("news-none");
  var names = {};
  Array.prototype.forEach.call(box.querySelectorAll("button"), function (b) { names[b.getAttribute("data-code")] = b.textContent; });
  function show(code) {
    Array.prototype.forEach.call(box.querySelectorAll("button"), function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-code") === code ? "true" : "false"); });
    var any = false;
    Array.prototype.forEach.call(document.querySelectorAll(".news-day"), function (day) {
      var shown = 0;
      Array.prototype.forEach.call(day.querySelectorAll("li[data-claimant]"), function (li) {
        var on = !code || li.getAttribute("data-claimant") === code;
        li.hidden = !on; if (on) shown++;
      });
      day.hidden = !shown; if (shown) any = true;
      var n = day.querySelector(".news-n");
      if (n) {
        if (!n.hasAttribute("data-all")) n.setAttribute("data-all", n.textContent);
        var kinds = { added: 0, updated: 0, retracted: 0 };
        Array.prototype.forEach.call(day.querySelectorAll("li[data-claimant]"), function (li) { if (!li.hidden) for (var k in kinds) if (li.classList.contains("news-" + k)) kinds[k]++; });
        n.textContent = code ? [kinds.added + " added", kinds.updated ? kinds.updated + " updated" : "", kinds.retracted ? kinds.retracted + " retracted" : ""].filter(Boolean).join(", ") : n.getAttribute("data-all");
      }
    });
    if (none) none.hidden = any;
    feed.href = code ? "feeds/" + code.toLowerCase() + ".xml" : feed.getAttribute("data-all");
    feed.textContent = code ? "Feed for " + names[code] : "Feed for every claimant";
    try { history.replaceState(null, "", code ? "#" + code.toLowerCase() : location.pathname); } catch (e) { /* a sandboxed frame */ }
  }
  box.addEventListener("click", function (ev) {
    var b = ev.target.closest("button");
    if (b) show(b.getAttribute("data-code"));
  });
  var m = /^#([a-z]{2})$/.exec(location.hash);
  if (m && names[m[1].toUpperCase()] !== undefined) show(m[1].toUpperCase());
})();
