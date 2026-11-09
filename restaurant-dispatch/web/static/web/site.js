/* Public site: the hero walkthrough (sample data, real component styles) and
 * the Fine Dining preset tabs. Nothing here talks to the server. */
(function () {
  "use strict";

  // ---------------------------------------------------------------- preset tabs
  var tabs = Array.prototype.slice.call(document.querySelectorAll("[data-preset-tab]"));
  var panels = Array.prototype.slice.call(document.querySelectorAll("[data-preset-panel]"));
  function select(key, focus) {
    tabs.forEach(function (t) {
      var on = t.getAttribute("data-preset-tab") === key;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      if (on && focus) t.focus();
    });
    panels.forEach(function (p) { p.hidden = p.getAttribute("data-preset-panel") !== key; });
  }
  tabs.forEach(function (t, i) {
    t.addEventListener("click", function () { select(t.getAttribute("data-preset-tab")); });
    t.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      var next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
      select(next.getAttribute("data-preset-tab"), true);
    });
  });
  if (tabs.length) select(tabs[0].getAttribute("data-preset-tab"));

  // ---------------------------------------------------------------- hero walkthrough
  var root = document.querySelector("[data-walkthrough]");
  if (!root) return;
  var card = root.querySelector("[data-wt-card]");
  var chip = root.querySelector("[data-wt-chip]");
  var meta = root.querySelector("[data-wt-meta]");
  var actions = root.querySelector("[data-wt-actions]");
  var count = root.querySelector("[data-wt-count]");
  var empty = root.querySelector("[data-wt-empty]");
  var seconds = 32;
  var timer = null;

  function chipHtml(mod, glyph, text) {
    return '<span class="chip chip--' + mod + '"><span class="chip__glyph" aria-hidden="true">' + glyph + "</span>" + text + "</span>";
  }
  function buttons(list) {
    actions.innerHTML = list.map(function (b) {
      return '<button class="btn ' + (b.primary ? "btn-primary" : "btn-quiet") + '" type="button" data-wt="' + b.key + '">' + b.label + "</button>";
    }).join("");
  }
  function state(name) {
    clearInterval(timer);
    card.className = "card task";
    if (name === "offer") {
      seconds = 32;
      card.classList.add("task--mine-offer");
      chip.innerHTML = chipHtml("offered", "→", "Offered to you");
      meta.innerHTML = 'Main room · from expo · <span class="timer" data-wt-timer>0:32</span> to claim, then it goes to backup.';
      buttons([{ key: "claim", label: "Claim", primary: true }, { key: "decline", label: "Decline" }]);
      count.textContent = "0"; empty.hidden = false;
      timer = setInterval(function () {
        seconds -= 1;
        var t = root.querySelector("[data-wt-timer]");
        if (t) { t.textContent = "0:" + String(Math.max(seconds, 0)).padStart(2, "0"); t.classList.toggle("is-urgent", seconds <= 10); }
        if (seconds <= 0) state("missed");
      }, 1000);
    } else if (name === "claimed") {
      card.classList.add("task--claimed");
      chip.innerHTML = chipHtml("claimed", "●", "You have it");
      meta.textContent = "Main room · claimed just now. It stays yours until you deliver it or give it back.";
      buttons([{ key: "deliver", label: "Delivered", primary: true }, { key: "replay", label: "Give back" }]);
      count.textContent = "1"; empty.hidden = true;
    } else if (name === "delivered") {
      card.classList.add("task--completed");
      chip.innerHTML = chipHtml("done", "✓", "Delivered");
      meta.textContent = "Expo and the floor lead see it closed the moment you tap.";
      buttons([{ key: "replay", label: "Replay" }]);
      count.textContent = "0"; empty.hidden = false;
    } else if (name === "missed") {
      card.classList.add("task--offered");
      chip.innerHTML = chipHtml("offered", "→", "Offered to Dev (backup)");
      meta.textContent = "Moved to backup coverage automatically. If Dev misses it too, the floor lead gets it.";
      buttons([{ key: "replay", label: "Replay" }]);
    }
  }
  actions.addEventListener("click", function (e) {
    var key = e.target.getAttribute && e.target.getAttribute("data-wt");
    if (key === "claim") state("claimed");
    else if (key === "decline") state("missed");
    else if (key === "deliver") state("delivered");
    else if (key === "replay") state("offer");
  });
  state("offer");
})();
