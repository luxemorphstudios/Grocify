/* Small helpers shared by every page: theme switch, confirm dialogs, flashes. */
(function () {
  "use strict";

  // ------------------------------------------------------------ theme
  var root = document.documentElement;
  var toggle = document.getElementById("themeToggle");

  function paintToggle() {
    if (!toggle) return;
    var dark = root.getAttribute("data-bs-theme") === "dark";
    toggle.innerHTML = dark
      ? '<i class="bi bi-sun"></i>'
      : '<i class="bi bi-moon-stars"></i>';
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-bs-theme", next);
      try { localStorage.setItem("grocify-theme", next); } catch (e) {}
      paintToggle();
      document.dispatchEvent(new CustomEvent("grocify:theme", { detail: next }));
    });
    paintToggle();
  }

  // -------------------------------------------- confirm before submitting
  document.addEventListener("submit", function (e) {
    var message = e.target.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      e.preventDefault();
    }
  });

  // --------------------------------------------------- dismiss flashes
  document.querySelectorAll(".alert-auto").forEach(function (el) {
    setTimeout(function () {
      el.classList.add("fade");
      el.classList.remove("show");
      setTimeout(function () { el.remove(); }, 300);
    }, 4500);
  });

  // ------------------------------- fill a modal from the row that opened it
  // <button data-bs-target="#editModal" data-field-name="Dairy"> fills #f-name
  document.addEventListener("show.bs.modal", function (e) {
    var trigger = e.relatedTarget;
    if (!trigger) return;
    Object.keys(trigger.dataset).forEach(function (key) {
      if (key.indexOf("field") !== 0) return;
      var name = key.slice(5).toLowerCase();
      var input = e.target.querySelector('[data-fill="' + name + '"]');
      if (input) input.value = trigger.dataset[key];
    });
    var action = trigger.dataset.action;
    if (action) {
      var form = e.target.querySelector("form");
      if (form) form.setAttribute("action", action);
    }
  });

  // ------------------------------------------ auto-submit filter selects
  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });
})();

/* Chart.js defaults that follow the current theme. */
function grocifyChartDefaults() {
  var dark = document.documentElement.getAttribute("data-bs-theme") === "dark";
  return {
    text: dark ? "#93a3b8" : "#64748b",
    grid: dark ? "rgba(147,163,184,.16)" : "rgba(100,116,139,.14)",
    brand: dark ? "#22c55e" : "#16a34a",
    palette: ["#16a34a", "#0ea5e9", "#f59e0b", "#8b5cf6", "#ef4444",
              "#14b8a6", "#ec4899", "#64748b", "#84cc16", "#f97316"]
  };
}
