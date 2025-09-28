(function () {
  if (window !== window.parent) {
    console.warn("🛑 Ya estamos dentro de un iframe. No se inyecta otro.");
    return;
  }

  const scriptTag = document.currentScript;
  const publicClientId = scriptTag?.getAttribute("data-client-id");

  if (!publicClientId) {
    console.error("❌ Evolvian embed: Falta atributo data-client-id");
    return;
  }

  const iframe = document.createElement("iframe");
  iframe.src = `https://www.evolvianai.net/widget/index.html?public_client_id=${publicClientId}`;
  iframe.style.position = "fixed";
  iframe.style.bottom = "20px";
  iframe.style.right = "20px";
  iframe.style.width = "360px";
  iframe.style.height = "540px";
  iframe.style.border = "1px solid #274472";
  iframe.style.borderRadius = "12px";
  iframe.style.zIndex = "9999";
  iframe.style.backgroundColor = "#ffffff";
  iframe.style.boxShadow = "0px 4px 12px rgba(0,0,0,0.15)";
  iframe.setAttribute("allow", "clipboard-write");

  document.body.appendChild(iframe);
})();
