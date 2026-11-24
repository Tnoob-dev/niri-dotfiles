#!/usr/bin/env python3
import re
import subprocess
import sys
import time
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gio, Gtk, Pango  # noqa: E402

# gtk-layer-shell se importa después de GTK 3 (opcional)
LayerShell = None
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell as LayerShell
except (ValueError, ImportError):
    LayerShell = None

ICON_WIFI = "\uf1eb"
ICON_LOCK = "\uf023"
ICON_CHECK = "\uf00c"
ICON_TRASH = "\uf1f8"

CSS = """
@define-color bg #0D0D0D;
@define-color red #F20505;
@define-color flare #F20519;
@define-color text #F2F2F2;
@define-color muted #6b6b72;

window.popup {
    background-color: alpha(@bg, 0.95);
    border: 1px solid @red;
    border-radius: 10px;
    box-shadow: 0 0 12px alpha(@red, 0.6);
    color: @text;
}
.title { font-weight: bold; font-size: 15px; color: @text; }
.muted { color: #F2F2F2; font-size: 12px; }
.nf { font-family: "CaskaydiaCove Nerd Font"; font-size: 18px; }
.nf-small { font-family: "CaskaydiaCove Nerd Font"; font-size: 15px; color: #F2F2F2; }
.ok { color: #F2F2F2; }
.net-row { border-radius: 6px; padding: 8px 10px; margin: 2px 0; }
.net-row:hover { background-color: alpha(@red, 0.2); }
.net-active { background-color: alpha(@red, 0.3); }
button.flat {
    background-image: none;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    box-shadow: none;
    color: #F2F2F2;
    min-height: 0;
    padding: 4px 8px;
}
button.flat:hover {
    color: @flare;
    border-color: alpha(@red, 0.35);
}
button.suggested-action {
    background-image: none;
    background-color: @red;
    border: 1px solid @red;
    color: @text;
}
button.suggested-action:hover { background-color: @flare; }
entry {
    background-color: #1a1a1d;
    border: 1px solid alpha(@red, 0.5);
    border-radius: 6px;
    color: @text;
}
entry:focus { border-color: @red; }
switch {
    background-color: #1a1a1d;
    border: 1px solid @red;
}
switch:checked { background-color: @red; }
switch slider { background-color: @text; }
listbox, list { background-color: transparent; }
scrollbar slider {
    background-color: alpha(@red, 0.6);
    border-radius: 4px;
}
/* Quitar el fondo gris de los contenedores internos de GTK */
listbox, list, row, listboxrow, scrolledwindow, viewport, scrolledwindow > viewport {
    background-color: transparent;
    background-image: none;
}

/* Hover más intenso */
row:hover, listboxrow:hover, .net-row:hover {
    background-color: alpha(@red, 0.55);
}

/* Redes activas y VPN conectada */
.net-active {
    background-color: alpha(@red, 0.75);
}

/* La fila no pinta nada */
listboxrow, row {
    background-color: transparent;
    background-image: none;
    border: none;
    box-shadow: none;
    padding: 0;
}

/* La caja interna siempre tiene la forma redondeada */
.net-row {
    border-radius: 6px;
}

/* Hover sobre la fila: pinta la caja redondeada */
listboxrow:hover .net-row {
    background-color: alpha(@red, 0.55);
}

/* Red activa o VPN conectada */
.net-active {
    background-color: alpha(@red, 0.75);
}
"""


def apply_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS.encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def css(widget, *names):
    for name in names:
        widget.get_style_context().add_class(name)
    return widget


