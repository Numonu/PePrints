/* =========================================================
   CONFIGURACIÓN (edita estos valores)
   ========================================================= */
const CONFIG = {
  // Número de WhatsApp con código de país, solo dígitos (Perú = 51)
  whatsappNumber: "51930224555",
  // Símbolo de moneda
  currency: "S/",
  // Ruta del JSON de productos (relativa a index.html)
  productsUrl: "data/products.json",
  // Orden de los filtros de categoría (las categorías nuevas del JSON se agregan al final)
  categories: ["Juguetes", "Decoraciones", "Llaveros"],
  // Texto amarillo junto a los precios/totales del popup y del carrito.
  // Déjalo en "" para ocultarlo por completo.
  shippingLabel: "+ envío",
  // Imagen de respaldo si una imagen del JSON no carga
  fallbackImage: "images/placeholder.svg",
};

/* =========================================================
   ESTADO
   ========================================================= */
let products = [];
let activeCategory = "Todos";
let currentProduct = null;
let currentColor = null;
let lastFocused = null;

const $ = (sel) => document.querySelector(sel);
const grid = $("#productGrid");
const filtersEl = $("#filters");
const modal = $("#modal");
const cartEl = $("#cart");

/* =========================================================
   UTILIDADES
   ========================================================= */
const formatPrice = (n) =>
  `${CONFIG.currency} ${Number(n).toLocaleString("es-PE", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

// "disponible" -> verde | cualquier otro valor ("a pedido") -> amarillo
// Lista de imágenes del producto: "imagenes" si existe; si no, solo "imagen". La primera es la principal.
const getImages = (p) => (Array.isArray(p.imagenes) && p.imagenes.length ? p.imagenes : [p.imagen]);

const isAvailable = (p) => String(p.stock).trim().toLowerCase() === "disponible";
const stockLabel = (p) => (isAvailable(p) ? "Disponible" : "A pedido");
const stockClass = (p) => (isAvailable(p) ? "ok" : "order");

const waLink = (text) =>
  `https://wa.me/${CONFIG.whatsappNumber}${text ? `?text=${encodeURIComponent(text)}` : ""}`;

function setImg(img, src, alt) {
  img.onerror = () => {
    img.onerror = null;
    img.src = CONFIG.fallbackImage;
  };
  img.src = src;
  img.alt = alt || "";
}

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(props).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  });
  children.forEach((c) => node.appendChild(c));
  return node;
}

/* =========================================================
   CARGA DE DATOS
   ========================================================= */
