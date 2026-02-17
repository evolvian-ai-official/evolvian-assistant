// embed-floating.js
(function () {
  // 🚫 Evitar ejecución dentro de iframes o del propio widget
  const isIframe = window.self !== window.top;
  const isWidget = window.location.pathname.includes("widget.html");

  if (isIframe || isWidget) {
    console.log("Evolvian Floating: bloqueado dentro de iframe/widget.");
    return; // 🔒 NO SIGUE
  }

  // Detecta el script que cargó este archivo
  const script =
    document.currentScript ||
    document.querySelector('script[src*="embed-floating.js"]');

  const clientId = script?.getAttribute("data-public-client-id");
  if (!clientId) {
    console.error("❌ Evolvian Floating: data-public-client-id no encontrado");
    return;
  }

  console.log("✅ Evolvian Floating cargado con clientId:", clientId);

 const baseOrigin = "https://evolvian-assistant.onrender.com/static";
//const baseOrigin = "http://localhost:8001/static";
  // 🟦 Botón flotante
  let isOpen = false;
  const button = document.createElement("button");
  Object.assign(button.style, {
    position: "fixed",
    bottom: "24px",
    right: "24px",
    width: "64px",
    height: "64px",
    borderRadius: "50%",
    border: "none",
    overflow: "hidden",
    cursor: "pointer",
    zIndex: "10000",
    boxShadow: "0 4px 8px rgba(0,0,0,0.15)",
    padding: "0",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "white",
  });

  // 🔹 Logo Evolvian (estado cerrado)
  const logo = document.createElement("img");
  logo.src = `${baseOrigin}/e1.png`;
  logo.alt = "Evolvian Logo";
  Object.assign(logo.style, {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    borderRadius: "50%",
  });

  // 🔹 Ícono de cierre (estado abierto)
  const closeIcon = document.createElement("span");
  closeIcon.innerText = "×";
  Object.assign(closeIcon.style, {
    fontSize: "32px",
    color: "white",
    background: "#4a90e2",
    width: "100%",
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  });

  // Estado inicial → logo
  button.appendChild(logo);

  // 🟦 Iframe oculto (ventana flotante, tamaño fijo)
  // Bump this when widget UI changes to force fresh widget shell on client sites.
  const widgetBuildVersion = "2026-02-17-01";
  const iframe = document.createElement("iframe");
  iframe.src = `${baseOrigin}/widget.html?public_client_id=${encodeURIComponent(clientId)}&v=${encodeURIComponent(widgetBuildVersion)}`;
  Object.assign(iframe.style, {
    position: "fixed",
    bottom: "90px",
    right: "24px",
    width: "360px",
    height: "520px",
    border: "none",
    borderRadius: "12px",
    display: "none",
    zIndex: "9999",
    background: "white",
    boxShadow: "0 0 12px rgba(0,0,0,0.2)",
    transition: "transform 0.3s ease, opacity 0.3s ease",
    transform: "translateY(20px)",
    opacity: "0",
  });

  // 🟦 Bandera lateral "Agendar" (lado izquierdo del widget)
  const scheduleFlag = document.createElement("button");
  scheduleFlag.textContent = "Agendar";
  Object.assign(scheduleFlag.style, {
    position: "fixed",
    right: "392px",
    bottom: "300px",
    border: "none",
    borderRadius: "10px 0 0 10px",
    background: "#4a90e2",
    color: "#ffffff",
    fontWeight: "700",
    fontSize: "13px",
    padding: "10px 12px",
    cursor: "pointer",
    zIndex: "9998",
    boxShadow: "0 4px 10px rgba(0,0,0,0.15)",
    display: "none",
  });

  function postWidgetView(view) {
    try {
      iframe.contentWindow?.postMessage(
        { type: "EVOLVIAN_WIDGET_VIEW", view },
        "*"
      );
    } catch (err) {
      console.warn("No se pudo enviar vista al widget:", err);
    }
  }

  function closeWidget() {
    isOpen = false;
    iframe.style.transform = "translateY(20px)";
    iframe.style.opacity = "0";
    scheduleFlag.style.display = "none";
    setTimeout(() => {
      iframe.style.display = "none";
    }, 300);
    button.innerHTML = "";
    button.appendChild(logo);
  }

  // 🟦 Toggle mostrar/ocultar
  button.addEventListener("click", () => {
    isOpen = !isOpen;
    if (isOpen) {
      iframe.style.display = "block";
      scheduleFlag.style.display = "block";
      setTimeout(() => {
        iframe.style.transform = "translateY(0)";
        iframe.style.opacity = "1";
        postWidgetView("chat");
      }, 10);
    } else {
      closeWidget();
    }

    button.innerHTML = "";
    button.appendChild(isOpen ? closeIcon : logo);
  });

  scheduleFlag.addEventListener("click", () => {
    if (!isOpen) {
      isOpen = true;
      iframe.style.display = "block";
      scheduleFlag.style.display = "block";
      setTimeout(() => {
        iframe.style.transform = "translateY(0)";
        iframe.style.opacity = "1";
      }, 10);
      button.innerHTML = "";
      button.appendChild(closeIcon);
    }
    postWidgetView("calendar");
  });

  // 🟦 Cerrar con tecla ESC
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen) {
      closeWidget();
    }
  });

  window.addEventListener("message", (event) => {
    const payload = event?.data;
    if (!payload || payload.type !== "EVOLVIAN_WIDGET_CLOSE") return;
    if (isOpen) closeWidget();
  });

  // 🟦 Insertar en el DOM
  document.body.appendChild(button);
  document.body.appendChild(iframe);
  document.body.appendChild(scheduleFlag);
})();