def nmcli(*args):
    r = subprocess.run(["nmcli", *args], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def split_terse(line):
    return [p.replace("\\:", ":") for p in re.split(r"(?<!\\):", line)]


def get_radio():
    _, out, _ = nmcli("radio", "wifi")
    return out.strip() == "enabled"


def get_saved():
    _, out, _ = nmcli("-t", "-f", "NAME,TYPE", "connection", "show")
    saved = set()
    for line in out.splitlines():
        name, _, ctype = line.rpartition(":")
        if ctype == "802-11-wireless":
            saved.add(name.replace("\\:", ":"))
    return saved


def get_networks(retries=3):
    nets = {}
    for _ in range(retries):
        _, out, _ = nmcli(
            "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
            "device", "wifi", "list", "--rescan", "auto",
        )
        nets = {}
        for line in out.splitlines():
            parts = split_terse(line)
            if len(parts) < 4:
                continue
            in_use, ssid, signal, security = parts[0], parts[1], parts[2], parts[3]
            if not ssid:
                continue
            net = {
                "ssid": ssid,
                "signal": int(signal) if signal.isdigit() else 0,
                "secure": security not in ("", "--"),
                "active": in_use == "*",
            }
            prev = nets.get(ssid)
            if prev is None or net["active"] or net["signal"] > prev["signal"]:
                nets[ssid] = net
        if nets:
            break
        time.sleep(1)
    return sorted(nets.values(), key=lambda n: (not n["active"], -n["signal"]))

VPN_TYPES = ("vpn", "wireguard")
ICON_VPN = "\uf132"


def get_vpns():
    _, out, _ = nmcli("-t", "-f", "NAME,TYPE", "connection", "show")
    _, active_out, _ = nmcli("-t", "-f", "NAME", "connection", "show", "--active")
    active = {line.replace("\\:", ":") for line in active_out.splitlines()}
    vpns = []
    for line in out.splitlines():
        name, _, ctype = line.rpartition(":")
        if ctype in VPN_TYPES:
            name = name.replace("\\:", ":")
            vpns.append({"name": name, "active": name in active})
    return sorted(vpns, key=lambda v: v["name"].lower())


def set_vpn(name, up):
    return nmcli("connection", "up" if up else "down", "id", name)

def connect(ssid, saved, password=None):
    if password:
        return nmcli("device", "wifi", "connect", ssid, "password", password)
    if ssid in saved:
        return nmcli("connection", "up", "id", ssid)
    return nmcli("device", "wifi", "connect", ssid)


class WifiWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(title="Wi-Fi")
        self.set_application(app)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(340, 440)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        css(self, "popup")

        self.saved = set()
        self.nets = {}
        self.message = None
        self.pending_ssid = None
        self.armed = False
        self.vpn_pending = {}
        self.vpn_labels = {}

        if LayerShell and LayerShell.is_supported():
            LayerShell.init_for_window(self)
            LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
            LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
            LayerShell.set_anchor(self, LayerShell.Edge.RIGHT, True)
            LayerShell.set_margin(self, LayerShell.Edge.TOP, 42)
            LayerShell.set_margin(self, LayerShell.Edge.RIGHT, 10)
            LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.ON_DEMAND)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_border_width(12)
        self.add(root)

        # Cabecera: título e interruptor
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = css(Gtk.Label(label="Wi-Fi"), "title")
        title.set_xalign(0)
        title.set_hexpand(True)
        self.switch = Gtk.Switch()
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch_handler = self.switch.connect("state-set", self.on_switch)
        header.pack_start(title, True, True, 0)
        header.pack_start(self.switch, False, False, 0)
        root.pack_start(header, False, False, 0)

        self.stack = Gtk.Stack()
        root.pack_start(self.stack, True, True, 0)

        # Página 1: lista de redes
        list_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.status = css(Gtk.Label(), "muted")
        self.status.set_xalign(0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(260)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.connect("row-activated", self.on_row_activated)
        scroll.add(self.listbox)
        list_page.pack_start(self.status, False, False, 0)
        list_page.pack_start(scroll, True, True, 0)

        self.vpn_title = css(Gtk.Label(label="VPN"), "muted")
        self.vpn_title.set_xalign(0)
        self.vpn_list = Gtk.ListBox()
        self.vpn_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.vpn_list.connect("row-activated", self.on_vpn_activated)
        list_page.pack_start(self.vpn_title, False, False, 0)
        list_page.pack_start(self.vpn_list, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.disconnect_btn = css(Gtk.Button(label="Desconectar"), "flat")
        self.disconnect_btn.connect("clicked", self.on_disconnect)
        editor_btn = css(Gtk.Button(label="Editor de conexiones"), "flat")
        editor_btn.set_hexpand(True)
        editor_btn.set_halign(Gtk.Align.END)
        editor_btn.connect("clicked", self.on_editor)
        footer.pack_start(self.disconnect_btn, False, False, 0)
        footer.pack_start(editor_btn, True, True, 0)
        list_page.pack_start(footer, False, False, 0)

        self.stack.add_named(list_page, "list")

        # Página 2: contraseña
        pass_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.pass_label = Gtk.Label()
        self.pass_label.set_xalign(0)
        self.pass_label.set_line_wrap(True)
        self.pass_entry = Gtk.Entry()
        self.pass_entry.set_visibility(False)
        self.pass_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.pass_entry.set_placeholder_text("Contraseña")
        self.pass_entry.connect("activate", self.on_password_submit)
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btns.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda *_: self.show_list())
        ok = css(Gtk.Button(label="Conectar"), "suggested-action")
        ok.connect("clicked", self.on_password_submit)
        btns.pack_start(cancel, False, False, 0)
        btns.pack_start(ok, False, False, 0)
        pass_page.pack_start(self.pass_label, False, False, 0)
        pass_page.pack_start(self.pass_entry, False, False, 0)
        pass_page.pack_start(btns, False, False, 0)
        self.stack.add_named(pass_page, "pass")

        self.connect("key-press-event", self.on_key)
        self.connect("notify::is-active", self.on_active)

        self.refresh()

    # ----- ventana -----

    def on_key(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            if self.stack.get_visible_child_name() == "pass":
                self.show_list()
            else:
                self.destroy()
            return True
        return False

    def on_active(self, *_):
        if self.is_active():
            self.armed = True
        elif self.armed:
            self.destroy()

    def show_list(self):
        self.stack.set_visible_child_name("list")

    # ----- datos -----

    def refresh(self):
        self.status.set_label("Buscando redes...")

        def worker():
            radio = get_radio()
            saved = get_saved()
            nets = get_networks() if radio else []
            vpns = get_vpns()
            GLib.idle_add(self.populate, radio, saved, nets, vpns)

        threading.Thread(target=worker, daemon=True).start()

    def populate(self, radio, saved, nets, vpns):
        self.saved = saved
        self.nets = {n["ssid"]: n for n in nets}
        self.vpns = vpns

        self.switch.handler_block(self.switch_handler)
        self.switch.set_active(radio)
        self.switch.handler_unblock(self.switch_handler)

        for child in self.listbox.get_children():
            self.listbox.remove(child)
        for child in self.vpn_list.get_children():
            self.vpn_list.remove(child)

        if self.message:
            self.status.set_label(self.message)
        elif not radio:
            self.status.set_label("Wi-Fi desactivado")
        elif not nets:
            self.status.set_label("No se encontraron redes")
        else:
            self.status.set_label("Redes disponibles")

        for net in nets:
            self.listbox.add(self.build_row(net))
        
        self.vpn_labels = {}
        for vpn in vpns:
            self.vpn_list.add(self.build_vpn_row(vpn))

        self.listbox.show_all()
        self.vpn_list.show_all()
        self.vpn_title.set_visible(bool(vpns))
        self.vpn_list.set_visible(bool(vpns))
        self.disconnect_btn.set_sensitive(any(n["active"] for n in nets))
        return False

    def build_row(self, net):
        row = Gtk.ListBoxRow()
        row.set_name(net["ssid"])

        box = css(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10), "net-row")
        if net["active"]:
            box.get_style_context().add_class("net-active")

        icon = css(Gtk.Label(label=ICON_WIFI), "nf")
        name = Gtk.Label(label=net["ssid"])
        name.set_xalign(0)
        name.set_hexpand(True)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        box.pack_start(icon, False, False, 0)
        box.pack_start(name, True, True, 0)

        if net["secure"]:
            box.pack_start(css(Gtk.Label(label=ICON_LOCK), "nf-small"), False, False, 0)

        if net["active"]:
            box.pack_start(css(Gtk.Label(label=ICON_CHECK), "nf", "ok"), False, False, 0)

        box.pack_start(css(Gtk.Label(label=f"{net['signal']}%"), "muted"), False, False, 0)

        if net["ssid"] in self.saved:
            forget = css(Gtk.Button(label=ICON_TRASH), "flat", "nf")
            forget.set_tooltip_text("Olvidar red")
            forget.connect("clicked", lambda *_, s=net["ssid"]: self.forget(s))
            box.pack_start(forget, False, False, 0)

        row.add(box)
        return row
    
    def build_vpn_row(self, vpn):
        row = Gtk.ListBoxRow()
        row.set_name(vpn["name"])

        box = css(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10), "net-row")
        if vpn["active"]:
            box.get_style_context().add_class("net-active")

        icon = css(Gtk.Label(label=ICON_VPN), "nf")
        name = Gtk.Label(label=vpn["name"])
        name.set_xalign(0)
        name.set_hexpand(True)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        box.pack_start(icon, False, False, 0)
        box.pack_start(name, True, True, 0)

        if vpn["active"]:
            box.pack_start(css(Gtk.Label(label=ICON_CHECK), "nf", "ok"), False, False, 0)

        text = self.vpn_pending.get(vpn["name"])
        if text is None:
            text = "Conectada" if vpn["active"] else "Desconectada"
        state_label = css(Gtk.Label(label=text), "muted")
        self.vpn_labels[vpn["name"]] = state_label
        box.pack_start(state_label, False, False, 0)

        row.add(box)
        return row

    def on_vpn_activated(self, _listbox, row):
        name = row.get_name()
        if name in self.vpn_pending:
            return  # ya hay una operación en curso para esta VPN
        active = any(v["name"] == name and v["active"] for v in self.vpns)
        self.message = None

        text = "Desconectando..." if active else "Conectando..."
        self.vpn_pending[name] = text
        label = self.vpn_labels.get(name)
        if label:
            label.set_label(text)

        def worker():
            code, _, err = set_vpn(name, not active)
            self.vpn_pending.pop(name, None)
            if code != 0:
                self.message = "Error VPN: " + (err.strip() or "no se pudo cambiar")
            GLib.idle_add(self.refresh)

        threading.Thread(target=worker, daemon=True).start()

    # ----- acciones -----

    def on_row_activated(self, _listbox, row):
        net = self.nets.get(row.get_name())
        if not net or net["active"]:
            return
        self.message = None
        if net["secure"] and net["ssid"] not in self.saved:
            self.ask_password(net["ssid"])
        else:
            self.do_connect(net["ssid"], None)

    def ask_password(self, ssid):
        self.pending_ssid = ssid
        self.pass_label.set_label(f"Introduce la contraseña de «{ssid}»")
        self.pass_entry.set_text("")
        self.stack.set_visible_child_name("pass")
        self.pass_entry.grab_focus()

    def on_password_submit(self, *_):
        pwd = self.pass_entry.get_text()
        if not pwd:
            return
        self.show_list()
        self.do_connect(self.pending_ssid, pwd)

    def do_connect(self, ssid, password):
        self.status.set_label(f"Conectando a {ssid}...")
        saved = self.saved

        def worker():
            code, _, err = connect(ssid, saved, password)
            GLib.idle_add(self.on_connect_done, ssid, code, err)

        threading.Thread(target=worker, daemon=True).start()

    def on_connect_done(self, ssid, code, err):
        if code == 0:
            self.message = f"Conectado a {ssid}"
        else:
            self.message = "Error: " + (err.strip() or "no se pudo conectar")
        self.refresh()
        return False

    def forget(self, ssid):
        def worker():
            code, _, err = nmcli("connection", "delete", "id", ssid)
            self.message = "Red olvidada" if code == 0 else (
                err.strip() or "No se pudo olvidar la red"
            )
            GLib.idle_add(self.refresh)

        threading.Thread(target=worker, daemon=True).start()

    def on_switch(self, _sw, state):
        def worker():
            nmcli("radio", "wifi", "on" if state else "off")
            if state:
                time.sleep(2)  # dar tiempo a que el dispositivo se active
            GLib.idle_add(self.refresh)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def on_disconnect(self, *_):
        def worker():
            _, out, _ = nmcli("-t", "-f", "DEVICE,TYPE", "device")
            for line in out.splitlines():
                dev, _, typ = line.rpartition(":")
                if typ == "wifi":
                    nmcli("device", "disconnect", dev)
            GLib.idle_add(self.refresh)

        threading.Thread(target=worker, daemon=True).start()

    def on_editor(self, *_):
        try:
            subprocess.Popen(["nm-connection-editor"])
            self.destroy()
        except FileNotFoundError:
            self.status.set_label("Instala nm-connection-editor")


class WifiApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.local.wifipopup",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.win = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        apply_css()

    def do_activate(self):
        # Un segundo clic en el módulo cierra el popup, como un toggle
        if self.win is not None:
            self.win.destroy()
            self.win = None
            return
        self.win = WifiWindow(self)
        self.win.connect("destroy", self.on_destroy)
        self.win.show_all()
        self.win.present()

    def on_destroy(self, *_):
        self.win = None


if __name__ == "__main__":
    WifiApp().run(sys.argv)