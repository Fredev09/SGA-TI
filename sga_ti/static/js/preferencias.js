(function () {
  var CLAVE_TEMA = "sga-ti-tema";
  var CLAVE_FUENTE = "sga-ti-fuente";
  var NOMBRES = {
    tema: { claro: "Modo claro", oscuro: "Modo oscuro" },
    fuente: { compacta: "Compacta", normal: "Normal", amplia: "Amplia" }
  };

  function leer(clave, opciones, defecto) {
    try {
      var valor = localStorage.getItem(clave);
      return opciones.indexOf(valor) >= 0 ? valor : defecto;
    } catch (error) {
      return defecto;
    }
  }

  function guardar(clave, valor) {
    try {
      localStorage.setItem(clave, valor);
    } catch (error) {
      return;
    }
  }

  function marcar(tipo, valor) {
    var controles = document.querySelectorAll("[data-" + tipo + "]");
    for (var i = 0; i < controles.length; i += 1) {
      controles[i].checked = controles[i].value === valor;
    }
    var etiqueta = document.querySelector("[data-" + tipo + "-activo]");
    if (etiqueta) {
      etiqueta.textContent = NOMBRES[tipo][valor];
    }
  }

  function aplicarTema(tema) {
    document.body.classList.toggle("theme-dark", tema === "oscuro");
    marcar("tema", tema);
  }

  function aplicarFuente(fuente) {
    document.body.classList.toggle("fuente-compacta", fuente === "compacta");
    document.body.classList.toggle("fuente-amplia", fuente === "amplia");
    marcar("fuente", fuente);
  }

  aplicarTema(leer(CLAVE_TEMA, ["claro", "oscuro"], "claro"));
  aplicarFuente(leer(CLAVE_FUENTE, ["compacta", "normal", "amplia"], "normal"));

  document.addEventListener("change", function (evento) {
    var control = evento.target;
    if (!control.hasAttribute) {
      return;
    }
    if (control.hasAttribute("data-tema")) {
      aplicarTema(control.value);
      guardar(CLAVE_TEMA, control.value);
    } else if (control.hasAttribute("data-fuente")) {
      aplicarFuente(control.value);
      guardar(CLAVE_FUENTE, control.value);
    }
  });
})();
