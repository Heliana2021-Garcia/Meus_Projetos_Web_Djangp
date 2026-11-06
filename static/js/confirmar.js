(function () {
  "use strict";
  var el = document.getElementById("modal-confirmar");
  if (!el || !window.bootstrap) { return; }
  var modal = bootstrap.Modal.getOrCreateInstance(el);
  var titulo = document.getElementById("modal-confirmar-titulo");
  var texto = document.getElementById("modal-confirmar-texto");
  var ok = document.getElementById("modal-confirmar-ok");
  var pendente = null;

  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (!form.hasAttribute || !form.hasAttribute("data-confirmar")) { return; }
    if (form.dataset.confirmado === "1") { form.dataset.confirmado = ""; return; }
    ev.preventDefault();
    pendente = { form: form, submitter: ev.submitter || null };
    titulo.textContent = form.getAttribute("data-confirmar-titulo") || "Confirmar";
    texto.textContent = form.getAttribute("data-confirmar");
    ok.textContent = form.getAttribute("data-confirmar-botao") || "Confirmar";
    ok.className = "btn " + (form.getAttribute("data-confirmar-tipo") === "primario" ? "btn-primary" : "btn-danger");
    ok.disabled = false;
    modal.show();
  });

  ok.addEventListener("click", function () {
    if (!pendente) { return; }
    var p = pendente;
    pendente = null;
    ok.disabled = true;
    p.form.dataset.confirmado = "1";
    if (p.form.requestSubmit) { p.form.requestSubmit(p.submitter); } else { p.form.submit(); }
  });

  el.addEventListener("hidden.bs.modal", function () { pendente = null; });
})();