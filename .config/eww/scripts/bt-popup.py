#!/usr/bin/env python3
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gio, Gtk, Pango  # noqa: E402

LayerShell = None
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell as LayerShell
except (ValueError, ImportError):
    LayerShell = None

ICON_BT = "\uf293"
ICON_CHECK = "\uf00c"
ICON_TRASH = "\uf1f8"

CSS = """
@define-color bg #0b0b0e;
@define-color red #8E1523;
@define-color flare #C1121F;
@define-color text #e6e6e6;
@define-color muted #F2F2F2;

window.popup {
    background-color: alpha(@bg, 0.95);
    border: 1px solid @red;
    border-radius: 10px;
    box-shadow: 0 0 12px alpha(@red, 0.6);
    color: @text;
}
.title { font-weight: bold; font-size: 15px; color: @text; }
.muted { color: @muted; font-size: 12px; }
.nf { font-family: "CaskaydiaCove Nerd Font"; font-size: 18px; }
.nf-small { font-family: "CaskaydiaCove Nerd Font"; font-size: 15px; color: @muted; }
.ok { color: @muted; }
.net-row { border-radius: 6px; padding: 8px 10px; margin: 2px 0; }
.net-active { background-color: alpha(@red, 0.3); }
listboxrow, row {
    background-color: transparent;
    background-image: none;
    border: none;
    box-shadow: none;
    padding: 0;
}
listboxrow:hover .net-row { background-color: alpha(@red, 0.55); }
button.flat {
    background-image: none;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    box-shadow: none;
    color: @muted;
    min-height: 0;
    padding: 4px 8px;
}
button.flat:hover { color: @flare; border-color: alpha(@red, 0.35); }
switch {
    background-color: #1a1a1d;
    border: 1px solid @red;
}
switch:checked { background-color: @red; }
switch slider { background-color: @text; }
listbox, list { background-color: transparent; }
scrollbar slider { background-color: alpha(@red, 0.6); border-radius: 4px; }
"""


