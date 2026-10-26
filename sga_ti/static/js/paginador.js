(function () {
  var TAMANOS = [5, 10, 20];

  function filasDe(contenedor) {
    if (contenedor.querySelector("table tbody")) {
      return Array.prototype.slice.call(contenedor.querySelectorAll("table tbody > tr"));
    }
    return Array.prototype.slice.call(contenedor.children).filter(function (hijo) {
      return hijo.tagName === "LI";
    });
  }

  function crearBoton(texto, etiqueta) {
    var boton = document.createElement("button");
    boton.type = "button";
    boton.className = "boton boton-icono";
    boton.textContent = texto;
    boton.setAttribute("aria-label", etiqueta);
    return boton;
  }

  function montar(contenedor) {
    var filas = filasDe(contenedor);
    if (filas.length === 0) {
      return;
    }
    var tamano = parseInt(contenedor.getAttribute("data-tamano"), 10) || 10;
    if (filas.length <= tamano) {
      return;
    }
    var pagina = 0;

    var barra = document.createElement("div");
    barra.className = "paginador";

    var resumen = document.createElement("span");
    resumen.className = "paginador-resumen";

    var controles = document.createElement("div");
    controles.className = "paginador-controles";

    var anterior = crearBoton("‹", "Página anterior");
    var siguiente = crearBoton("›", "Página siguiente");

    var selector = document.createElement("select");
    selector.className = "paginador-tamano";
    selector.setAttribute("aria-label", "Registros por página");
    TAMANOS.forEach(function (valor) {
      var opcion = document.createElement("option");
      opcion.value = String(valor);
      opcion.textContent = valor + " por página";
      if (valor === tamano) {
        opcion.selected = true;
      }
      selector.appendChild(opcion);
    });
    if (TAMANOS.indexOf(tamano) === -1) {
      var propia = document.createElement("option");
      propia.value = String(tamano);
      propia.textContent = tamano + " por página";
      propia.selected = true;
      selector.appendChild(propia);
    }

    function pintar() {
      var paginas = Math.max(1, Math.ceil(filas.length / tamano));
      if (pagina > paginas - 1) {
        pagina = paginas - 1;
      }
      filas.forEach(function (fila, indice) {
        var visible = indice >= pagina * tamano && indice < (pagina + 1) * tamano;
        fila.hidden = !visible;
      });
      resumen.textContent =
        "Página " + (pagina + 1) + " de " + paginas + " · " + filas.length + " registros";
      anterior.disabled = pagina === 0;
      siguiente.disabled = pagina === paginas - 1;
    }

    anterior.addEventListener("click", function () {
      if (pagina > 0) {
        pagina -= 1;
        pintar();
      }
    });

    siguiente.addEventListener("click", function () {
      var paginas = Math.max(1, Math.ceil(filas.length / tamano));
      if (pagina < paginas - 1) {
        pagina += 1;
        pintar();
      }
    });

    selector.addEventListener("change", function () {
      tamano = parseInt(selector.value, 10) || tamano;
      pagina = 0;
      pintar();
    });

    controles.appendChild(anterior);
    controles.appendChild(siguiente);
    controles.appendChild(selector);
    barra.appendChild(resumen);
    barra.appendChild(controles);
    contenedor.parentNode.insertBefore(barra, contenedor.nextSibling);
    pintar();
  }

  var contenedores = document.querySelectorAll("[data-paginar]");
  for (var i = 0; i < contenedores.length; i += 1) {
    montar(contenedores[i]);
  }
})();
