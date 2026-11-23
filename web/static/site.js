/* Every page (ticket 30): the banner's fold on inner pages and the opening curtain on the home page. */
(function () {
  "use strict";
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- inner pages: the whole banner on arrival, folding into the slim strip as the page scrolls ----
  // The fold box keeps the banner's full height in the flow; the banner sticks to its top and shrinks from
  // its own proportions to the strip over the first scroll, so the menu band below rises with the page
  // and stays against it; once folded, the strip scrolls away with the page.
  var fold = document.querySelector(".banner-fold"), banner = fold && fold.querySelector(".banner"), img = banner && banner.querySelector("img");
  if (fold && banner && img) {
    var full = 0, slim = 0;
    var measure = function () {
      var w = fold.clientWidth;
      full = Math.round(w * 950 / 2219);
      slim = Math.max(84, Math.min(150, Math.round(w * 0.11)));
      fold.style.height = full + "px";
      draw();
    };
    var draw = function () {
      var y = Math.max(0, window.scrollY || window.pageYOffset || 0);
      var h = Math.max(slim, full - y), f = full > slim ? (full - h) / (full - slim) : 1;
      banner.style.height = h + "px";
      img.style.objectPosition = "center " + Math.round(35 * f) + "%";   // whole at the top; the title's first line once folded
      fold.classList.toggle("folded", f >= 1);
    };
    var ticking = false;
    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () { ticking = false; draw(); });
    }, { passive: true });
    window.addEventListener("resize", measure);
    measure();
  }

  // ---- home page: the opening curtain, once per reader ----
  var curtain = document.getElementById("curtain");
  if (curtain) {
    var seen = false;
    try { seen = window.localStorage.getItem("scs-curtain-seen") === "1"; } catch (e) { seen = true; }
    if (!seen && !still) {
      curtain.hidden = false;
      document.documentElement.classList.add("curtain-on");
      var lift = function () {
        if (curtain.classList.contains("up")) return;
        curtain.classList.add("up");
        document.documentElement.classList.remove("curtain-on");
        try { window.localStorage.setItem("scs-curtain-seen", "1"); } catch (e) { /* private mode */ }
        setTimeout(function () { curtain.hidden = true; }, 1000);
      };
      var timer = setTimeout(lift, 1600);
      ["click", "keydown", "wheel", "touchstart"].forEach(function (ev) {
        window.addEventListener(ev, function () { clearTimeout(timer); lift(); }, { once: true, passive: true });
      });
    }
  }
})();