async function loadProducts() {
  try {
    const res = await fetch(CONFIG.productsUrl, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // Acepta un arreglo directo o { "productos": [...] }
    products = Array.isArray(data) ? data : data.productos || [];
    renderFilters();
    renderGrid();
    renderCart();
  } catch (err) {
    console.error("No se pudo cargar el JSON:", err);
    grid.replaceChildren(
      el("p", {
        class: "state-msg",
        text: "No se pudieron cargar los productos. Si abriste el archivo con doble clic, usa un servidor local (por ejemplo: python -m http.server).",
      })
    );
  }
}

/* =========================================================
   FILTROS (se generan desde el campo opcional "categoria")
   ========================================================= */
function renderFilters() {
  const inJson = [...new Set(products.map((p) => p.categoria).filter(Boolean))];
  const cats = [...CONFIG.categories.filter((c) => inJson.includes(c)), ...inJson.filter((c) => !CONFIG.categories.includes(c))];
  if (cats.length === 0) {
    filtersEl.hidden = true;
    return;
  }
  filtersEl.hidden = false;
  filtersEl.replaceChildren(
    ...["Todos", ...cats].map((cat) => {
      const b = el("button", {
        class: "filter" + (cat === activeCategory ? " active" : ""),
        type: "button",
        role: "tab",
        "aria-selected": cat === activeCategory,
        text: cat,
      });
      b.addEventListener("click", () => {
        activeCategory = cat;
        renderFilters();
        renderGrid();
      });
      return b;
    })
  );
}

/* =========================================================
   GRILLA DE PRODUCTOS
   ========================================================= */
function renderGrid() {
  const list =
    activeCategory === "Todos" ? products : products.filter((p) => p.categoria === activeCategory);

  if (list.length === 0) {
    grid.replaceChildren(el("p", { class: "state-msg", text: "No hay productos en esta categoría." }));
    return;
  }

  grid.replaceChildren(
    ...list.map((p) => {
      const img = el("img", { loading: "lazy" });
      setImg(img, getImages(p)[0], p.nombre);

      const card = el("button", { class: "product", type: "button", "aria-label": `Ver ${p.nombre}` }, [
        el("div", { class: "product-img" }, [img]),
        el("span", { class: "product-name", text: p.nombre }),
        el("span", { class: "product-price", text: formatPrice(p.precio) }),
        el("span", { class: `badge ${stockClass(p)}`, text: stockLabel(p) }),
      ]);
      card.addEventListener("click", () => openModal(p));
      return card;
    })
  );
}

/* =========================================================
   POPUP
   ========================================================= */
function openModal(p) {
  currentProduct = p;
  lastFocused = document.activeElement;

  renderGallery(p);
  $("#mTitle").textContent = p.nombre;
  $("#mPrice").textContent = formatPrice(p.precio);
  $("#mDesc").textContent = p.descripcion || "";

  const badge = $("#mStock");
  badge.textContent = stockLabel(p);
  badge.className = `badge ${stockClass(p)}`;

  // Medidas
  const d = p.medidas || {};
  const dims = [
    ["Alto", d.alto],
    ["Ancho", d.ancho],
    ["Profundidad", d.profundidad],
  ].filter(([, v]) => v !== undefined && v !== null && v !== "");
  $("#mDims").replaceChildren(
    ...dims.map(([label, v]) => el("div", {}, [el("dt", { text: label }), el("dd", { text: `${v} cm` })]))
  );

  // Colores
  const colors = Array.isArray(p.colores) ? p.colores : [];
  currentColor = colors.length ? colors[0] : null;
  renderColors(colors);

  // Aviso cuando no es entrega inmediata
  $("#mWarning").hidden = isAvailable(p);

  updateWaLink();

  modal.hidden = false;
  document.body.classList.add("no-scroll");
  modal.querySelector(".modal-close").focus();
}

function renderGallery(p) {
  const imgs = getImages(p);
  const main = $("#mImg");
  const box = $("#mThumbs");
  setImg(main, imgs[0], p.nombre);

  if (imgs.length < 2) {
    box.hidden = true;
    box.replaceChildren();
    return;
  }
  box.hidden = false;
  box.replaceChildren(
    ...imgs.map((src, i) => {
      const t = el("img", { loading: "lazy" });
      setImg(t, src, `${p.nombre} – imagen ${i + 1}`);
      const b = el("button", { class: "thumb", type: "button", "aria-label": `Ver imagen ${i + 1}` }, [t]);
      if (i === 0) b.setAttribute("aria-current", "true");
      b.addEventListener("click", () => {
        setImg(main, src, p.nombre);
        box.querySelectorAll(".thumb").forEach((x) => x.removeAttribute("aria-current"));
        b.setAttribute("aria-current", "true");
      });
      return b;
    })
  );
}

function renderColors(colors) {
  const box = $("#mColors");
  const nameEl = $("#mColorName");

  if (colors.length === 0) {
    box.replaceChildren();
    nameEl.textContent = "Color único";
    return;
  }

  const paint = () => {
    box.replaceChildren(
      ...colors.map((c) => {
        const b = el("button", {
          class: "swatch",
          type: "button",
          role: "radio",
          title: c.nombre,
          "aria-label": c.nombre,
          "aria-checked": c === currentColor,
        });
        b.style.background = c.hex || "#ccc";
        b.addEventListener("click", () => {
          currentColor = c;
          paint();
          updateWaLink();
        });
        return b;
      })
    );
    nameEl.textContent = currentColor ? currentColor.nombre : "";
  };
  paint();
}

function updateWaLink() {
  const p = currentProduct;
  if (!p) return;
  let msg = `Hola, me interesa el producto ${p.nombre}`;
  if (currentColor) msg += ` en color ${currentColor.nombre}`;
  msg += ".";
  $("#mWa").href = waLink(msg);
}

function closeModal() {
  modal.hidden = true;
  document.body.classList.remove("no-scroll");
  currentProduct = null;
  if (lastFocused) lastFocused.focus();
}

$("#mAddCart").addEventListener("click", () => {
  if (!currentProduct) return;
  addToCart(currentProduct, currentColor ? currentColor.nombre : null);
  closeModal();
});

modal.addEventListener("click", (e) => {
  if (e.target.closest("[data-close]")) closeModal();
});

function trapTab(e, container) {
  const f = container.querySelectorAll("button:not([hidden]), a[href]");
  if (!f.length) return;
  const first = f[0];
  const last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}

document.addEventListener("keydown", (e) => {
  // El carrito está por encima del popup
  if (!cartEl.hidden) {
    if (e.key === "Escape") closeCart();
    else if (e.key === "Tab") trapTab(e, cartEl.querySelector(".cart-panel"));
    return;
  }
  if (modal.hidden) return;
  if (e.key === "Escape") closeModal();
  else if (e.key === "Tab") trapTab(e, modal);
});

/* =========================================================
   CARRITO (se guarda en localStorage: sobrevive a recargas)
   Cada línea: { id, color, qty }
   ========================================================= */
const CART_KEY = "depot_cart_v1";
const MAX_QTY = 99;
let cart = loadCart();
let toastTimer = null;

function loadCart() {
  try {
    const data = JSON.parse(localStorage.getItem(CART_KEY));
    return Array.isArray(data)
      ? data.filter((l) => l && l.id !== undefined && Number.isInteger(l.qty) && l.qty > 0)
      : [];
  } catch {
    return [];
  }
}

function saveCart() {
  try {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
  } catch {
    /* sin almacenamiento: el carrito funciona solo durante la sesión */
  }
}

const sameLine = (l, id, color) => l.id === id && (l.color || null) === (color || null);

function showToast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
}

