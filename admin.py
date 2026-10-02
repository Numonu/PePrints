#!/usr/bin/env python3
"""
Administrador de productos (interfaz simple con Tkinter, sin dependencias externas).

Uso:   python admin.py      (desde la raíz del proyecto)

- Lee y escribe data/products.json
- Cada producto puede tener varias imágenes (incluye GIF). La primera es la principal
  y es la que se ve en la miniatura.
- Al guardar, las imágenes nuevas se copian a images/ usando el "Nombre base" que escribas
  (llavero-gato.png, llavero-gato-2.gif, llavero-gato-3.jpg…). La extensión se conserva.
"""
import json
import os
import re
import shutil
import subprocess
import threading
import unicodedata
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "data" / "products.json"
IMG_DIR = ROOT / "images"
IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")

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


# ------------------------------------------------------------------ interfaz
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Administrador de productos")
        self.geometry("980x740")
        self.minsize(860, 680)

        self.products = load_products()
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
        self.lb_images = tk.Listbox(imf, height=6, width=52, exportselection=False)
        self.lb_images.pack(side="left")
        ib = ttk.Frame(imf)
        ib.pack(side="left", padx=10, anchor="n")
        for text, cmd in (("Agregar imágenes…", self.add_images), ("Quitar seleccionada", self.remove_image),
                          ("Subir", lambda: self.move_image(-1)), ("Bajar", lambda: self.move_image(1)),
                          ("Hacer principal ★", self.make_main)):
            ttk.Button(ib, text=text, command=cmd).pack(fill="x", pady=1)
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
        bar = ttk.Frame(right)
        bar.grid(row=r, column=0, columnspan=4, sticky="e", pady=16)
        self.lbl_mode = ttk.Label(bar, text="")
        self.lbl_mode.pack(side="left", padx=12)
        self.lbl_git = ttk.Label(bar, text="")
        self.lbl_git.pack(side="left", padx=12)
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

    # ---- git push automático (en segundo plano para no congelar la ventana)
    def git_push(self, message):
        self.lbl_git.config(text="⏳ Subiendo a GitHub…", foreground="#666")
        result = {}

        def work():
            result["r"] = git_publish(message)

        def poll():
            if "r" not in result:
                return self.after(300, poll)
            ok, detail = result["r"]
            if ok:
                self.lbl_git.config(text="✔ Subido a GitHub", foreground="#2e7d32")
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
