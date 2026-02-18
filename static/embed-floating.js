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
  const apiOrigin = baseOrigin.replace(/\/static$/, "");
//const baseOrigin = "http://localhost:8001/static";
  let showScheduleFlag = false;
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
    transition: "opacity 180ms ease, transform 200ms ease, box-shadow 180ms ease",
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

  // Estado inicial → logo
  button.appendChild(logo);

  // 🔹 Botón de cierre (dockeado al widget cuando está abierto)
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.setAttribute("aria-label", "Cerrar asistente");
  closeButton.textContent = "×";
  Object.assign(closeButton.style, {
    position: "fixed",
    zIndex: "10001",
    width: "42px",
    height: "42px",
    borderRadius: "14px",
    border: "1px solid rgba(31, 62, 105, 0.18)",
    background: "linear-gradient(155deg, rgba(255,255,255,0.96) 0%, rgba(241,247,255,0.92) 100%)",
    color: "#1f3e69",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 12px 28px rgba(21, 45, 79, 0.26)",
    cursor: "pointer",
    backdropFilter: "blur(10px)",
    fontSize: "24px",
    lineHeight: "1",
    fontWeight: "500",
    opacity: "0",
    transform: "scale(0.85)",
    pointerEvents: "none",
    transition: "opacity 180ms ease, transform 180ms ease, box-shadow 180ms ease",
  });

  // 🟦 Iframe oculto (ventana flotante, tamaño fijo)
  // Bump this when widget UI changes to force fresh widget shell on client sites.
  const widgetBuildVersion = "2026-02-18-04";
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

  function applyLauncherVisibility() {
    if (isOpen) {
      button.style.opacity = "0";
      button.style.transform = "scale(0.82)";
      button.style.pointerEvents = "none";
    } else {
      button.style.opacity = "1";
      button.style.transform = "scale(1)";
      button.style.pointerEvents = "auto";
    }
  }

  function applyCloseButtonPosition() {
    const isMobile = window.matchMedia("(max-width: 640px)").matches;
    if (isMobile) {
      closeButton.style.top = "16px";
      closeButton.style.right = "16px";
      closeButton.style.bottom = "auto";
      closeButton.style.width = "40px";
      closeButton.style.height = "40px";
    } else {
      closeButton.style.top = "auto";
      closeButton.style.right = "8px";
      closeButton.style.bottom = "618px";
      closeButton.style.width = "42px";
      closeButton.style.height = "42px";
    }
  }

  function applyCloseButtonVisibility() {
    if (isOpen) {
      closeButton.style.opacity = "1";
      closeButton.style.transform = "scale(1)";
      closeButton.style.pointerEvents = "auto";
    } else {
      closeButton.style.opacity = "0";
      closeButton.style.transform = "scale(0.85)";
      closeButton.style.pointerEvents = "none";
    }
  }

  async function loadScheduleVisibility() {
    try {
      const res = await fetch(
        `${apiOrigin}/widget/calendar/visibility?public_client_id=${encodeURIComponent(clientId)}`
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "No se pudo cargar visibilidad");
      const isVisible = Boolean(data?.show_agenda_in_chat_widget ?? false);
      const calendarStatus = String(data?.calendar_status || "inactive").toLowerCase();
      showScheduleFlag = isVisible && calendarStatus === "active";
    } catch {
      showScheduleFlag = false;
    }
  }

  loadScheduleVisibility();

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
    applyLauncherVisibility();
    applyCloseButtonVisibility();
  }

  // 🟦 Toggle mostrar/ocultar
  button.addEventListener("click", () => {
    isOpen = !isOpen;
    if (isOpen) {
      applyCloseButtonPosition();
      iframe.style.display = "block";
      scheduleFlag.style.display = showScheduleFlag ? "block" : "none";
      setTimeout(() => {
        iframe.style.transform = "translateY(0)";
        iframe.style.opacity = "1";
        postWidgetView("chat");
      }, 10);
    } else {
      closeWidget();
    }
    applyLauncherVisibility();
    applyCloseButtonVisibility();
  });

  scheduleFlag.addEventListener("click", () => {
    if (!showScheduleFlag) return;
    if (!isOpen) {
      isOpen = true;
      applyCloseButtonPosition();
      iframe.style.display = "block";
      scheduleFlag.style.display = "block";
      setTimeout(() => {
        iframe.style.transform = "translateY(0)";
        iframe.style.opacity = "1";
      }, 10);
      applyLauncherVisibility();
      applyCloseButtonVisibility();
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

  window.addEventListener("resize", () => {
    applyCloseButtonPosition();
  });

  closeButton.addEventListener("click", () => {
    if (isOpen) closeWidget();
  });

  // 🟦 Insertar en el DOM
  applyCloseButtonPosition();
  applyLauncherVisibility();
  applyCloseButtonVisibility();
  document.body.appendChild(button);
  document.body.appendChild(iframe);
  document.body.appendChild(scheduleFlag);
  document.body.appendChild(closeButton);
})();
