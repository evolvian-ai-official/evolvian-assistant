# 📘 Evolvian Blog API

Módulo que gestiona los **comentarios públicos del blog de Evolvian**.

---

## 🧩 Endpoints disponibles

### `GET /api/blog/comments?slug=...`
Devuelve los comentarios aprobados de un post.

**Ejemplo:**
```bash
curl https://evolvian-assistant.onrender.com/api/blog/comments?slug=nuevo-chat-widget-2-0
