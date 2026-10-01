# DEPOT – catálogo estático

Sitio estático (HTML + CSS + JS) sin dependencias. Los productos se leen de `data/products.json`.

## Estructura
```
index.html
admin.py            ← administrador de productos (Python + Tkinter)
css/styles.css
js/app.js          ← aquí está CONFIG (número de WhatsApp, moneda)
data/products.json ← catálogo
images/            ← imágenes de productos
```

## Formato de cada producto
```json
{
  "id": 1,
  "nombre": "Cesta con asas",
  "descripcion": "Texto…",
  "precio": 160,
  "imagen": "images/producto-1.svg",
  "imagenes": ["images/producto-1.svg", "images/producto-1-b.svg"],
  "colores": [{ "nombre": "Negro", "hex": "#1b1b1b" }],
  "medidas": { "alto": 40, "ancho": 28, "profundidad": 20 },
  "stock": "disponible",
  "categoria": "Decoraciones"
}
```
- `stock`: `"disponible"` (verde) o `"a pedido"` (amarillo + aviso en el popup).
- `imagen`: la principal (miniatura). `imagenes`: todas, con la principal primero; acepta GIF. Si falta `imagenes`, se usa solo `imagen`.
- `medidas`: en centímetros.
- `categoria`: opcional; genera los filtros automáticamente.

## Probar en local
`fetch` no funciona con doble clic (file://). Usa un servidor:
```
python -m http.server 8000
```
y abre http://localhost:8000

## Publicar en GitHub Pages
Sube todo al repositorio → Settings → Pages → Deploy from branch → `main` / root.

## Administrar productos (admin.py)
```
python admin.py
```
Requiere Python 3 con Tkinter (viene incluido en Windows/macOS; en Linux: `sudo apt install python3-tk`).
Permite crear, editar y eliminar productos. Puedes agregar varias imágenes (la primera es la principal) y las nuevas se copian a `images/` usando el
"Nombre base" que escribas (`base.png`, `base-2.gif`…). Cada guardado actualiza `data/products.json`
(y deja una copia de seguridad en `data/products.json.bak`). Luego haz commit y push a GitHub.

## Carrito
El carrito vive en el navegador del cliente (`localStorage`, clave `depot_cart_v1`), así que no necesita servidor.
Guarda solo `id`, color y cantidad; nombres y precios se leen siempre del JSON actual.
Si cambias el `id` de un producto o lo eliminas, desaparece de los carritos que lo tenían.
