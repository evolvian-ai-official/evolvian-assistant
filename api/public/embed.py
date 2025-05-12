from fastapi import APIRouter, Response

router = APIRouter()

@router.get("/embed.js")
def serve_embed_js():
    js_content = """
(function () {
  const clientId = document.currentScript.getAttribute("data-client-id");
  if (!clientId) {
    console.warn("❌ Evolvian: Falta data-client-id en el script.");
    return;
  }

  const baseUrl = "redirectTo: "https://www.evolvianai.com/"; // ✅ Siempre producción

  console.log("📦 public_client_id:", clientId);
  console.log("🌐 Evolvian baseUrl:", baseUrl);

  // Crear wrapper
  const wrapper = document.createElement("div");
  wrapper.id = "evolvian-widget-wrapper";
  Object.assign(wrapper.style, {
    position: "fixed",
    bottom: "20px",
    right: "20px",
    zIndex: "9999",
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
  });
  document.body.appendChild(wrapper);

  // Botón flotante
  const button = document.createElement("button");
  button.innerText = "💬";
  button.title = "Chatea con Evolvian";
  Object.assign(button.style, {
    backgroundColor: "#4a90e2",
    color: "white",
    fontSize: "24px",
    border: "none",
    borderRadius: "50%",
    width: "56px",
    height: "56px",
    cursor: "pointer",
    boxShadow: "0 4px 8px rgba(0,0,0,0.3)",
    transition: "all 0.3s ease",
  });
  wrapper.appendChild(button);

  // Contenedor del iframe
  const widgetContainer = document.createElement("div");
  widgetContainer.id = "evolvian-chat-widget";
  Object.assign(widgetContainer.style, {
    display: "none",
    marginTop: "10px",
    width: "400px",
    height: "500px",
    border: "none",
    borderRadius: "12px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
    overflow: "hidden",
    background: "white",
  });
  wrapper.appendChild(widgetContainer);

  // Toggle
  let visible = false;
  button.addEventListener("click", () => {
    visible = !visible;
    widgetContainer.style.display = visible ? "block" : "none";
  });

  // Crear iframe
  const iframe = document.createElement("iframe");
  iframe.src = `${baseUrl}/chat-widget?public_client_id=${clientId}`;
  Object.assign(iframe.style, {
    width: "100%",
    height: "100%",
    border: "none",
    borderRadius: "12px",
  });
  iframe.setAttribute("title", "Evolvian AI Widget");
  iframe.setAttribute("allow", "clipboard-write; microphone");
  iframe.setAttribute("loading", "lazy");

  widgetContainer.appendChild(iframe);
})();
"""
    return Response(
        content=js_content,
        media_type="application/javascript; charset=utf-8",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cross-Origin-Resource-Policy": "cross-origin"
        }
    )