function addToCart(p, colorName) {
  const line = cart.find((l) => sameLine(l, p.id, colorName));
  if (line) line.qty = Math.min(MAX_QTY, line.qty + 1);
  else cart.push({ id: p.id, color: colorName || null, qty: 1 });
  saveCart();
  renderCart();
  const btn = $("#cartBtn");
  btn.classList.remove("bump");
  void btn.offsetWidth; // reinicia la animación
  btn.classList.add("bump");
  showToast("Agregado al carrito");
}

function changeQty(id, color, delta) {
  const line = cart.find((l) => sameLine(l, id, color));
  if (!line) return;
  line.qty = Math.min(MAX_QTY, line.qty + delta);
  if (line.qty <= 0) cart = cart.filter((l) => l !== line);
  saveCart();
  renderCart();
}

function removeFromCart(id, color) {
  cart = cart.filter((l) => !sameLine(l, id, color));
  saveCart();
  renderCart();
}

// Une cada línea con su producto actual del JSON (si un producto ya no existe, se ignora)
function cartLines() {
  return cart
    .map((l) => ({ line: l, product: products.find((p) => p.id === l.id) }))
    .filter((x) => x.product);
}

function cartMessage(lines) {
  const items = lines.map(({ line, product }) => {
    let t = `• ${product.nombre}`;
    if (line.color) t += ` en color ${line.color}`;
    if (line.qty > 1) t += ` (x${line.qty})`;
    return t;
  });
  const total = lines.reduce((s, { line, product }) => s + product.precio * line.qty, 0);
  return (
    "Hola, me interesa solicitar el siguiente paquete de productos:\n\n" +
    items.join("\n")
  );
}

