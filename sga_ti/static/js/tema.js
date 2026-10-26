(function () {
  var CLAVE = "sga-ti-tema";

  function temaGuardado() {
    try {
      return localStorage.getItem(CLAVE) === "oscuro" ? "oscuro" : "claro";
    } catch (error) {
      return "claro";
    }
  }

  function aplicar(tema) {
    document.body.classList.toggle("theme-dark", tema === "oscuro");
    var controles = document.querySelectorAll("[data-tema]");
    for (var i = 0; i < controles.length; i += 1) {
      controles[i].checked = controles[i].value === tema;
    }
  }

  aplicar(temaGuardado());

  document.addEventListener("change", function (evento) {
    var control = evento.target;
    if (!control.hasAttribute || !control.hasAttribute("data-tema")) {
      return;
    }
    aplicar(control.value);
    try {
      localStorage.setItem(CLAVE, control.value);
    } catch (error) {
      return;
    }
  });
})();
