#!/usr/bin/env python3
"""
Administrador de productos (interfaz simple con Tkinter, sin dependencias externas).

Uso:   python admin.py      (desde la raíz del proyecto)

- Lee y escribe data/products.json
- Cada producto puede tener varias imágenes (incluye GIF). La primera es la principal
  y es la que se ve en la miniatura.
- Al guardar, las imágenes nuevas se copian a images/ usando el "Nombre base" que escribas
  (llavero-gato.png, llavero-gato-2.gif, llavero-gato-3.jpg…). La extensión se conserva.
- Vista previa de la imagen seleccionada (JPG/WEBP requieren Pillow: pip install pillow).
- Presets de color: se guardan en admin_presets.json, junto a este script.
- Al guardar un producto se hace git push automático (data/products.json e images/).
"""
import json
import os
import re
import shutil
import subprocess
import threading
import unicodedata
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

try:  # opcional: con Pillow la vista previa también funciona con JPG y WEBP
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "data" / "products.json"
PRESETS_PATH = ROOT / "admin_presets.json"   # presets de color (no se sube a GitHub)
IMG_DIR = ROOT / "images"
IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")
PREVIEW_SIZE = 140   # lado (px) del recuadro de vista previa

DEFAULT_CATEGORIES = ["Juguetes", "Decoraciones", "Llaveros"]
STOCK_OPTIONS = ["disponible", "a pedido"]


# ------------------------------------------------------------------ datos
def load_products():
    if not JSON_PATH.exists():
        return []
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("productos", [])


def save_products(products):
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    if JSON_PATH.exists():  # copia de seguridad por si algo sale mal
        shutil.copy2(JSON_PATH, JSON_PATH.with_suffix(".json.bak"))
    tmp = JSON_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(JSON_PATH)


HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")


