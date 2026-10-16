"""Shared dark ttk theme for the three explorer windows."""

from tkinter import font, ttk

from PIL import Image, ImageDraw, ImageTk


SURFACE = "#152232"
FIELD = "#1d2d40"
BORDER = "#354b61"
TEXT = "#dce8f2"
MUTED = "#95abc0"
ACCENT = "#6ad7c5"


def configure_theme(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=SURFACE)
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", "#304b62")
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
    style.configure(".", background=SURFACE, foreground=TEXT,
                    fieldbackground=FIELD, bordercolor=BORDER,
                    lightcolor=SURFACE, darkcolor=SURFACE,
                    troughcolor="#0e1926", selectbackground="#304b62",
                    selectforeground=TEXT)
    style.configure("Muted.TLabel", foreground=MUTED)
    root._cusps_heading_font = font.nametofont("TkDefaultFont", root=root).copy()
    root._cusps_heading_font.configure(weight="bold")
    style.configure("Heading.TLabel", foreground=ACCENT, font=root._cusps_heading_font)
    style.configure("TButton", padding=(10, 6), borderwidth=1, relief="solid",
                    focuscolor=ACCENT, focusthickness=1)
    style.map("TButton", background=[("disabled", SURFACE), ("pressed", "#243c50"),
                                      ("active", "#203449")],
              bordercolor=[("disabled", BORDER), ("focus", ACCENT), ("active", ACCENT)],
              foreground=[("disabled", MUTED)])
    style.configure("Accent.TButton", background="#24453f", foreground="#a7f0e2", bordercolor="#3d766b")
    style.map("Accent.TButton", background=[("disabled", SURFACE), ("pressed", "#315f55"),
                                             ("active", "#2a5149")])
    for name in ("TEntry", "TCombobox"):
        style.configure(name, padding=4, borderwidth=1, relief="flat", arrowsize=12,
                        insertcolor=TEXT, arrowcolor=MUTED)
        style.map(name, fieldbackground=[("disabled", SURFACE), ("readonly", FIELD)],
                  background=[("active", FIELD), ("readonly", FIELD)],
                  foreground=[("disabled", MUTED), ("readonly", TEXT)],
                  bordercolor=[("disabled", BORDER), ("focus", ACCENT), ("active", ACCENT)],
                  lightcolor=[("focus", ACCENT)], darkcolor=[("focus", ACCENT)])

    # Image indicators avoid the native white square/X and stay identical on
    # hover. Only the outer border changes; selected and keyboard focus remain
    # distinguishable without changing the control's background or its label.
    images = []
    for selected, disabled in ((False, False), (True, False), (False, True), (True, True)):
        image = Image.new("RGBA", (60, 60))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((5, 5, 55, 55), radius=10, fill=FIELD,
                               outline=MUTED if disabled else (ACCENT if selected else BORDER), width=4)
        if selected:
            draw.line(((17, 30), (26, 39), (44, 20)), fill=MUTED if disabled else ACCENT,
                      width=6, joint="curve")
        images.append(ImageTk.PhotoImage(image.resize((20, 20), Image.Resampling.LANCZOS), master=root))
    root._cusps_theme_images = images  # Tcl does not retain Python image owners.
    style.element_create("Cusps.Check.indicator", "image", images[0],
                         (("disabled", "selected"), images[3]),
                         ("disabled", images[2]), ("selected", images[1]))
    style.element_create("Cusps.Check.border", "from", "clam", "border")
    style.layout("TCheckbutton", [("Cusps.Check.border", {"sticky": "nswe", "border": 1, "children": [
        ("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Cusps.Check.indicator", {"side": "left"}),
            ("Checkbutton.label", {"side": "left", "sticky": "w"})]})]})])
    style.configure("TCheckbutton", padding=(4, 3), borderwidth=1, relief="solid",
                    bordercolor=SURFACE)
    style.map("TCheckbutton", background=[("disabled", SURFACE), ("active", SURFACE)],
              foreground=[("disabled", MUTED), ("active", TEXT)],
              bordercolor=[("disabled", SURFACE), ("focus", ACCENT), ("active", ACCENT)])
    style.configure("TLabelframe", borderwidth=1, relief="solid")
    style.configure("TLabelframe.Label", foreground=MUTED, padding=(4, 0))
    style.configure("Horizontal.TScale", background="#506d88", bordercolor="#506d88",
                    lightcolor="#506d88", darkcolor="#506d88", troughcolor="#0e1926",
                    sliderlength=18, borderwidth=0)
    style.map("Horizontal.TScale", background=[("active", ACCENT)], bordercolor=[("active", ACCENT)])
    style.configure("Horizontal.TProgressbar", background=ACCENT, bordercolor=SURFACE,
                    lightcolor=ACCENT, darkcolor=ACCENT, troughcolor="#0e1926",
                    borderwidth=0, thickness=4)
