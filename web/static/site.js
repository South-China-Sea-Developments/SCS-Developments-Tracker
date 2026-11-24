/* The home page's opening curtain (ticket 30); the inner pages' banner strip is CSS only. */
(function () {
  "use strict";
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- home page: the opening curtain, once per reader ----
  var curtain = document.getElementById("curtain");
  if (curtain && !/\bembed\b/.test(document.documentElement.className)) {
    var seen = false;
    try { seen = window.localStorage.getItem("scs-curtain-seen") === "1"; } catch (e) { seen = true; }
    if (!seen && !still) {
      curtain.hidden = false;
      document.documentElement.classList.add("curtain-on");
      // fill the screen: cover it where the logo (left 1 %) and the title (to 74 % of the artwork's width)
      // still fit across; otherwise scale to just fit them across and centre the banner on its blue
      var art = curtain.querySelector("img");
      var place = function () {
        var W = window.innerWidth, H = window.innerHeight, AW = 2219, AH = 950;
        var keepL = 0.008 * AW, keepR = 0.75 * AW;   // the logo's left edge and the title's right end, with a margin
        var s = Math.max(W / AW, H / AH), left;
        if ((keepR - keepL) * s <= W) {
          // cover, shifted so the kept span sits inside, as centred as the crop allows
          var spare = AW * s - W, mid = ((keepL + keepR) / 2) * s - W / 2;
          left = -Math.max(0, Math.min(spare, mid));
          left = Math.min(-0, Math.max(left, W - keepR * s));
          left = Math.min(left, -keepL * s + 0);
          art.style.cssText = "width:" + (AW * s) + "px;height:" + (AH * s) + "px;left:" + left + "px;top:" + ((H - AH * s) / 2) + "px;transform:none";
        } else {
          s = W / (keepR - keepL + 0.02 * AW);
          left = -(keepL - 0.01 * AW) * s;
          art.style.cssText = "width:" + (AW * s) + "px;height:" + (AH * s) + "px;left:" + left + "px;top:" + ((H - AH * s) / 2) + "px;transform:none";
        }
      };
      place();
      window.addEventListener("resize", place);
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

  // ---- home page: the latest moves open under the pointer (they also open on click, tap or Enter) ----
  var latest = document.getElementById("amap-latest");
  if (latest && window.matchMedia && window.matchMedia("(hover: hover)").matches) {
    latest.addEventListener("mouseenter", function () { latest.open = true; });
    latest.addEventListener("mouseleave", function () { if (!latest.contains(document.activeElement)) latest.open = false; });
    // the pointer has already opened it: a mouse click keeps it open rather than closing it again
    // (a keyboard Enter, event.detail 0, still toggles it)
    latest.addEventListener("focusout", function (ev) { if (!latest.contains(ev.relatedTarget) && !latest.matches(":hover")) latest.open = false; });
    latest.querySelector("summary").addEventListener("click", function (ev) { if (ev.detail > 0) { ev.preventDefault(); latest.open = true; } });
  }
})();