def load_presets():
    """Presets de color guardados: [{"nombre":..., "hex":...}]. Si no hay archivo, lista vacía."""
    try:
        with open(PRESETS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for c in data if isinstance(data, list) else []:
        if isinstance(c, dict) and c.get("nombre") and HEX_RE.fullmatch(str(c.get("hex", ""))):
            out.append({"nombre": str(c["nombre"]), "hex": c["hex"].lower()})
    return out


def save_presets(presets):
    tmp = PRESETS_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(PRESETS_PATH)


SITE_URL = "https://numonu.github.io/PePrints/"
PAGES_WAIT = 60   # segundos que tarda aprox. GitHub Pages en actualizar

GIT_PATHS = ["data/products.json", "images"]   # lo único que se sube
GIT_LOCK = threading.Lock()


def git_publish(message):
    """git add + commit + push de products.json e images/. Devuelve (ok, detalle)."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")  # que nunca se quede esperando una contraseña
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # sin ventana de consola en Windows

    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, timeout=180,
                              creationflags=flags)

    try:
        with GIT_LOCK:
            r = git("add", "-A", "--", *GIT_PATHS)
            if r.returncode:
                return False, r.stderr.strip() or r.stdout.strip()
            if git("status", "--porcelain", "--", *GIT_PATHS).stdout.strip():
                r = git("commit", "-m", message, "--", *GIT_PATHS)
                if r.returncode:
                    return False, r.stderr.strip() or r.stdout.strip()
            r = git("push")
            if r.returncode:
                return False, r.stderr.strip() or r.stdout.strip()
        return True, ""
    except FileNotFoundError:
        return False, "No se encontró 'git' en este equipo."
    except subprocess.TimeoutExpired:
        return False, "git tardó demasiado (¿sin internet o pidiendo credenciales?)."


def product_images(p):
    """Lista de imágenes de un producto (la primera es la principal)."""
    imgs = p.get("imagenes") or ([p["imagen"]] if p.get("imagen") else [])
    return list(imgs)


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "producto"


def parse_number(text, field, required=True):
    text = text.strip().replace(",", ".")
    if not text:
        if required:
            raise ValueError(f"El campo '{field}' es obligatorio.")
        return None
    try:
        n = float(text)
    except ValueError:
        raise ValueError(f"'{field}' debe ser un número.")
    if n < 0:
        raise ValueError(f"'{field}' no puede ser negativo.")
    return int(n) if n == int(n) else n


def load_preview(path, box=PREVIEW_SIZE):
    """Miniatura de una imagen. Devuelve (PhotoImage | None, (ancho, alto) | None, mensaje)."""
    path = Path(path)
    ext = path.suffix.lower()
    if not path.exists():
        return None, None, "Archivo no encontrado"
    if ext == ".svg":
        return None, None, "SVG: sin vista previa"
    try:
        if Image is not None:                      # con Pillow: PNG, JPG, WEBP, GIF…
            with Image.open(path) as im:
                size = im.size
                im.thumbnail((box, box))
                thumb = im.convert("RGBA")
            return ImageTk.PhotoImage(thumb), size, ""
        if ext in (".png", ".gif"):                # sin Pillow: solo lo que Tk sabe leer
            img = tk.PhotoImage(file=str(path))
            w, h = img.width(), img.height()
            f = max(1, -(-w // box), -(-h // box))  # reducción entera (redondeo hacia arriba)
            if f > 1:
                img = img.subsample(f, f)
            return img, (w, h), ""
        return None, None, f"Sin vista previa para {ext}\n(instala Pillow:\npip install pillow)"
    except Exception:
        return None, None, "No se pudo mostrar\nla imagen"


# ------------------------------------------------------------------ interfaz
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Administrador de productos")
        self.geometry("980x780")
        self.minsize(860, 720)

        self.products = load_products()
        self.presets = load_presets()   # presets de color guardados
        self._preview_photo = None      # referencia a la miniatura (si no, Tk la borra)
        self.current = None        # índice del producto en edición (None = nuevo)
        self.colors = []           # [{"nombre":..., "hex":...}]
        self.images = []           # [{"path": "images/x.png" | None, "src": Path | None}]

        self._build()
        self.refresh_list()
        self.new_product()

    # ---- construcción de la ventana
    def _build(self):
        left = ttk.Frame(self, padding=8)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Productos").pack(anchor="w")
        self.listbox = tk.Listbox(left, width=30, exportselection=False)
        self.listbox.pack(fill="y", expand=True, pady=4)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        ttk.Button(left, text="Nuevo producto", command=self.new_product).pack(fill="x")
        ttk.Button(left, text="Eliminar seleccionado", command=self.delete_product).pack(fill="x", pady=(4, 0))

        right = ttk.Frame(self, padding=8)
        right.pack(side="left", fill="both", expand=True)
        right.columnconfigure(1, weight=1)

        self.v_nombre = tk.StringVar()
        self.v_precio = tk.StringVar()
        self.v_categoria = tk.StringVar()
        self.v_stock = tk.StringVar(value=STOCK_OPTIONS[0])
        self.v_alto = tk.StringVar()
        self.v_ancho = tk.StringVar()
        self.v_prof = tk.StringVar()
        self.v_imgname = tk.StringVar()
        self.v_cname = tk.StringVar()
        self.v_chex = tk.StringVar(value="#000000")

        r = 0
        ttk.Label(right, text="Nombre *").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Entry(right, textvariable=self.v_nombre).grid(row=r, column=1, columnspan=3, sticky="ew")

        r += 1
        ttk.Label(right, text="Descripción").grid(row=r, column=0, sticky="nw", pady=3)
        self.t_desc = tk.Text(right, height=4, wrap="word")
        self.t_desc.grid(row=r, column=1, columnspan=3, sticky="ew")

        r += 1
        ttk.Label(right, text="Precio *").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Entry(right, textvariable=self.v_precio, width=12).grid(row=r, column=1, sticky="w")

        r += 1
        ttk.Label(right, text="Categoría").grid(row=r, column=0, sticky="w", pady=3)
        self.cb_cat = ttk.Combobox(right, textvariable=self.v_categoria)
        self.cb_cat.grid(row=r, column=1, sticky="w")

        r += 1
        ttk.Label(right, text="Stock").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Combobox(right, textvariable=self.v_stock, values=STOCK_OPTIONS, state="readonly", width=14).grid(
            row=r, column=1, sticky="w")

        r += 1
        ttk.Label(right, text="Medidas (cm)").grid(row=r, column=0, sticky="w", pady=3)
        m = ttk.Frame(right)
        m.grid(row=r, column=1, columnspan=3, sticky="w")
        for label, var in (("Alto", self.v_alto), ("Ancho", self.v_ancho), ("Profundidad", self.v_prof)):
            ttk.Label(m, text=label).pack(side="left", padx=(0, 3))
            ttk.Entry(m, textvariable=var, width=7).pack(side="left", padx=(0, 12))

        r += 1
        ttk.Separator(right).grid(row=r, column=0, columnspan=4, sticky="ew", pady=8)

        r += 1
        ttk.Label(right, text="Imágenes *").grid(row=r, column=0, sticky="nw")
        imf = ttk.Frame(right)
        imf.grid(row=r, column=1, columnspan=3, sticky="ew")
        self.lb_images = tk.Listbox(imf, height=6, width=38, exportselection=False)
        self.lb_images.pack(side="left")
        self.lb_images.bind("<<ListboxSelect>>", self.update_preview)
        ib = ttk.Frame(imf)
        ib.pack(side="left", padx=10, anchor="n")
        for text, cmd in (("Agregar imágenes…", self.add_images), ("Quitar seleccionada", self.remove_image),
                          ("Subir", lambda: self.move_image(-1)), ("Bajar", lambda: self.move_image(1)),
                          ("Hacer principal ★", self.make_main)):
            ttk.Button(ib, text=text, command=cmd).pack(fill="x", pady=1)
        pv = ttk.Frame(imf)                       # vista previa de la imagen seleccionada
        pv.pack(side="left", anchor="n")
        self.cv_preview = tk.Canvas(pv, width=PREVIEW_SIZE, height=PREVIEW_SIZE, bg="#f2f2f2",
                                    highlightthickness=1, highlightbackground="#bbb")
        self.cv_preview.pack()
        self.lbl_preview = ttk.Label(pv, text="", foreground="#666")
        self.lbl_preview.pack()
        r += 1
        ttk.Label(right, text="★ = principal (miniatura). Acepta PNG, JPG, WEBP, GIF y SVG.",
                  foreground="#666").grid(row=r, column=1, columnspan=3, sticky="w")
        r += 1
        ttk.Label(right, text="Nombre base").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Entry(right, textvariable=self.v_imgname, width=30).grid(row=r, column=1, sticky="w")
        ttk.Label(right, text="ej. llavero-gato → llavero-gato.png, llavero-gato-2.gif…",
                  foreground="#666").grid(row=r, column=2, columnspan=2, sticky="w", padx=8)

        r += 1
        ttk.Separator(right).grid(row=r, column=0, columnspan=4, sticky="ew", pady=8)

        r += 1
        ttk.Label(right, text="Colores").grid(row=r, column=0, sticky="nw")
        cf = ttk.Frame(right)
        cf.grid(row=r, column=1, columnspan=3, sticky="ew")
        self.lb_colors = tk.Listbox(cf, height=5, width=32, exportselection=False)
        self.lb_colors.pack(side="left")
        cc = ttk.Frame(cf)
        cc.pack(side="left", padx=10, anchor="n")
        row1 = ttk.Frame(cc); row1.pack(anchor="w")
        ttk.Label(row1, text="Nombre").pack(side="left")
        ttk.Entry(row1, textvariable=self.v_cname, width=16).pack(side="left", padx=4)
        row2 = ttk.Frame(cc); row2.pack(anchor="w", pady=3)
        ttk.Label(row2, text="Hex").pack(side="left")
        ttk.Entry(row2, textvariable=self.v_chex, width=9).pack(side="left", padx=4)
        ttk.Button(row2, text="Elegir color…", command=self.pick_color).pack(side="left")
        row3 = ttk.Frame(cc); row3.pack(anchor="w")
        ttk.Button(row3, text="Agregar color", command=self.add_color).pack(side="left")
        ttk.Button(row3, text="Quitar seleccionado", command=self.remove_color).pack(side="left", padx=4)

        r += 1
        ttk.Label(right, text="Presets").grid(row=r, column=0, sticky="w", pady=(8, 0))
        pf = ttk.Frame(right)
        pf.grid(row=r, column=1, columnspan=3, sticky="w", pady=(8, 0))
        self.v_preset = tk.StringVar()
        self.cb_preset = ttk.Combobox(pf, textvariable=self.v_preset, state="readonly", width=26)
        self.cb_preset.pack(side="left")
        self.cb_preset.bind("<<ComboboxSelected>>", self.on_preset_select)
        self.sw_preset = tk.Label(pf, width=3, relief="solid", borderwidth=1)   # muestra del color
        self.sw_preset.pack(side="left", padx=6)
        self._sw_default = self.sw_preset.cget("bg")
        ttk.Button(pf, text="Añadir al producto", command=self.use_preset).pack(side="left")
        ttk.Button(pf, text="Guardar como preset", command=self.save_preset).pack(side="left", padx=4)
        ttk.Button(pf, text="Borrar preset", command=self.delete_preset).pack(side="left")
        self.refresh_presets()

        r += 1
        bar = ttk.Frame(right)
        bar.grid(row=r, column=0, columnspan=4, sticky="e", pady=16)
        self.lbl_mode = ttk.Label(bar, text="")
        self.lbl_mode.pack(side="left", padx=12)
        self.lbl_git = ttk.Label(bar, text="")
        self.lbl_git.pack(side="left", padx=12)
        self._view_timer = None
        self.btn_view = ttk.Button(bar, text="Ver cambios", command=self.open_site, state="disabled")
        self.btn_view.pack(side="left", padx=(0, 8))
        ttk.Button(bar, text="Guardar producto", command=self.save).pack(side="left")

    # ---- lista
    def refresh_list(self, select=None):
        self.listbox.delete(0, "end")
        for p in self.products:
            self.listbox.insert("end", f"{p.get('id', '?')} · {p.get('nombre', '')}")
        cats = list(dict.fromkeys(DEFAULT_CATEGORIES + [p.get("categoria") for p in self.products if p.get("categoria")]))
        self.cb_cat["values"] = cats
        if select is not None:
            self.listbox.selection_set(select)
            self.listbox.see(select)

    def on_select(self, _event=None):
        sel = self.listbox.curselection()
        if sel:
            self.load_into_form(sel[0])

    # ---- formulario
    def clear_form(self):
        for v in (self.v_nombre, self.v_precio, self.v_categoria, self.v_alto, self.v_ancho, self.v_prof,
                  self.v_imgname, self.v_cname):
            v.set("")
        self.v_stock.set(STOCK_OPTIONS[0])
        self.v_chex.set("#000000")
        self.t_desc.delete("1.0", "end")
        self.colors = []
        self.images = []
        self.refresh_images()
        self.refresh_colors()

    def new_product(self):
        self.current = None
        self.listbox.selection_clear(0, "end")
        self.clear_form()
        self.lbl_mode.config(text="Nuevo producto")

    def load_into_form(self, idx):
        p = self.products[idx]
        self.current = idx
        self.clear_form()
        self.v_nombre.set(p.get("nombre", ""))
        self.t_desc.insert("1.0", p.get("descripcion", ""))
        self.v_precio.set(str(p.get("precio", "")))
        self.v_categoria.set(p.get("categoria", ""))
        self.v_stock.set(p.get("stock", STOCK_OPTIONS[0]))
        d = p.get("medidas", {})
        self.v_alto.set(str(d.get("alto", "")))
        self.v_ancho.set(str(d.get("ancho", "")))
        self.v_prof.set(str(d.get("profundidad", "")))
        paths = product_images(p)
        self.images = [{"path": x, "src": None} for x in paths]
        self.v_imgname.set(Path(paths[0]).stem if paths else "")
        self.refresh_images()
        self.colors = [dict(c) for c in p.get("colores", [])]
        self.refresh_colors()
        self.lbl_mode.config(text=f"Editando producto {p.get('id')}")

    # ---- imágenes
    def refresh_images(self, select=None):
        self.lb_images.delete(0, "end")
        for i, e in enumerate(self.images):
            star = "★ " if i == 0 else "   "
            label = e["path"] if e["src"] is None else f"(nueva) {e['src'].name}"
            self.lb_images.insert("end", star + label)
        if select is not None and 0 <= select < len(self.images):
            self.lb_images.selection_set(select)
        self.update_preview()

    def update_preview(self, _event=None):
        """Muestra la imagen seleccionada (o la principal si no hay ninguna seleccionada)."""
        c = self.cv_preview
        c.delete("all")
        self._preview_photo = None
        self.lbl_preview.config(text="")
        sel = self._sel_image()
        i = sel if sel is not None else (0 if self.images else None)
        mid = PREVIEW_SIZE // 2
        if i is None or i >= len(self.images):
            c.create_text(mid, mid, text="Sin imágenes", fill="#888")
            return
        e = self.images[i]
        path = e["src"] if e["src"] is not None else ROOT / e["path"]
        photo, size, msg = load_preview(path)
        if photo is None:
            c.create_text(mid, mid, text=msg, fill="#888", justify="center", width=PREVIEW_SIZE - 16)
            return
        self._preview_photo = photo
        c.create_image(mid, mid, image=photo)
        info = f"{size[0]}×{size[1]} px"
        try:
            info += f" · {Path(path).stat().st_size // 1024} KB"
        except OSError:
            pass
        self.lbl_preview.config(text=("★ " if i == 0 else "") + info)

    def add_images(self):
        paths = filedialog.askopenfilenames(
            title="Elegir imágenes",
            filetypes=[("Imágenes", " ".join("*" + e for e in IMG_EXTS)), ("Todos", "*.*")])
        for p in paths:
            self.images.append({"path": None, "src": Path(p)})
        if paths and not self.v_imgname.get().strip():
            self.v_imgname.set(slugify(self.v_nombre.get()) if self.v_nombre.get().strip() else slugify(Path(paths[0]).stem))
        self.refresh_images()

    def _sel_image(self):
        sel = self.lb_images.curselection()
        return sel[0] if sel else None

    def remove_image(self):
        i = self._sel_image()
        if i is not None:
            del self.images[i]
            self.refresh_images(select=min(i, len(self.images) - 1))

    def move_image(self, delta):
        i = self._sel_image()
        if i is None or not 0 <= i + delta < len(self.images):
            return
        self.images[i], self.images[i + delta] = self.images[i + delta], self.images[i]
        self.refresh_images(select=i + delta)

    def make_main(self):
        i = self._sel_image()
        if i is not None and i > 0:
            self.images.insert(0, self.images.pop(i))
            self.refresh_images(select=0)

    # ---- colores
    def refresh_colors(self):
        self.lb_colors.delete(0, "end")
        for c in self.colors:
            self.lb_colors.insert("end", f"{c['nombre']}  ({c['hex']})")

    def pick_color(self):
        rgb, hexv = colorchooser.askcolor(color=self.v_chex.get() or "#000000", title="Elegir color")
        if hexv:
            self.v_chex.set(hexv)

    def add_color(self):
        name = self.v_cname.get().strip()
        hexv = self.v_chex.get().strip()
        if not name:
            return messagebox.showwarning("Color", "Escribe el nombre del color.")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", hexv):
            return messagebox.showwarning("Color", "El hex debe tener el formato #RRGGBB (ej. #1b1b1b).")
        self.colors.append({"nombre": name, "hex": hexv.lower()})
        self.v_cname.set("")
        self.refresh_colors()

    def remove_color(self):
        sel = self.lb_colors.curselection()
        if sel:
            del self.colors[sel[0]]
            self.refresh_colors()

    # ---- presets de color (se guardan en admin_presets.json)
    def refresh_presets(self, select=None):
        self.cb_preset["values"] = [f"{p['nombre']}  ({p['hex']})" for p in self.presets]
        if select is not None and 0 <= select < len(self.presets):
            self.cb_preset.current(select)
        else:
            self.v_preset.set("")
        self.on_preset_select()

    def _sel_preset(self):
        i = self.cb_preset.current()
        return i if 0 <= i < len(self.presets) else None

    def on_preset_select(self, _event=None):
        i = self._sel_preset()
        self.sw_preset.config(bg=self.presets[i]["hex"] if i is not None else self._sw_default)

    def use_preset(self):
        """Agrega el preset elegido a los colores del producto."""
        i = self._sel_preset()
        if i is None:
            return messagebox.showinfo("Presets", "Elige un preset de la lista.")
        c = self.presets[i]
        if any(x["hex"].lower() == c["hex"] and x["nombre"].lower() == c["nombre"].lower() for x in self.colors):
            return messagebox.showinfo("Presets", f"'{c['nombre']}' ya está en este producto.")
        self.colors.append({"nombre": c["nombre"], "hex": c["hex"]})
        self.refresh_colors()

    def save_preset(self):
        """Guarda como preset lo escrito en Nombre/Hex; si el nombre está vacío, el color seleccionado de la lista."""
        name, hexv = self.v_cname.get().strip(), self.v_chex.get().strip()
        if not name:
            sel = self.lb_colors.curselection()
            if not sel:
                return messagebox.showwarning(
                    "Preset", "Escribe el nombre y el hex del color, o selecciona uno de la lista de colores.")
            name, hexv = self.colors[sel[0]]["nombre"], self.colors[sel[0]]["hex"]
        if not HEX_RE.fullmatch(hexv):
            return messagebox.showwarning("Preset", "El hex debe tener el formato #RRGGBB (ej. #ffc83d).")
        hexv = hexv.lower()
        for idx, p in enumerate(self.presets):
            if p["nombre"].lower() == name.lower():      # mismo nombre: se actualiza el color
                p["nombre"], p["hex"] = name, hexv
                break
        else:
            self.presets.append({"nombre": name, "hex": hexv})
            idx = len(self.presets) - 1
        try:
            save_presets(self.presets)
        except OSError as e:
            return messagebox.showerror("Error al guardar presets", str(e))
        self.refresh_presets(select=idx)

    def delete_preset(self):
        i = self._sel_preset()
        if i is None:
            return messagebox.showinfo("Presets", "Elige un preset de la lista.")
        if not messagebox.askyesno("Presets", f"¿Borrar el preset '{self.presets[i]['nombre']}'?"):
            return
        del self.presets[i]
        try:
            save_presets(self.presets)
        except OSError as e:
            return messagebox.showerror("Error al guardar presets", str(e))
        self.refresh_presets()

    # ---- botón "Ver cambios" (gris durante la espera de GitHub Pages)
    def _stop_view_timer(self):
        if self._view_timer is not None:
            self.after_cancel(self._view_timer)
            self._view_timer = None

    def reset_view_button(self):
        self._stop_view_timer()
        self.btn_view.config(text="Ver cambios", state="disabled")

    def start_view_countdown(self, remaining=PAGES_WAIT):
        self._stop_view_timer()
        if remaining <= 0:
            self.btn_view.config(text="Ver cambios", state="normal")
            return
        self.btn_view.config(text=f"Ver cambios ({remaining}s)", state="disabled")
        self._view_timer = self.after(1000, lambda: self.start_view_countdown(remaining - 1))

    def open_site(self):
        webbrowser.open(SITE_URL)

    # ---- git push automático (en segundo plano para no congelar la ventana)
    def git_push(self, message):
        self.lbl_git.config(text="⏳ Subiendo a GitHub…", foreground="#666")
        self.reset_view_button()
        result = {}

        def work():
            result["r"] = git_publish(message)

        def poll():
            if "r" not in result:
                return self.after(300, poll)
            ok, detail = result["r"]
            if ok:
                self.lbl_git.config(text="✔ Subido a GitHub", foreground="#2e7d32")
                self.start_view_countdown()
            else:
                self.lbl_git.config(text="✘ No se pudo subir", foreground="#c62828")
                messagebox.showwarning(
                    "Git push",
                    "El producto se guardó, pero no se pudo subir a GitHub:\n\n" + detail[:800])

        threading.Thread(target=work, daemon=True).start()
        self.after(300, poll)

    # ---- guardar / eliminar
    def save(self):
        try:
            nombre = self.v_nombre.get().strip()
            if not nombre:
                raise ValueError("El campo 'Nombre' es obligatorio.")
            precio = parse_number(self.v_precio.get(), "Precio")
            medidas = {}
            for key, var, label in (("alto", self.v_alto, "Alto"), ("ancho", self.v_ancho, "Ancho"),
                                    ("profundidad", self.v_prof, "Profundidad")):
                n = parse_number(var.get(), label, required=False)
                if n is not None:
                    medidas[key] = n
            editing = self.current is not None
            old = self.products[self.current] if editing else {}

            # Imágenes
            if not self.images:
                raise ValueError("Debes agregar al menos una imagen.")
            new_entries = [e for e in self.images if e["src"] is not None]
            if new_entries and not self.v_imgname.get().strip():
                raise ValueError("Escribe el 'Nombre base' para las imágenes nuevas.")
            base = slugify(Path(self.v_imgname.get().strip()).stem)
            used = {Path(e["path"]).name for e in self.images if e["src"] is None}

            def unique_name(ext):
                n = 1
                while True:
                    name = f"{base}{'' if n == 1 else f'-{n}'}{ext}"
                    if name not in used and not (IMG_DIR / name).exists():
                        used.add(name)
                        return name
                    n += 1

            IMG_DIR.mkdir(exist_ok=True)
            final = []
            for e in self.images:
                if e["src"] is None:
                    final.append(e["path"])
                else:
                    name = unique_name(e["src"].suffix.lower())
                    shutil.copy2(e["src"], IMG_DIR / name)
                    final.append(f"images/{name}")
            imagen = final[0]

            new_id = old.get("id") or (max([p.get("id", 0) for p in self.products] + [0]) + 1)
            product = {
                "id": new_id,
                "nombre": nombre,
                "descripcion": self.t_desc.get("1.0", "end").strip(),
                "precio": precio,
                "imagen": imagen,
                "imagenes": final,
                "colores": self.colors,
                "medidas": medidas,
                "stock": self.v_stock.get(),
                "categoria": self.v_categoria.get().strip(),
            }
            if not product["categoria"]:
                del product["categoria"]

            if editing:
                self.products[self.current] = product
                idx = self.current
            else:
                self.products.append(product)
                idx = len(self.products) - 1
            save_products(self.products)
        except ValueError as e:
            return messagebox.showwarning("Revisa los datos", str(e))
        except OSError as e:
            return messagebox.showerror("Error al guardar", str(e))

        self.git_push(f"{'Actualizar' if editing else 'Agregar'} producto: {nombre}")
        self.refresh_list(select=idx)
        self.load_into_form(idx)
        messagebox.showinfo("Listo", f"Producto '{nombre}' guardado en data/products.json")

    def delete_product(self):
        sel = self.listbox.curselection()
        if not sel:
            return messagebox.showinfo("Eliminar", "Selecciona un producto de la lista.")
        p = self.products[sel[0]]
        if not messagebox.askyesno("Eliminar", f"¿Eliminar '{p.get('nombre')}'?"):
            return
        imgs = product_images(p)
        del self.products[sel[0]]
        in_use = {x for q in self.products for x in product_images(q)}
        orphans = [x for x in imgs if x not in in_use and (ROOT / x).exists()]
        if orphans and messagebox.askyesno("Imágenes", f"¿Borrar también {len(orphans)} archivo(s) de imagen?"):
            for x in orphans:
                (ROOT / x).unlink()
        save_products(self.products)
        self.refresh_list()
        self.new_product()


if __name__ == "__main__":
    App().mainloop()
