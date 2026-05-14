(function () {
  function onlyDigits(value) {
    return String(value || "").replace(/\D/g, "");
  }

  function formatMoneyPtBrFromDigits(digits) {
    var n = digits || "0";
    if (n.length < 3) n = n.padStart(3, "0");
    var cents = n.slice(-2);
    var integer = n.slice(0, -2).replace(/^0+/, "") || "0";
    var withDots = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return withDots + "," + cents;
  }

  function applyMoneyMask(input) {
    if (!input || input.dataset.maskMoneyBound === "1") return;
    input.dataset.maskMoneyBound = "1";

    function update() {
      var digits = onlyDigits(input.value);
      input.value = formatMoneyPtBrFromDigits(digits);
    }

    input.addEventListener("input", update);
    input.addEventListener("blur", update);
    if (input.value && /[0-9]/.test(input.value)) update();
  }

  function applyCpfMask(input) {
    if (!input || input.dataset.maskCpfBound === "1") return;
    input.dataset.maskCpfBound = "1";
    input.addEventListener("input", function () {
      var v = onlyDigits(input.value).slice(0, 11);
      if (v.length <= 3) input.value = v;
      else if (v.length <= 6) input.value = v.slice(0, 3) + "." + v.slice(3);
      else if (v.length <= 9) input.value = v.slice(0, 3) + "." + v.slice(3, 6) + "." + v.slice(6);
      else input.value = v.slice(0, 3) + "." + v.slice(3, 6) + "." + v.slice(6, 9) + "-" + v.slice(9);
    });
  }

  function applyCepMask(input) {
    if (!input || input.dataset.maskCepBound === "1") return;
    input.dataset.maskCepBound = "1";
    input.addEventListener("input", function () {
      var v = onlyDigits(input.value).slice(0, 8);
      input.value = v.length > 5 ? v.slice(0, 5) + "-" + v.slice(5) : v;
    });
  }

  function applyPhoneMask(input) {
    if (!input || input.dataset.maskPhoneBound === "1") return;
    input.dataset.maskPhoneBound = "1";
    input.addEventListener("input", function () {
      var v = onlyDigits(input.value).slice(0, 11);
      if (v.length <= 2) {
        input.value = v.length ? "(" + v : "";
      } else if (v.length <= 6) {
        input.value = "(" + v.slice(0, 2) + ") " + v.slice(2);
      } else if (v.length <= 10) {
        input.value = "(" + v.slice(0, 2) + ") " + v.slice(2, 6) + "-" + v.slice(6);
      } else {
        input.value = "(" + v.slice(0, 2) + ") " + v.slice(2, 7) + "-" + v.slice(7);
      }
    });
  }

  function createGlobalLoadingElements() {
    if (!document.getElementById("m3-top-progress")) {
      var bar = document.createElement("div");
      bar.id = "m3-top-progress";
      bar.className = "m3-top-progress";
      bar.setAttribute("aria-hidden", "true");
      document.body.appendChild(bar);
    }
    if (!document.getElementById("m3-page-mask")) {
      var mask = document.createElement("div");
      mask.id = "m3-page-mask";
      mask.className = "m3-page-mask";
      mask.setAttribute("aria-hidden", "true");
      document.body.appendChild(mask);
    }
  }

  var loadingCounter = 0;
  var progressTimer = null;

  function getProgressBar() {
    return document.getElementById("m3-top-progress");
  }

  function getPageMask() {
    return document.getElementById("m3-page-mask");
  }

  function beginLoading() {
    createGlobalLoadingElements();
    loadingCounter += 1;

    var bar = getProgressBar();
    var mask = getPageMask();
    if (!bar || !mask) return;

    bar.classList.add("is-active");
    mask.classList.add("is-active");
    bar.style.width = "18%";

    if (progressTimer) {
      clearInterval(progressTimer);
    }

    progressTimer = setInterval(function () {
      var current = parseFloat(bar.style.width || "18");
      if (current < 85) {
        bar.style.width = String(current + Math.random() * 8) + "%";
      }
    }, 220);
  }

  function endLoading(force) {
    if (force) {
      loadingCounter = 0;
    } else {
      loadingCounter = Math.max(loadingCounter - 1, 0);
    }

    if (loadingCounter > 0) return;

    var bar = getProgressBar();
    var mask = getPageMask();
    if (!bar || !mask) return;

    if (progressTimer) {
      clearInterval(progressTimer);
      progressTimer = null;
    }

    bar.style.width = "100%";
    setTimeout(function () {
      bar.classList.remove("is-active");
      bar.style.width = "0";
      mask.classList.remove("is-active");
    }, 260);
  }

  function shouldTrackNavigation(anchor) {
    if (!anchor || !anchor.href) return false;
    if (anchor.dataset.noNavLoading === "1") return false;
    if (anchor.target && anchor.target !== "_self") return false;
    if (anchor.hasAttribute("download")) return false;
    if (anchor.getAttribute("href").startsWith("#")) return false;

    try {
      var url = new URL(anchor.href, window.location.origin);
      if (url.origin !== window.location.origin) return false;
      if (url.pathname === window.location.pathname && url.search === window.location.search) return false;
      return true;
    } catch (e) {
      return false;
    }
  }

  function setupNavigationFeedback() {
    document.addEventListener("click", function (event) {
      var anchor = event.target.closest("a[href]");
      if (!shouldTrackNavigation(anchor)) return;
      beginLoading();
    });

    window.addEventListener("pageshow", function () {
      endLoading(true);
    });

    window.addEventListener("beforeunload", function () {
      beginLoading();
    });
  }

  function setupFetchFeedback() {
    if (!window.fetch || window.__m3FetchWrapped) return;
    var originalFetch = window.fetch;
    window.__m3FetchWrapped = true;

    function getCookie(name) {
      var value = "; " + document.cookie;
      var parts = value.split("; " + name + "=");
      if (parts.length === 2) return parts.pop().split(";").shift();
      return "";
    }

    function isUnsafeMethod(method) {
      var m = String(method || "GET").toUpperCase();
      return ["POST", "PUT", "PATCH", "DELETE"].indexOf(m) >= 0;
    }

    window.fetch = function () {
      var args = Array.prototype.slice.call(arguments);
      var input = args[0];
      var init = args[1] || {};
      var method = init.method || "GET";
      var headers = new Headers(init.headers || {});

      try {
        var url = typeof input === "string" ? new URL(input, window.location.origin) : new URL(input.url, window.location.origin);
        if (url.origin === window.location.origin && isUnsafeMethod(method) && !headers.has("X-CSRFToken")) {
          var token = getCookie("csrftoken");
          if (token) headers.set("X-CSRFToken", token);
        }
      } catch (e) {
        // Ignore URL parse errors and keep request flow.
      }

      init.headers = headers;
      args[1] = init;

      beginLoading();
      return originalFetch.apply(this, args).finally(function () {
        endLoading();
      });
    };
  }

  function setupRequiredHints() {
    document.querySelectorAll("label").forEach(function (label) {
      if (label.dataset.m3RequiredBound === "1") return;
      var inputId = label.getAttribute("for");
      if (!inputId) return;
      var field = document.getElementById(inputId);
      if (!field || !field.required) return;
      label.classList.add("m3-required");
      label.dataset.m3RequiredBound = "1";
    });
  }

  function setupValidationFeedback() {
    document.querySelectorAll("form").forEach(function (form) {
      if (form.dataset.validationBound === "1") return;
      form.dataset.validationBound = "1";

      form.querySelectorAll("input, select, textarea").forEach(function (field) {
        field.addEventListener("blur", function () {
          if (!field.checkValidity()) {
            field.classList.add("is-invalid");
          } else {
            field.classList.remove("is-invalid");
          }
        });
      });
    });
  }

  function setupSubmitFeedback() {
    document.querySelectorAll("form").forEach(function (form) {
      if (form.dataset.submitFeedbackBound === "1") return;
      form.dataset.submitFeedbackBound = "1";

      form.addEventListener("submit", function (event) {
        if (!form.checkValidity()) {
          form.classList.add("was-validated");
          event.preventDefault();
          endLoading(true);
          return;
        }

        beginLoading();
        var submit = form.querySelector('button[type="submit"], input[type="submit"]');
        if (submit && !submit.disabled) {
          submit.dataset.originalHtml = submit.innerHTML || submit.value || "Enviar";
          if (submit.tagName === "BUTTON") {
            submit.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Enviando...';
          } else {
            submit.value = "Enviando...";
          }
          submit.disabled = true;
        }
        form.classList.add("m3-loading");
      });
    });
  }

  function autoDismissAlerts() {
    setTimeout(function () {
      document.querySelectorAll(".alert.show").forEach(function (alertEl) {
        if (window.bootstrap && bootstrap.Alert) {
          try {
            bootstrap.Alert.getOrCreateInstance(alertEl).close();
          } catch (e) {
            return;
          }
        }
      });
    }, 7000);
  }

  function normalizeVisualPatterns() {
    document.querySelectorAll("table").forEach(function (table) {
      if (!table.classList.contains("table")) {
        table.classList.add("table");
      }
    });

    document.querySelectorAll(".main-content form").forEach(function (form) {
      if (!form.classList.contains("m3-form")) {
        form.classList.add("m3-form");
      }
    });

    document.body.classList.add("m3-shell-ready");
  }

  document.addEventListener("DOMContentLoaded", function () {
    createGlobalLoadingElements();
    setupNavigationFeedback();
    setupFetchFeedback();

    document.querySelectorAll("input.money-mask").forEach(applyMoneyMask);
    document.querySelectorAll("input.cpf-mask").forEach(applyCpfMask);
    document.querySelectorAll("input.cep-mask").forEach(applyCepMask);
    document.querySelectorAll("input.phone-mask").forEach(applyPhoneMask);

    setupRequiredHints();
    setupValidationFeedback();
    setupSubmitFeedback();
    normalizeVisualPatterns();
    autoDismissAlerts();

    endLoading(true);
  });
})();
