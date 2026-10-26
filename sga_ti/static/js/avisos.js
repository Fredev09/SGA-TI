(function () {
  var DURACION = 7000;

  function cerrar(aviso) {
    aviso.classList.add("toast-oculto");
    window.setTimeout(function () {
      aviso.remove();
    }, 250);
  }

  function preparar(aviso) {
    var boton = aviso.querySelector(".toast-cerrar");
    if (boton) {
      boton.addEventListener("click", function () {
        cerrar(aviso);
      });
    }
    window.setTimeout(function () {
      cerrar(aviso);
    }, DURACION);
  }

  var avisos = document.querySelectorAll(".toast");
  for (var i = 0; i < avisos.length; i += 1) {
    preparar(avisos[i]);
  }
})();
