/* Syncora demo — guided tour.
 * Polls /demo/tour/ and renders the next step. Buttons call real server
 * actions (the same engine the staff screens use); the "offer expires" step
 * is completed by the timer worker, never by this page. All text is set with
 * textContent: no HTML from the server is injected.
 */
(function () {
  "use strict";
  var roots = Array.prototype.slice.call(document.querySelectorAll("[data-tour]"));
  if (!roots.length) return;
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  var offset = 0;
  var last = null;
  var busy = false;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function secondsLeft(step) {
    if (!step || !step.expires_at_ms) return null;
    return Math.max(0, Math.round((step.expires_at_ms - (Date.now() + offset)) / 1000));
  }
  function clock(s) { return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf, "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body: body || "",
    }).then(function (res) { return res.json(); });
  }

  function act(root, step, button) {
    if (busy) return;
    busy = true;
    button.disabled = true;
    button.textContent = "Sending…";
    post(root.getAttribute("data-tour-do"), "step=" + encodeURIComponent(step.key))
      .then(function (body) {
        say(root, body.message, body.ok && body.tone !== "refused" ? "ok" : "err");
        if (body.state) apply(body.state);
      })
      .catch(function () { say(root, "Not confirmed: the connection dropped. Checking the floor…", "err"); })
      .then(function () { busy = false; refresh(); });
  }

  function say(root, message, kind) {
    var box = root.querySelector("[data-tour-msg]");
    if (!box || !message) return;
    box.textContent = (kind === "err" ? "▲ " : "✓ ") + message;
    box.className = "tour__msg tour__msg--" + kind;
  }

  function renderNow(root, state) {
    var now = root.querySelector("[data-tour-now]");
    if (!now) return;
    var compact = root.hasAttribute("data-compact");
    var self = Number(root.getAttribute("data-self-sid") || 0);
    now.textContent = "";
    var total = state.steps.length;
    if (state.complete) {
      var lastStep = state.steps[total - 1];
      now.appendChild(el("p", "tour__title", "✓ Tour complete — " + state.edition + (state.preset !== state.edition ? " · " + state.preset : "") + "."));
      if (lastStep && lastStep.note) now.appendChild(el("p", "tour__note", lastStep.note));
      now.appendChild(el("p", "tour__note", compact ? "Every screen is live. Keep exploring." : "Every screen below is live. Keep exploring, or restart the tour."));
      return;
    }
    var step = state.steps[state.current];
    var head = el("p", "tour__step", "Step " + (state.current + 1) + " of " + total + (step.who ? " · " + step.who : ""));
    now.appendChild(head);
    now.appendChild(el("p", "tour__title", step.title));
    var row = el("div", "tour__actions");
    if (step.waiting) {
      var left = secondsLeft(step);
      var t = el("p", "tour__timer", left > 0 ? "Timer worker moves it in " + clock(left) : "Moving it now…");
      t.setAttribute("data-tour-timer", "");
      now.appendChild(t);
    }
    if (step.action) {
      var mine = !self || self === step.who_sid;
      if (compact && !mine) {
        // On someone else's screen: send the visitor to the right person.
      } else {
        var b = el("button", "btn btn-primary" + (compact ? " btn-small" : ""), compact ? "Do it: " + step.action : step.action);
        b.type = "button";
        b.addEventListener("click", function () { act(root, step, b); });
        row.appendChild(b);
      }
    }
    if (step.who_url && (!compact || self !== step.who_sid)) {
      var a = el("a", "btn" + (compact ? " btn-small" : " btn-quiet"), (compact ? "Switch to " : "Open ") + step.who.split(" (")[0] + (compact ? "" : "'s screen"));
      a.href = step.who_url;
      row.appendChild(a);
    }
    if (compact && self === step.who_sid && step.action) {
      now.appendChild(el("p", "tour__note", "Your turn. Use the button on this screen, or the shortcut."));
    }
    if (row.childNodes.length) now.appendChild(row);
    if (step.note) now.appendChild(el("p", "tour__note", step.note));
  }

  function renderList(root, state) {
    var list = root.querySelector("[data-tour-steps]");
    if (!list) return;
    list.textContent = "";
    state.steps.forEach(function (s) {
      var li = el("li", "tour__item is-" + s.status);
      var mark = el("span", "tour__mark", s.status === "done" ? "✓" : s.status === "current" ? "➜" : "○");
      mark.setAttribute("aria-hidden", "true");
      li.appendChild(mark);
      var body = el("span", null, s.title);
      if (s.status === "done") body.appendChild(el("span", "visually-hidden", " (done)"));
      if (s.status === "current") body.appendChild(el("span", "visually-hidden", " (next)"));
      li.appendChild(body);
      list.appendChild(li);
    });
  }

  function highlight(state) {
    var step = state.complete ? null : state.steps[state.current];
    var sid = step ? step.who_sid : null;
    document.querySelectorAll("[data-pane-sid]").forEach(function (p) {
      p.classList.toggle("is-acting", sid != null && Number(p.getAttribute("data-pane-sid")) === sid);
    });
    document.querySelectorAll("[data-persona-sid]").forEach(function (p) {
      p.classList.toggle("is-next", sid != null && Number(p.getAttribute("data-persona-sid")) === sid);
    });
  }

  function apply(state) {
    if (state.now_ms) offset = state.now_ms - Date.now();
    var key = JSON.stringify(state.steps.map(function (s) { return [s.status, s.title, s.action, s.note]; }));
    var changed = key !== last;
    last = key;
    roots.forEach(function (root) {
      if (changed) { renderNow(root, state); renderList(root, state); }
      root.hidden = false;
    });
    highlight(state);
    window.__tourState = state;
  }

  function refresh() {
    return fetch(roots[0].getAttribute("data-tour-url"), { credentials: "same-origin", cache: "no-store" })
      .then(function (res) { if (!res.ok) throw new Error(res.status); return res.json(); })
      .then(apply)
      .catch(function () {});
  }

  roots.forEach(function (root) {
    var restart = root.querySelector("[data-tour-restart-btn]");
    if (restart) restart.addEventListener("click", function () {
      post(root.getAttribute("data-tour-restart")).then(function (body) { last = null; apply(body.state); say(root, "Tour restarted on a fresh table.", "ok"); });
    });
  });

  setInterval(function () {
    var state = window.__tourState;
    if (!state || state.complete) return;
    var step = state.steps[state.current];
    var left = secondsLeft(step);
    document.querySelectorAll("[data-tour-timer]").forEach(function (t) {
      t.textContent = left > 0 ? "Timer worker moves it in " + clock(left) : "Moving it now…";
    });
  }, 1000);
  setInterval(refresh, 2000);
  refresh();
})();