def bt(*args, timeout=10):
    try:
        r = subprocess.run(["bluetoothctl", *args], capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "tiempo agotado"


def parse_devices(text):
    devs = []
    for line in text.splitlines():
        parts = line.strip().split(" ", 2)
        if len(parts) == 3 and parts[0] == "Device":
            devs.append({"mac": parts[1], "name": parts[2]})
    return devs


def load_state():
    _, show, _ = bt("show", timeout=5)
    if "Powered: yes" not in show:
        return {"radio": False, "paired": [], "avail": []}

    _, out, _ = bt("devices", "Paired", timeout=5)
    if not out.strip():
        _, out, _ = bt("paired-devices", timeout=5)
    paired = parse_devices(out)
    for d in paired:
        _, info, _ = bt("info", d["mac"], timeout=5)
        d["connected"] = "Connected: yes" in info

    mac_paired = {d["mac"] for d in paired}
    _, all_out, _ = bt("devices", timeout=5)
    avail = [d for d in parse_devices(all_out) if d["mac"] not in mac_paired]
    return {"radio": True, "paired": paired, "avail": avail}


def pair_device(mac):
    # NoInputNoOutput sirve para dispositivos sin PIN (audífonos, ratones, etc.)
    script = (
        "agent NoInputNoOutput\n"
        "default-agent\n"
        f"pair {mac}\n"
        f"trust {mac}\n"
        f"connect {mac}\n"
        "quit\n"
    )
    try:
        r = subprocess.run(["bluetoothctl"], input=script, capture_output=True,
                           text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False
    return "Pairing successful" in r.stdout or "Pairing successful" in r.stderr


def apply_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS.encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


class BtWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(title="Bluetooth")
        self.set_application(app)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(340, 420)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.get_style_context().add_class("popup")

        self.radio = False
        self.paired = []
        self.avail = []
        self.pending = {}
        self.message = None
        self.armed = False

        if LayerShell and LayerShell.is_supported():
            LayerShell.init_for_window(self)
            LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
            LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
            LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
            LayerShell.set_margin(self, LayerShell.Edge.TOP, 42)
            LayerShell.set_margin(self, LayerShell.Edge.RIGHT, 130)
            LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.ON_DEMAND)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_border_width(12)
        self.add(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label(label="Bluetooth")
        title.get_style_context().add_class("title")
        title.set_xalign(0)
        title.set_hexpand(True)
        self.switch = Gtk.Switch()
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch_handler = self.switch.connect("state-set", self.on_switch)
        header.pack_start(title, True, True, 0)
        header.pack_start(self.switch, False, False, 0)
        root.pack_start(header, False, False, 0)

        self.status = Gtk.Label()
        self.status.get_style_context().add_class("muted")
        self.status.set_xalign(0)
        root.pack_start(self.status, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(280)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.connect("row-activated", self.on_row_activated)
        scroll.add(self.listbox)
        root.pack_start(scroll, True, True, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.scan_btn = Gtk.Button(label="Buscar dispositivos")
        self.scan_btn.get_style_context().add_class("flat")
        self.scan_btn.connect("clicked", self.on_scan)
        footer.pack_start(self.scan_btn, True, True, 0)
        root.pack_start(footer, False, False, 0)

        self.connect("key-press-event", self.on_key)
        self.connect("notify::is-active", self.on_active)
        self.refresh()

    # ----- ventana -----

    def on_key(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def on_active(self, *_):
        if self.is_active():
            self.armed = True
        elif self.armed:
            self.destroy()

    # ----- datos -----

    def refresh(self):
        self.status.set_label("Cargando...")

        def worker():
            data = load_state()
            GLib.idle_add(self.populate, data)

        threading.Thread(target=worker, daemon=True).start()

    def populate(self, data):
        self.radio = data["radio"]
        self.paired = data["paired"]
        self.avail = data["avail"]

        self.switch.handler_block(self.switch_handler)
        self.switch.set_active(self.radio)
        self.switch.handler_unblock(self.switch_handler)

        self.rebuild()
        return False

    def rebuild(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        if self.message:
            self.status.set_label(self.message)
        elif not self.radio:
            self.status.set_label("Bluetooth desactivado")
        elif not self.paired and not self.avail:
            self.status.set_label("Sin dispositivos. Pulsa Buscar.")
        elif self.paired:
            self.status.set_label("Dispositivos emparejados")
        else:
            self.status.set_label("Dispositivos disponibles")

        for d in self.paired:
            self.listbox.add(self.build_row(d, "paired"))
        for d in self.avail:
            self.listbox.add(self.build_row(d, "avail"))
        self.listbox.show_all()
        return False

    def build_row(self, dev, section):
        mac = dev["mac"]
        row = Gtk.ListBoxRow()
        row.set_name(f"{section}|{mac}")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.get_style_context().add_class("net-row")
        if dev.get("connected"):
            box.get_style_context().add_class("net-active")

        icon = Gtk.Label(label=ICON_BT)
        icon.get_style_context().add_class("nf")
        name = Gtk.Label(label=dev["name"])
        name.set_xalign(0)
        name.set_hexpand(True)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        box.pack_start(icon, False, False, 0)
        box.pack_start(name, True, True, 0)

        if mac in self.pending:
            state = Gtk.Label(label=self.pending[mac])
        elif dev.get("connected"):
            check = Gtk.Label(label=ICON_CHECK)
            check.get_style_context().add_class("nf")
            check.get_style_context().add_class("ok")
            box.pack_start(check, False, False, 0)
            state = Gtk.Label(label="Conectado")
        elif section == "paired":
            state = Gtk.Label(label="Desconectado")
        else:
            state = Gtk.Label(label="Nuevo")
        state.get_style_context().add_class("muted")
        box.pack_start(state, False, False, 0)

        if section == "paired":
            forget = Gtk.Button(label=ICON_TRASH)
            forget.get_style_context().add_class("flat")
            forget.get_style_context().add_class("nf")
            forget.set_tooltip_text("Olvidar dispositivo")
            forget.connect("clicked", lambda *_, m=mac: self.forget(m))
            box.pack_start(forget, False, False, 0)

        row.add(box)
        return row

    # ----- acciones -----

    def on_row_activated(self, _listbox, row):
        section, mac = row.get_name().split("|", 1)
        if mac in self.pending:
            return
        self.message = None

        if section == "avail":
            self.pending[mac] = "Emparejando..."
            action = "pair"
        else:
            dev = next((d for d in self.paired if d["mac"] == mac), None)
            if dev and dev.get("connected"):
                self.pending[mac] = "Desconectando..."
                action = "disconnect"
            else:
                self.pending[mac] = "Conectando..."
                action = "connect"

        GLib.idle_add(self.rebuild)
        self.run(mac, action)

    def run(self, mac, action):
        def worker():
            if action == "pair":
                ok = pair_device(mac)
                self.message = None if ok else "No se pudo emparejar (si pide PIN, usa bluetoothctl)"
            elif action == "connect":
                code, _, _ = bt("connect", mac, timeout=25)
                self.message = None if code == 0 else "No se pudo conectar"
            else:
                code, _, _ = bt("disconnect", mac, timeout=15)
                self.message = None if code == 0 else "No se pudo desconectar"
            self.pending.pop(mac, None)
            GLib.idle_add(self.refresh)

        threading.Thread(target=worker, daemon=True).start()

    def forget(self, mac):
        def worker():
            code, _, _ = bt("remove", mac, timeout=10)
            self.message = "Dispositivo olvidado" if code == 0 else "No se pudo olvidar"
            GLib.idle_add(self.refresh)

        threading.Thread(target=worker, daemon=True).start()

    def on_switch(self, _sw, state):
        def worker():
            bt("power", "on" if state else "off", timeout=10)
            GLib.idle_add(self.refresh)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def on_scan(self, *_):
        self.scan_btn.set_sensitive(False)
        self.status.set_label("Buscando dispositivos...")

        def worker():
            bt("--timeout", "8", "scan", "on", timeout=15)
            GLib.idle_add(self.scan_done)

        threading.Thread(target=worker, daemon=True).start()

    def scan_done(self):
        self.scan_btn.set_sensitive(True)
        self.refresh()
        return False


class BtApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.local.btpopup",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.win = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        apply_css()

    def do_activate(self):
        # Un segundo clic en el módulo cierra el popup, como en el de Wi-Fi
        if self.win is not None:
            self.win.destroy()
            self.win = None
            return
        self.win = BtWindow(self)
        self.win.connect("destroy", self.on_destroy)
        self.win.show_all()
        self.win.present()

    def on_destroy(self, *_):
        self.win = None


if __name__ == "__main__":
    BtApp().run(sys.argv)
