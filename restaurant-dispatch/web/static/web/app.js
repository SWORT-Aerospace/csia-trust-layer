/* Restaurant Service Dispatch — staff screen runtime.
 *
 * - Short polling keeps every [data-live] region current.
 * - Action forms ([data-act]) post with fetch. If a request fails or the
 *   connection drops, the action is shown as UNCONFIRMED and buttons are
 *   locked until the board has been re-read from the server, so nobody
 *   retries blind. Forms still work without JavaScript (POST + redirect).
 * - Offer countdowns tick locally against the server clock.
 */
(function () {
  "use strict";

  var POLL_MS = 2500;
  var OFFLINE_POLL_MS = 4000;
  var ACTION_TIMEOUT_MS = 8000;
  var MAX_DEFER_MS = 15000;

  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  var conn = document.querySelector("[data-conn]");
  var toasts = document.querySelector("[data-toasts]");
  var banner = document.querySelector("[data-unconfirmed]");
  var bannerText = document.querySelector("[data-unconfirmed-text]");
  var regions = Array.prototype.slice.call(document.querySelectorAll("[data-live]"));
  var serverOffset = 0;
  var online = true;
  var pending = null; // label of an unconfirmed action
  var pollTimer = null;

  function timeText(d) {
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
  }

  function setConn(state, text) {
    if (!conn) return;
    conn.setAttribute("data-state", state);
    conn.textContent = text;
  }

  function toast(message, kind) {
    if (!toasts || !message) return;
    var el = document.createElement("div");
    el.className = "toast" + (kind ? " toast--" + kind : "");
    el.setAttribute("role", kind === "err" ? "alert" : "status");
    el.textContent = (kind === "err" ? "▲ " : kind === "warn" ? "◌ " : "✓ ") + message;
    toasts.appendChild(el);
    setTimeout(function () { el.remove(); }, kind === "err" ? 7000 : 4000);
  }

  // ---------------------------------------------------------------- unconfirmed actions
  function markUnconfirmed(label) {
    pending = label || "your last action";
    document.body.classList.remove("is-reconciled");
    document.body.classList.add("is-unconfirmed");
    if (bannerText) {
      bannerText.textContent =
        "▲ Not confirmed: “" + pending + "”. The connection dropped before the server answered. " +
        "Checking the floor — don't retry until the board refreshes.";
    }
    setConn("offline", "Offline — reconnecting");
    schedule(1000);
  }

  function markReconciled() {
    if (!pending) return;
    var label = pending;
    pending = null;
    document.body.classList.remove("is-unconfirmed");
    document.body.classList.add("is-reconciled");
    if (bannerText) {
      bannerText.textContent =
        "✓ Back online. The board below is the server's current state — check whether “" + label +
        "” went through before you try again.";
    }
    setTimeout(function () { document.body.classList.remove("is-reconciled"); }, 9000);
  }

  // ---------------------------------------------------------------- live regions
  function isBusy(region) {
    if (region.hasAttribute("data-hold-when-dirty") && region._dirty) return true;
    var active = document.activeElement;
    if (active && region.contains(active) && /^(SELECT|INPUT|TEXTAREA)$/.test(active.tagName)) return true;
    if (region.querySelector("details[open]")) return true;
    return false;
  }

  function swap(region, html) {
    region.innerHTML = html;
    region._html = html;
    region._dirty = false;
    region._deferSince = 0;
    tick();
  }

  function refresh(region, force) {
    return fetch(region.getAttribute("data-live"), {
      headers: { "X-Dispatch-Fetch": "1" },
      credentials: "same-origin",
      cache: "no-store",
    }).then(function (res) {
      if (res.redirected || res.status === 401) { window.location.reload(); return; }
      if (res.status === 403 || res.status === 404) { window.location.reload(); return; }
      if (!res.ok) throw new Error("HTTP " + res.status);
      var st = Number(res.headers.get("X-Server-Time"));
      if (st) serverOffset = st - Date.now();
      return res.text().then(function (html) {
        if (html === region._html) return;
        // A composer the user has started filling keeps its form (and its
        // idempotency token) until it is submitted successfully, so a retry
        // after a dropped connection is deduplicated by the server.
        var held = region.hasAttribute("data-hold-when-dirty") && region._dirty;
        if (held) return;
        if (!force && isBusy(region)) {
          region._deferSince = region._deferSince || Date.now();
          if (Date.now() - region._deferSince < MAX_DEFER_MS) return;
        }
        swap(region, html);
      });
    });
  }

  function refreshAll(force) {
    return Promise.all(regions.map(function (r) { return refresh(r, force); }));
  }

  function schedule(ms) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, ms);
  }

  function poll() {
    if (!regions.length) return;
    refreshAll(!!pending).then(function () {
      online = true;
      setConn("live", "Live · " + timeText(new Date()));
      markReconciled();
      schedule(document.hidden ? POLL_MS * 2 : POLL_MS);
    }).catch(function () {
      online = false;
      setConn("offline", "Offline — reconnecting");
      schedule(OFFLINE_POLL_MS);
    });
  }

  // ---------------------------------------------------------------- actions
  document.addEventListener("input", function (ev) {
    var region = ev.target.closest && ev.target.closest("[data-hold-when-dirty]");
    if (region) region._dirty = true;
  });
  document.addEventListener("change", function (ev) {
    var region = ev.target.closest && ev.target.closest("[data-hold-when-dirty]");
    if (region) region._dirty = true;
    if (ev.target.matches && ev.target.matches("[data-persona-switch]")) {
      var target = ev.target.value;
      if (target) window.location.href = target;
    }
  });

  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (!form.matches || !form.matches("form[data-act]")) return;
    ev.preventDefault();
    if (pending) {
      toast("Still checking your last action. Wait for the board to refresh.", "warn");
      return;
    }
    var submitter = ev.submitter || form.querySelector('button[type="submit"]');
    if (form._sending) return; // double tap: the first request is in flight
    form._sending = true;
    var label = form.getAttribute("data-label") || (submitter ? submitter.textContent.trim() : "action");
    var data = new FormData(form);
    if (submitter && submitter.name) data.append(submitter.name, submitter.value);
    var buttons = form.querySelectorAll("button");
    var original = submitter ? submitter.innerHTML : "";
    buttons.forEach(function (b) { b.disabled = true; });
    if (submitter) submitter.textContent = "Sending…";
    var controller = window.AbortController ? new AbortController() : null;
    var timer = setTimeout(function () { if (controller) controller.abort(); }, ACTION_TIMEOUT_MS);

    fetch(form.action, {
      method: "POST",
      body: data,
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf, "X-Dispatch-Fetch": "1", Accept: "application/json" },
      signal: controller ? controller.signal : undefined,
    }).then(function (res) {
      var st = Number(res.headers.get("X-Server-Time"));
      if (st) serverOffset = st - Date.now();
      return res.json().catch(function () { return null; }).then(function (body) {
        if (!body) {
          if (res.status === 403) { toast("Your session expired. Reloading…", "err"); setTimeout(function () { location.reload(); }, 1200); return; }
          throw new Error("unreadable response");
        }
        toast(body.message, body.ok ? "ok" : "err");
        var region = form.closest("[data-live]");
        if (body.ok && region) region._dirty = false;
        return refreshAll(body.ok);
      });
    }).catch(function () {
      markUnconfirmed(label);
    }).then(function () {
      clearTimeout(timer);
      form._sending = false;
      if (document.body.contains(form)) {
        buttons.forEach(function (b) { b.disabled = false; });
        if (submitter) submitter.innerHTML = original;
      }
    });
  });

  // ---------------------------------------------------------------- countdowns
  function tick() {
    var now = Date.now() + serverOffset;
    document.querySelectorAll("[data-expires]").forEach(function (el) {
      var end = Number(el.getAttribute("data-expires"));
      if (!end) return;
      var left = Math.max(0, Math.round((end - now) / 1000));
      el.textContent = left > 0 ? Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0") : "time's up — moving on";
      el.classList.toggle("is-urgent", left <= 10);
    });
  }
  setInterval(tick, 1000);
  tick();

  document.addEventListener("visibilitychange", function () { if (!document.hidden) schedule(50); });
  window.addEventListener("online", function () { schedule(50); });
  window.addEventListener("offline", function () { setConn("offline", "Offline — reconnecting"); });

  regions.forEach(function (r) { r._html = r.innerHTML; });
  if (regions.length) { setConn("live", "Live"); schedule(POLL_MS); }
})();
