(function () {
  const quadro = document.getElementById("quadro-kanban");
  if (!quadro) return;

  const csrf = quadro.dataset.csrf;
  const colunas = quadro.querySelectorAll("[data-coluna]");
  const dialogo = document.getElementById("dlg-rejeitar");
  const formRejeitar = document.getElementById("form-rejeitar");
  const campoFeedback = document.getElementById("feedback-rejeitar");
  const botaoCancelar = document.getElementById("cancelar-rejeitar");

  let cartao = null;
  let pendente = null;

  function aviso(texto, erro) {
    const div = document.createElement("div");
    div.className = "sigest-aviso alert shadow " + (erro ? "alert-danger" : "alert-success");
    div.setAttribute("role", "alert");
    div.textContent = texto;
    document.body.appendChild(div);
    setTimeout(function () { div.remove(); }, 5000);
  }

  function permitidos(el) {
    return (el.dataset.transicoes || "").split(",").filter(Boolean);
  }

  async function enviar(el, destino, feedback) {
    const dados = new FormData();
    dados.append("novo_estado", destino);
    dados.append("feedback", feedback || "");
    try {
      const resposta = await fetch(el.dataset.url, {
        method: "POST",
        headers: { "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest" },
        body: dados,
        credentials: "same-origin",
      });
      const json = await resposta.json();
      if (json.ok) {
        window.location.reload();
      } else {
        aviso((json.erros || ["Não foi possível mover a candidatura."]).join(" "), true);
      }
    } catch (e) {
      aviso("Não foi possível comunicar com o servidor.", true);
    }
  }

  quadro.querySelectorAll("[data-cartao][draggable='true']").forEach(function (el) {
    el.addEventListener("dragstart", function (e) {
      cartao = el;
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", el.dataset.id);
      el.classList.add("a-arrastar");
      const ok = permitidos(el);
      colunas.forEach(function (c) {
        if (ok.indexOf(c.dataset.estado) !== -1) c.classList.add("alvo-possivel");
      });
    });
    el.addEventListener("dragend", function () {
      el.classList.remove("a-arrastar");
      colunas.forEach(function (c) {
        c.classList.remove("alvo-possivel", "alvo-activo");
      });
      cartao = null;
    });
  });

  colunas.forEach(function (coluna) {
    coluna.addEventListener("dragover", function (e) {
      if (cartao && permitidos(cartao).indexOf(coluna.dataset.estado) !== -1) {
        e.preventDefault();
        coluna.classList.add("alvo-activo");
      }
    });
    coluna.addEventListener("dragleave", function () {
      coluna.classList.remove("alvo-activo");
    });
    coluna.addEventListener("drop", function (e) {
      e.preventDefault();
      coluna.classList.remove("alvo-activo");
      if (!cartao) return;
      const destino = coluna.dataset.estado;
      if (destino === cartao.dataset.estado) return;
      if (permitidos(cartao).indexOf(destino) === -1) {
        aviso("Movimento não permitido.", true);
        return;
      }
      if (destino === "REJEITADO") {
        pendente = cartao;
        campoFeedback.value = "";
        dialogo.showModal();
        campoFeedback.focus();
        return;
      }
      enviar(cartao, destino, "");
    });
  });

  formRejeitar.addEventListener("submit", function (e) {
    e.preventDefault();
    const texto = campoFeedback.value.trim();
    if (!texto) {
      aviso("O feedback é obrigatório ao rejeitar.", true);
      return;
    }
    if (!pendente) return;
    const el = pendente;
    pendente = null;
    dialogo.close();
    enviar(el, "REJEITADO", texto);
  });

  botaoCancelar.addEventListener("click", function () {
    pendente = null;
    dialogo.close();
  });
})();