function renderCart() {
  const count = cart.reduce((s, l) => s + l.qty, 0);
  $("#cartCount").textContent = `(${count})`;

  const lines = cartLines();
  const list = $("#cartList");
  const empty = lines.length === 0;
  $("#cartEmpty").hidden = !empty;
  $("#cartFoot").hidden = empty;
  list.hidden = empty;

  list.replaceChildren(
    ...lines.map(({ line, product }) => {
      const img = el("img", { loading: "lazy" });
      setImg(img, getImages(product)[0], product.nombre);

      const minus = el("button", { type: "button", "aria-label": "Quitar una unidad", text: "−" });
      const plus = el("button", { type: "button", "aria-label": "Agregar una unidad", text: "+" });
      minus.addEventListener("click", () => changeQty(line.id, line.color, -1));
      plus.addEventListener("click", () => changeQty(line.id, line.color, 1));
      const del = el("button", { class: "cart-remove", type: "button", text: "Eliminar" });
      del.setAttribute("aria-label", `Eliminar ${product.nombre} del carrito`);
      del.addEventListener("click", () => removeFromCart(line.id, line.color));

      return el("li", { class: "cart-item" }, [
        el("div", { class: "cart-thumb" }, [img]),
        el("div", { class: "cart-info" }, [
          el("span", { class: "cart-name", text: product.nombre }),
          el("span", { class: "cart-meta", text: line.color ? `Color: ${line.color}` : "Color único" }),
          el("span", { class: "cart-meta", text: formatPrice(product.precio) }),
          el("div", { class: "cart-row" }, [
            el("div", { class: "qty" }, [minus, el("span", { text: String(line.qty) }), plus]),
            del,
          ]),
        ]),
      ]);
    })
  );

  if (!empty) {
    const total = lines.reduce((s, { line, product }) => s + product.precio * line.qty, 0);
    $("#cartTotal").textContent = formatPrice(total);
    $("#cartWarning").hidden = lines.every(({ product }) => isAvailable(product));
    $("#cartWa").href = waLink(cartMessage(lines));
  }
}

let cartLastFocus = null;
function openCart() {
  cartLastFocus = document.activeElement;
  renderCart();
  cartEl.hidden = false;
  document.body.classList.add("no-scroll");
  cartEl.querySelector(".cart-close").focus();
}

function closeCart() {
  cartEl.hidden = true;
  if (modal.hidden) document.body.classList.remove("no-scroll");
  if (cartLastFocus) cartLastFocus.focus();
}

$("#cartBtn").addEventListener("click", openCart);
cartEl.addEventListener("click", (e) => {
  if (e.target.closest("[data-cart-close]")) closeCart();
});
$("#cartClear").addEventListener("click", () => {
  cart = [];
  saveCart();
  renderCart();
});

renderCart();

/* =========================================================
   MENÚ MÓVIL Y EXTRAS
   ========================================================= */
const menuToggle = $("#menuToggle");
const mainNav = $("#mainNav");
menuToggle.addEventListener("click", () => {
  const open = mainNav.classList.toggle("open");
  menuToggle.setAttribute("aria-expanded", open);
});
mainNav.addEventListener("click", (e) => {
  if (e.target.tagName === "A") {
    mainNav.classList.remove("open");
    menuToggle.setAttribute("aria-expanded", "false");
  }
});

$("#headerWa").href = waLink("Hola, quisiera más información sobre sus productos.");
$("#footerWa").href = waLink("Hola, quisiera más información sobre sus productos.");
// Todos los elementos con data-ship muestran el mismo texto configurable
document.querySelectorAll("[data-ship]").forEach((n) => (n.textContent = CONFIG.shippingLabel));
$("#year").textContent = new Date().getFullYear();

loadProducts();
