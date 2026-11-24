"""Tkinter desktop interface for the preliminary Beam Designer."""

from __future__ import annotations

import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any

from analysis import analyze


ROOT = Path(__file__).resolve().parent
INK = "#172a35"
MUTED = "#62727b"
LINE = "#dce4e7"
PAPER = "#ffffff"
CANVAS = "#f3f6f7"
NAVY = "#163747"
TEAL = "#087c78"
GOLD = "#d78a2c"
BLUE = "#5879a7"
RED = "#b94137"
GREEN = "#18764d"


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


class ScrollableFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, *, background: str = CANVAS) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, background=background, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, background=background)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._sync_scroll)
        self.canvas.bind("<Configure>", self._sync_width)
        self.canvas.bind_all("<MouseWheel>", self._wheel, add="+")

    def _sync_scroll(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window, width=event.width)

    def _wheel(self, event: tk.Event) -> None:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None and widget is not self:
            widget = getattr(widget, "master", None)
        if widget is self:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")


class LoadRow:
    def __init__(self, app: "BeamDesigner", kind: str, values: dict[str, Any] | None = None) -> None:
        self.app = app
        self.kind = kind
        self.values = values or {}
        self.frame = tk.Frame(app.point_rows if kind == "point" else app.uniform_rows, bg="#fbfcfc", highlightbackground=LINE, highlightthickness=1)
        self.entries: dict[str, ttk.Entry] = {}
        self.direction = tk.StringVar(value=self.values.get("direction", "Down"))
        self.frame.grid_columnconfigure(0, weight=1)
        labels = [("Magnitude", "magnitude", self.values.get("magnitude", "")), ("Position", "position", self.values.get("position", ""))] if kind == "point" else [
            ("Intensity", "magnitude", self.values.get("magnitude", "")),
            ("Start", "start", self.values.get("start", "")),
            ("End", "end", self.values.get("end", "")),
        ]
        for col, (label, key, value) in enumerate(labels):
            field = tk.Frame(self.frame, bg="#fbfcfc")
            field.grid(row=0, column=col, sticky="ew", padx=(8, 2), pady=7)
            tk.Label(field, text=label, bg="#fbfcfc", fg=MUTED, font=("Helvetica", 9, "bold")).pack(anchor="w")
            entry = ttk.Entry(field, width=10)
            entry.insert(0, str(value))
            entry.pack(fill="x", pady=(3, 0))
            self.entries[key] = entry
        direction_col = len(labels)
        field = tk.Frame(self.frame, bg="#fbfcfc")
        field.grid(row=0, column=direction_col, sticky="ew", padx=2, pady=7)
        tk.Label(field, text="Direction", bg="#fbfcfc", fg=MUTED, font=("Helvetica", 9, "bold")).pack(anchor="w")
        ttk.Combobox(field, textvariable=self.direction, values=("Down", "Up"), state="readonly", width=7).pack(fill="x", pady=(3, 0))
        button = ttk.Button(self.frame, text="×", width=3, command=self.remove)
        button.grid(row=0, column=direction_col + 1, padx=(2, 7), pady=(20, 7))

    def remove(self) -> None:
        self.frame.destroy()
        self.app.load_rows.remove(self)

    def values_for_analysis(self, span_ft: float) -> dict[str, float | str]:
        def number(key: str) -> float:
            raw = self.entries[key].get().strip()
            try:
                value = float(raw)
            except ValueError as exc:
                raise ValueError("Enter a number for every load magnitude and position.") from exc
            if not math.isfinite(value):
                raise ValueError("Load values must be finite numbers.")
            return value

        magnitude = number("magnitude")
        if magnitude < 0:
            raise ValueError("Enter non-negative load magnitudes, then choose the load direction.")
        sign = 1.0 if self.direction.get() == "Down" else -1.0
        if self.kind == "point":
            position = number("position")
            if not 0 <= position <= span_ft:
                raise ValueError(f"Point-load positions must be between 0 and {fmt(span_ft, 3)} ft.")
            return {"kind": "point", "p": sign * magnitude, "x": position * 12, "magnitude": magnitude, "position": position, "direction": self.direction.get()}
        start, end = number("start"), number("end")
        if start < 0 or end > span_ft or end <= start:
            raise ValueError(f"Each uniform load must satisfy 0 ≤ start < end ≤ {fmt(span_ft, 3)} ft.")
        return {"kind": "uniform", "q": sign * magnitude / 12, "a": start * 12, "b": end * 12, "magnitude": magnitude, "start": start, "end": end, "direction": self.direction.get()}


class Chart(tk.Canvas):
    def __init__(self, master: tk.Misc, title: str, units: str, color: str, app: "BeamDesigner", key: str) -> None:
        super().__init__(master, height=175, background=PAPER, highlightthickness=0)
        self.title, self.units, self.color, self.app, self.key = title, units, color, app, key
        self.bind("<Configure>", self.redraw)

    def redraw(self, _event: tk.Event | None = None) -> None:
        self.delete("all")
        width, height = max(self.winfo_width(), 300), max(self.winfo_height(), 150)
        data = self.app.result
        if not data:
            self.create_text(width / 2, height / 2, text="Analyze a beam to view this diagram", fill="#96a4a8", font=("Helvetica", 10))
            return
        if self.key == "capacity" and not data["strength"]["checked"]:
            self.create_text(width / 2, height / 2, text="Compact-section screen not met; no ASD capacity reported", fill="#92701f", font=("Helvetica", 10), width=width - 30)
            return
        series = data["diagrams"][self.key]
        margin = (45, 14, 15, 30)
        left, top, right, bottom = margin[0], margin[1], width - margin[2], height - margin[3]
        xs = [point[0] for point in series]
        ys = [point[1] for point in series]
        threshold = None
        if self.key == "capacity":
            threshold = data["strength"]["allowable_kip_ft"]
            ys.append(threshold)
        low, high = min([0.0, *ys]), max([0.0, *ys])
        if abs(high - low) < 1e-10:
            low, high = -1.0, 1.0
        padding = (high - low) * 0.12
        low -= padding
        high += padding
        xmax = max(xs) or 1.0
        mapx = lambda x: left + x / xmax * (right - left)
        if self.key == "deflection":
            mapy = lambda y: top + (y - low) / (high - low) * (bottom - top)
        else:
            mapy = lambda y: bottom - (y - low) / (high - low) * (bottom - top)
        baseline = mapy(0)
        self.create_line(left, top, right, top, fill="#edf1f2")
        self.create_line(left, bottom, right, bottom, fill="#edf1f2")
        self.create_line(left, baseline, right, baseline, fill="#cbd5d8")
        if threshold is not None:
            y = mapy(threshold)
            self.create_line(left, y, right, y, fill=RED, dash=(5, 4), width=2)
            self.create_text(right - 2, max(top + 8, y - 8), text=f"allowable {fmt(threshold)}", anchor="e", fill=RED, font=("Helvetica", 8))
        coords = [coord for x, value in series for coord in (mapx(x), mapy(value))]
        if len(coords) >= 4:
            self.create_line(*coords, fill=self.color, width=2, smooth=False)
        peak = max(series, key=lambda item: abs(item[1]))
        px, py = mapx(peak[0]), mapy(peak[1])
        self.create_oval(px - 4, py - 4, px + 4, py + 4, fill=PAPER, outline=self.color, width=2)
        self.create_text(left, 9, anchor="w", text=f"Peak {fmt(abs(peak[1]))} {self.units}", fill=MUTED, font=("Helvetica", 8))
        self.create_text(left, height - 9, anchor="w", text="0 ft", fill=MUTED, font=("Helvetica", 8))
        self.create_text(right, height - 9, anchor="e", text=f"{fmt(data['span_in'] / 12, 1)} ft", fill=MUTED, font=("Helvetica", 8))


class BeamDesigner:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Beam Designer · Preliminary Analysis")
        self.root.geometry("1440x940")
        self.root.minsize(1100, 720)
        self.root.configure(background=CANVAS)
        self.sections: list[dict[str, Any]] = []
        self.material: dict[str, Any] = {"grade": "A992", "Fy": 50.0, "E": 29000.0}
        self.catalog_source = "AISC Shapes Database v16.0 · U.S. customary units"
        self.load_rows: list[LoadRow] = []
        self.result: dict[str, Any] | None = None
        self._configure_style()
        self._build()
        self._load_data()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=CANVAS)
        style.configure("Card.TFrame", background=PAPER)
        style.configure("TLabel", background=CANVAS, foreground=INK, font=("Helvetica", 10))
        style.configure("Muted.TLabel", foreground=MUTED, font=("Helvetica", 9))
        style.configure("Title.TLabel", foreground=NAVY, background=CANVAS, font=("Helvetica", 25, "bold"))
        style.configure("Heading.TLabel", foreground=NAVY, background=PAPER, font=("Helvetica", 12, "bold"))
        style.configure("Section.TLabel", foreground=NAVY, background=CANVAS, font=("Helvetica", 11, "bold"))
        style.configure("TButton", padding=(9, 6), font=("Helvetica", 9, "bold"))
        style.configure("Primary.TButton", background=TEAL, foreground="white", padding=(12, 9), font=("Helvetica", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#05615e")])
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=6)

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=CANVAS)
        header.pack(fill="x", padx=24, pady=(18, 10))
        brand = tk.Frame(header, bg=NAVY, width=42, height=42)
        brand.pack(side="left", padx=(0, 12))
        brand.pack_propagate(False)
        tk.Label(brand, text="BD", bg=NAVY, fg="white", font=("Helvetica", 14, "bold")).pack(expand=True)
        labels = tk.Frame(header, bg=CANVAS)
        labels.pack(side="left")
        tk.Label(labels, text="BEAM DESIGNER", bg=CANVAS, fg=INK, font=("Helvetica", 11, "bold")).pack(anchor="w")
        tk.Label(labels, text="Preliminary single-span analysis", bg=CANVAS, fg=MUTED, font=("Helvetica", 9)).pack(anchor="w")
        tk.Label(header, text="AISC W-SHAPES · v16.0", bg="#f9fbfb", fg="#41616c", font=("Helvetica", 9, "bold"), padx=11, pady=7, relief="solid", bd=1).pack(side="right")

        intro = tk.Frame(self.root, bg=CANVAS)
        intro.pack(fill="x", padx=25, pady=(5, 12))
        tk.Label(intro, text="Understand your beam.", bg=CANVAS, fg=NAVY, font=("Helvetica", 25, "bold")).pack(anchor="w")
        tk.Label(intro, text="Set the span, supports, section, and service-level loads. Review reactions, diagrams, and preliminary checks.", bg=CANVAS, fg=MUTED, font=("Helvetica", 10)).pack(anchor="w", pady=(4, 0))
        tk.Label(self.root, text="EDUCATIONAL, PRELIMINARY ANALYSIS ONLY. Not a complete structural design or construction approval. Continuous bracing is assumed; shear strength, excluded local limit states, bearing, connections, vibration, and load combinations are not checked.", anchor="w", justify="left", wraplength=1350, bg="#fffdf7", fg="#63583e", padx=13, pady=10, relief="solid", bd=1).pack(fill="x", padx=25, pady=(0, 12))

        panes = ttk.Panedwindow(self.root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self.setup_scroll = ScrollableFrame(panes)
        self.results_scroll = ScrollableFrame(panes)
        panes.add(self.setup_scroll, weight=0)
        panes.add(self.results_scroll, weight=1)
        panes.paneconfigure(self.setup_scroll, minsize=340, width=385)
        panes.paneconfigure(self.results_scroll, minsize=600)
        self._build_setup(self.setup_scroll.inner)
        self._build_results(self.results_scroll.inner)

    def _card(self, master: tk.Misc, *, pad: int = 16) -> tk.Frame:
        card = tk.Frame(master, bg=PAPER, highlightbackground=LINE, highlightthickness=1)
        card._content_pad = pad  # type: ignore[attr-defined]
        return card

    def _field(self, master: tk.Misc, label: str, variable: tk.StringVar | None = None, values: tuple[str, ...] | None = None) -> ttk.Widget:
        frame = tk.Frame(master, bg=PAPER)
        tk.Label(frame, text=label, bg=PAPER, fg="#50636c", font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 4))
        if values:
            widget = ttk.Combobox(frame, textvariable=variable, values=values, state="readonly")
        else:
            widget = ttk.Entry(frame, textvariable=variable)
        widget.pack(fill="x")
        return frame

    def _build_setup(self, parent: tk.Misc) -> None:
        card = self._card(parent)
        card.pack(fill="x", padx=(0, 8), pady=(0, 8))
        inner = tk.Frame(card, bg=PAPER, padx=15, pady=15)
        inner.pack(fill="x")
        tk.Label(inner, text="BEAM SETUP", bg=PAPER, fg=NAVY, font=("Helvetica", 13, "bold")).pack(anchor="w")
        tk.Label(inner, text="Define one span and its service-level loads.", bg=PAPER, fg=MUTED, font=("Helvetica", 9)).pack(anchor="w", pady=(3, 14))

        self.support_var = tk.StringVar(value="Simply supported")
        grid = tk.Frame(inner, bg=PAPER)
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1, uniform="fields")
        self._field(grid, "Support condition", self.support_var, ("Simply supported", "Cantilever")).grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 10))
        self.span_var = tk.StringVar(value="20")
        self._field(grid, "Span · ft", self.span_var).grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(0, 10))
        tk.Label(inner, text="Steel W-shape", bg=PAPER, fg="#50636c", font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 4))
        self.section_var = tk.StringVar()
        self.section_box = ttk.Combobox(inner, textvariable=self.section_var, state="disabled")
        self.section_box.pack(fill="x", pady=(0, 7))
        tk.Label(inner, text="A992 steel · Fy = 50 ksi · E = 29,000 ksi", bg=PAPER, fg=MUTED, font=("Helvetica", 9)).pack(anchor="w")

        self._divider(inner)
        row_title = tk.Frame(inner, bg=PAPER)
        row_title.pack(fill="x", pady=(0, 7))
        tk.Label(row_title, text="APPLIED LOADS", bg=PAPER, fg=NAVY, font=("Helvetica", 10, "bold")).pack(side="left")
        tk.Label(row_title, text="DOWNWARD +", bg=PAPER, fg=GOLD, font=("Helvetica", 8, "bold")).pack(side="right")
        self.point_rows = tk.Frame(inner, bg=PAPER)
        self.point_rows.pack(fill="x")
        self.uniform_rows = tk.Frame(inner, bg=PAPER)
        self.uniform_rows.pack(fill="x", pady=(7, 0))
        self.load_rows = []
        buttons = tk.Frame(inner, bg=PAPER)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="＋ Point load", command=lambda: self.add_load("point")).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="＋ Uniform load", command=lambda: self.add_load("uniform")).pack(side="left")
        tk.Label(inner, text="Loads are service-level. Include member self-weight if applicable; the app does not add it or create load combinations.", bg=PAPER, fg=MUTED, wraplength=325, justify="left", font=("Helvetica", 8)).pack(anchor="w", pady=(9, 0))

        self._divider(inner)
        tk.Label(inner, text="DEFLECTION LIMIT", bg=PAPER, fg=NAVY, font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 8))
        self.limit_var = tk.StringVar(value="L/360")
        limit_grid = tk.Frame(inner, bg=PAPER)
        limit_grid.pack(fill="x")
        limit_grid.columnconfigure(0, weight=1)
        limit_grid.columnconfigure(1, weight=1)
        self._field(limit_grid, "Allowable ratio", self.limit_var, ("L/240", "L/360", "L/480", "Custom")).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.custom_limit_var = tk.StringVar(value="0.667")
        self.custom_field = self._field(limit_grid, "Custom limit · in", self.custom_limit_var)
        self.custom_field.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.limit_var.trace_add("write", lambda *_: self._toggle_custom())
        tk.Label(inner, text="L/360 is configurable and is not a universal requirement.", bg=PAPER, fg=MUTED, font=("Helvetica", 8)).pack(anchor="w", pady=(7, 0))

        self.error_label = tk.Label(inner, text="", bg=PAPER, fg=RED, wraplength=325, justify="left", font=("Helvetica", 9))
        self.error_label.pack(fill="x", pady=(10, 0))
        ttk.Button(inner, text="Analyze beam   →", style="Primary.TButton", command=self.run_analysis).pack(fill="x", pady=(10, 5))
        ttk.Button(inner, text="Restore example beam", command=self.restore_example).pack(fill="x")

    def _divider(self, parent: tk.Misc) -> None:
        tk.Frame(parent, bg="#edf1f2", height=1).pack(fill="x", pady=14)

    def _toggle_custom(self) -> None:
        if hasattr(self, "custom_field"):
            if self.limit_var.get() == "Custom":
                self.custom_field.grid()
            else:
                self.custom_field.grid_remove()

    def add_load(self, kind: str, values: dict[str, Any] | None = None) -> None:
        row = LoadRow(self, kind, values)
        row.frame.pack(fill="x", pady=3)
        self.load_rows.append(row)

    def _build_results(self, parent: tk.Misc) -> None:
        top = tk.Frame(parent, bg=CANVAS)
        top.pack(fill="x", padx=(8, 0), pady=(0, 8))
        tk.Label(top, text="ANALYSIS RESULTS", bg=CANVAS, fg=TEAL, font=("Helvetica", 9, "bold")).pack(anchor="w")
        tk.Label(top, text="Beam overview", bg=CANVAS, fg=NAVY, font=("Helvetica", 17, "bold")).pack(anchor="w", pady=(2, 0))
        self.status_label = tk.Label(top, text="READY", bg="#f2faf6", fg=GREEN, padx=9, pady=4, font=("Helvetica", 8, "bold"))
        self.status_label.pack(anchor="ne", pady=(-30, 0))

        self.summary_card = self._card(parent)
        self.summary_card.pack(fill="x", padx=(8, 0), pady=(0, 8))
        self.summary_values: dict[str, tk.Label] = {}
        summary = tk.Frame(self.summary_card, bg="#f8fafb")
        summary.pack(fill="x", padx=1, pady=1)
        summary_items = [("SECTION", "section"), ("AREA", "area"), ("Ix", "ix"), ("Sx", "sx"), ("Zx", "zx"), ("STEEL", "steel")]
        for col, (label, key) in enumerate(summary_items):
            item = tk.Frame(summary, bg="#f8fafb", padx=9, pady=9)
            item.grid(row=0, column=col, sticky="nsew")
            summary.columnconfigure(col, weight=1, uniform="summary")
            tk.Label(item, text=label, bg="#f8fafb", fg="#73848a", font=("Helvetica", 7, "bold")).pack(anchor="w")
            value = tk.Label(item, text="—", bg="#f8fafb", fg="#213b47", font=("Helvetica", 9, "bold"), anchor="w")
            value.pack(anchor="w", pady=(4, 0))
            self.summary_values[key] = value
        tk.Label(self.summary_card, text=self.catalog_source, bg=PAPER, fg=MUTED, font=("Helvetica", 8)).pack(anchor="w", padx=10, pady=(3, 8))

        self.metric_card = self._card(parent)
        self.metric_card.pack(fill="x", padx=(8, 0), pady=(0, 8))
        self.metric_values: dict[str, tuple[tk.Label, tk.Label]] = {}
        metrics = tk.Frame(self.metric_card, bg=PAPER)
        metrics.pack(fill="x", padx=10, pady=10)
        for col, (key, title) in enumerate((("ra", "Left reaction"), ("rb", "Right reaction"), ("moment", "Maximum moment"), ("deflection", "Maximum deflection"))):
            metrics.columnconfigure(col, weight=1, uniform="metrics")
            item = tk.Frame(metrics, bg=PAPER, highlightbackground="#e5ebed", highlightthickness=1, padx=10, pady=9)
            item.grid(row=0, column=col, sticky="nsew", padx=3)
            tk.Label(item, text=title.upper(), bg=PAPER, fg="#6a7b82", font=("Helvetica", 7, "bold")).pack(anchor="w")
            value = tk.Label(item, text="—", bg=PAPER, fg=NAVY, font=("Helvetica", 15, "bold"), anchor="w")
            value.pack(anchor="w", pady=(5, 2))
            detail = tk.Label(item, text="", bg=PAPER, fg=MUTED, font=("Helvetica", 8), anchor="w", justify="left")
            detail.pack(anchor="w")
            self.metric_values[key] = (value, detail)

        checks = tk.Frame(parent, bg=CANVAS)
        checks.pack(fill="x", padx=(8, 0), pady=(0, 8))
        checks.columnconfigure((0, 1), weight=1, uniform="check")
        self.strength_check = self._check_card(checks, "FLEXURAL STRENGTH · ASD")
        self.strength_check.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.deflection_check = self._check_card(checks, "SERVICE DEFLECTION")
        self.deflection_check.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.check_values: dict[str, tuple[tk.Label, tk.Label]] = {"strength": self.strength_check, "deflection": self.deflection_check}
        tk.Label(parent, text="A992 steel, E = 29,000 ksi. Strength follows the limited ASD screen in the spec and assumes continuous lateral bracing. The estimated web slenderness uses (d − 2tf)/tw because clear web depth is not in the selected catalog fields. Lateral-torsional buckling is not checked.", bg=CANVAS, fg=MUTED, wraplength=950, justify="left", font=("Helvetica", 8)).pack(fill="x", padx=(10, 0), pady=(0, 12))

        beam_card = self._card(parent)
        beam_card.pack(fill="x", padx=(8, 0), pady=(0, 8))
        self._card_heading(beam_card, "Beam & applied loads", "Reactions and load positions")
        self.beam_canvas = tk.Canvas(beam_card, height=170, bg=PAPER, highlightthickness=0)
        self.beam_canvas.pack(fill="x", padx=10, pady=(0, 10))
        self.beam_canvas.bind("<Configure>", self._redraw_all)

        charts_card = self._card(parent)
        charts_card.pack(fill="x", padx=(8, 0), pady=(0, 8))
        self._card_heading(charts_card, "Analysis diagrams", "Positive sagging moment · downward deflection positive")
        charts = tk.Frame(charts_card, bg=PAPER)
        charts.pack(fill="x", padx=8, pady=(0, 10))
        charts.columnconfigure((0, 1), weight=1, uniform="charts")
        self.charts: dict[str, Chart] = {}
        for index, (key, title, units, color) in enumerate((
            ("shear", "Shear force", "kip", TEAL),
            ("moment", "Bending moment", "kip-ft", GOLD),
            ("deflection", "Deflection", "in", BLUE),
            ("capacity", "Moment vs allowable", "kip-ft", GOLD),
        )):
            cell = tk.Frame(charts, bg=PAPER, highlightbackground="#e5ebed", highlightthickness=1)
            cell.grid(row=index // 2, column=index % 2, sticky="nsew", padx=3, pady=3)
            tk.Label(cell, text=f"{title}   ·   {units}", bg=PAPER, fg=NAVY, font=("Helvetica", 9, "bold")).pack(anchor="w", padx=9, pady=(8, 0))
            chart = Chart(cell, title, units, color, self, key)
            chart.pack(fill="x")
            self.charts[key] = chart
        tk.Label(parent, text="Service-level loading only. Include the applicable loads yourself; this app does not generate combinations or certify code compliance.", bg=CANVAS, fg=MUTED, font=("Helvetica", 8)).pack(fill="x", padx=(10, 0), pady=(2, 14))

    def _check_card(self, master: tk.Misc, title: str) -> tuple[tk.Label, tk.Label]:
        card = tk.Frame(master, bg=PAPER, highlightbackground=LINE, highlightthickness=1, padx=12, pady=11)
        tk.Label(card, text=title, bg=PAPER, fg=NAVY, font=("Helvetica", 9, "bold")).pack(anchor="w")
        detail = tk.Label(card, text="Awaiting analysis", bg=PAPER, fg=MUTED, wraplength=300, justify="left", font=("Helvetica", 8))
        detail.pack(anchor="w", pady=(5, 8))
        status = tk.Label(card, text="—", bg=PAPER, fg=GREEN, font=("Helvetica", 10, "bold"))
        status.pack(anchor="e")
        return status, detail

    def _card_heading(self, card: tk.Frame, title: str, subtitle: str) -> None:
        head = tk.Frame(card, bg=PAPER)
        head.pack(fill="x", padx=12, pady=(11, 7))
        tk.Label(head, text=title, bg=PAPER, fg=NAVY, font=("Helvetica", 11, "bold")).pack(anchor="w")
        tk.Label(head, text=subtitle, bg=PAPER, fg=MUTED, font=("Helvetica", 8)).pack(anchor="w", pady=(2, 0))

    def _load_data(self) -> None:
        try:
            catalog = json.loads((ROOT / "01_data" / "w_shapes_v16.json").read_text(encoding="utf-8"))
            materials = json.loads((ROOT / "01_data" / "materials.json").read_text(encoding="utf-8"))
            rows = catalog.get("shapes", [])
            required = ("area", "depth", "flangeWidth", "webThickness", "flangeThickness", "Ix", "Sx", "Zx")
            if not rows or any(not shape.get("label", "").startswith("W") or any(not isinstance(shape.get(k), (int, float)) or shape[k] <= 0 for k in required) for shape in rows):
                raise ValueError("The section catalog contains missing or invalid required properties.")
            self.sections = rows
            self.catalog_source = catalog.get("source", self.catalog_source)
            self.material = materials["materials"][0]
            self.section_box.configure(values=[shape["label"].replace("X", "x") for shape in rows], state="readonly")
            labels = [shape["label"].replace("X", "x") for shape in rows]
            self.section_var.set("W12x26" if "W12x26" in labels else labels[0])
            self.summary_card.winfo_children()[-1].configure(text=f"Section properties: {self.catalog_source} · U.S. customary units")
            self.status_label.configure(text=f"{len(rows)} W-SHAPES LOADED", bg="#f2faf6", fg=GREEN)
            self.restore_example()
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self.status_label.configure(text="DATA UNAVAILABLE", bg="#fff4f3", fg=RED)
            self.error_label.configure(text=f"Could not load the AISC section or material data: {exc}")

    def restore_example(self) -> None:
        self.support_var.set("Simply supported")
        self.span_var.set("20")
        self.limit_var.set("L/360")
        self.custom_limit_var.set("0.667")
        for row in self.load_rows[:]:
            row.remove()
        self.add_load("uniform", {"magnitude": "1", "start": "0", "end": "20", "direction": "Down"})
        if self.sections:
            self.section_var.set("W12x26")
            self.error_label.configure(text="")
            self.run_analysis()

    def run_analysis(self) -> None:
        try:
            if not self.sections:
                raise ValueError("A valid AISC section catalog is required before analysis.")
            span_ft = float(self.span_var.get().strip())
            if not math.isfinite(span_ft) or not 0 < span_ft <= 500:
                raise ValueError("Enter a span greater than 0 and no more than 500 ft.")
            section = next((item for item in self.sections if item["label"].replace("X", "x") == self.section_var.get()), None)
            if section is None:
                raise ValueError("Select a valid W-shape from the section catalog.")
            points, uniforms = [], []
            for row in self.load_rows:
                parsed = row.values_for_analysis(span_ft)
                if parsed["kind"] == "point":
                    points.append({"p": parsed["p"], "x": parsed["x"]})
                else:
                    uniforms.append({"q": parsed["q"], "a": parsed["a"], "b": parsed["b"]})
            if not points and not uniforms:
                raise ValueError("Add at least one point or uniform load to analyze the beam.")
            if not any(abs(item["p"]) > 0 for item in points) and not any(abs(item["q"]) > 0 for item in uniforms):
                raise ValueError("At least one applied load must have a non-zero magnitude.")
            if self.limit_var.get() == "Custom":
                custom = float(self.custom_limit_var.get().strip())
                if not math.isfinite(custom) or custom <= 0:
                    raise ValueError("Enter a custom deflection limit greater than 0 in.")
                limit_ratio, custom_limit = None, custom
            else:
                limit_ratio, custom_limit = int(self.limit_var.get().split("/")[1]), None
            support = "cantilever" if self.support_var.get() == "Cantilever" else "simple"
            self.result = analyze(span_ft, support, section, points, uniforms, self.material["E"], self.material["Fy"], limit_ratio, custom_limit)
            self.error_label.configure(text="")
            self.status_label.configure(text="ANALYSIS COMPLETE", bg="#f2faf6", fg=GREEN)
            self._render_results(section, span_ft)
            self._redraw_all()
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            self.result = None
            self.status_label.configure(text="RESULTS STALE", bg="#fff4f3", fg=RED)
            self.error_label.configure(text=str(exc))
            self._clear_results()

    def _render_results(self, section: dict[str, Any], span_ft: float) -> None:
        assert self.result is not None
        r = self.result
        self.summary_values["section"].configure(text=section["label"].replace("X", "x"))
        self.summary_values["area"].configure(text=f"{fmt(section['area'], 1)} in²")
        self.summary_values["ix"].configure(text=f"{fmt(section['Ix'], 1)} in⁴")
        self.summary_values["sx"].configure(text=f"{fmt(section['Sx'], 1)} in³")
        self.summary_values["zx"].configure(text=f"{fmt(section['Zx'], 1)} in³")
        self.summary_values["steel"].configure(text=f"{self.material['grade']} · {fmt(self.material['Fy'], 0)} ksi")
        reaction = r["reaction"]
        self.metric_values["ra"][0].configure(text=f"{fmt(reaction['left'])} kip")
        self.metric_values["ra"][1].configure(text="Fixed vertical reaction · upward +" if r["support"] == "cantilever" else "Left support · upward +")
        self.metric_values["rb"][0].configure(text=f"{fmt(reaction['fixed_moment'] / 12)} kip-ft" if r["support"] == "cantilever" else f"{fmt(reaction['right'])} kip")
        self.metric_values["rb"][1].configure(text="Fixed reaction moment · CCW +" if r["support"] == "cantilever" else "Right support · upward +")
        mp, dp = r["moment_peak"], r["deflection_peak"]
        self.metric_values["moment"][0].configure(text=f"{fmt(abs(mp['value']) / 12)} kip-ft")
        self.metric_values["moment"][1].configure(text=f"Absolute peak at {fmt(mp['x'] / 12)} ft")
        self.metric_values["deflection"][0].configure(text=f"{fmt(abs(dp['value']), 3)} in")
        direction = "Downward" if dp["value"] >= 0 else "Upward"
        self.metric_values["deflection"][1].configure(text=f"{direction} at {fmt(dp['x'] / 12)} ft · limit {fmt(r['deflection_limit_in'], 3)} in")
        strength_status, strength_detail = self.check_values["strength"]
        strength = r["strength"]
        if not strength["checked"]:
            strength_status.configure(text="NOT CHECKED", fg="#92701f")
            strength_detail.configure(text=f"Elastic stress {fmt(strength['stress_ksi'])} ksi. The compact-section screen was not met; no ASD capacity is reported.")
        else:
            passed = strength["pass"]
            strength_status.configure(text=f"{'PASS' if passed else 'FAIL'} · {fmt(strength['utilization'] * 100, 1)}%", fg=GREEN if passed else RED)
            strength_detail.configure(text=f"Demand {fmt(strength['demand_kip_ft'])} / allowable {fmt(strength['allowable_kip_ft'])} kip-ft · AISC 360-22 ASD · fully braced assumed")
        def_status, def_detail = self.check_values["deflection"]
        def_status.configure(text="PASS" if r["deflection_pass"] else "FAIL", fg=GREEN if r["deflection_pass"] else RED)
        def_detail.configure(text=f"Maximum service deflection {fmt(abs(dp['value']), 3)} in · limit {fmt(r['deflection_limit_in'], 3)} in · L = {fmt(span_ft)} ft")

    def _clear_results(self) -> None:
        for value, detail in self.metric_values.values():
            value.configure(text="—")
            detail.configure(text="")
        for status, detail in self.check_values.values():
            status.configure(text="—", fg=MUTED)
            detail.configure(text="Awaiting valid analysis")
        for value in self.summary_values.values():
            value.configure(text="—")
        self._redraw_all()

    def _redraw_all(self, _event: tk.Event | None = None) -> None:
        self._draw_beam()
        for chart in getattr(self, "charts", {}).values():
            chart.redraw()

    def _draw_beam(self) -> None:
        if not hasattr(self, "beam_canvas"):
            return
        canvas = self.beam_canvas
        canvas.delete("all")
        width, height = max(canvas.winfo_width(), 500), max(canvas.winfo_height(), 150)
        if not self.result:
            canvas.create_text(width / 2, height / 2, text="Run an analysis to view the beam.", fill="#96a4a8", font=("Helvetica", 10))
            return
        x0, x1, y = 55, width - 45, 82
        span = self.result["span_in"]
        scale_x = lambda x: x0 + x / span * (x1 - x0)
        canvas.create_line(x0, y, x1, y, fill=NAVY, width=5, capstyle="round")
        if self.result["support"] == "cantilever":
            canvas.create_rectangle(x0 - 14, y - 38, x0 - 2, y + 38, fill="#eaf0f1", outline="#71878f")
            canvas.create_text(x0, y + 52, text="FIXED", fill=MUTED, font=("Helvetica", 8, "bold"))
        else:
            for x in (x0, x1):
                canvas.create_polygon(x, y + 3, x - 13, y + 25, x + 13, y + 25, fill=PAPER, outline="#385a68", width=2)
                canvas.create_line(x - 18, y + 28, x + 18, y + 28, fill="#87979d")
            canvas.create_oval(x1 - 9, y + 27, x1 - 3, y + 33, fill=PAPER, outline="#385a68")
            canvas.create_oval(x1 + 3, y + 27, x1 + 9, y + 33, fill=PAPER, outline="#385a68")
        canvas.create_text(x0, 13, text="0 ft", fill=MUTED, font=("Helvetica", 8))
        canvas.create_text(x1, 13, text=f"{fmt(span / 12)} ft", fill=MUTED, font=("Helvetica", 8))

        for index, row in enumerate(self.load_rows):
            try:
                v = row.values_for_analysis(span / 12)
            except ValueError:
                continue
            if v["kind"] == "point":
                x = scale_x(float(v["x"]))
                down = v["direction"] == "Down"
                y1 = 27 + (index % 2) * 8 if down else 135
                y2 = y - 5 if down else y + 5
                canvas.create_line(x, y1, x, y2, fill=GOLD, width=2, arrow=tk.LAST)
                canvas.create_text(x, y1 - 8 if down else y1 + 12, text=f"{fmt(float(v['magnitude']))} kip", fill="#8f6020", font=("Helvetica", 8, "bold"))
            else:
                a, b = scale_x(float(v["a"])), scale_x(float(v["b"]))
                down = v["direction"] == "Down"
                y1, y2 = (32 + (index % 2) * 5, y - 5) if down else (133, y + 5)
                canvas.create_line(a, y1, b, y1, fill=GOLD, width=1)
                for step in range(9):
                    x = a + (b - a) * step / 8
                    canvas.create_line(x, y1, x, y2, fill=GOLD, arrow=tk.LAST, width=1)
                canvas.create_text((a + b) / 2, y1 - 8 if down else y1 + 12, text=f"{fmt(float(v['magnitude']))} kip/ft", fill="#8f6020", font=("Helvetica", 8, "bold"))
        reaction = self.result["reaction"]
        if self.result["support"] == "simple":
            for x, value in ((x0, reaction["left"]), (x1, reaction["right"])):
                start, end = (y + 43, y + 8) if value >= 0 else (y + 8, y + 43)
                canvas.create_line(x, start, x, end, fill=TEAL, width=2, arrow=tk.LAST)
                canvas.create_text(x, y + 53, text=f"{fmt(value)} kip", fill=TEAL, font=("Helvetica", 8))
        else:
            value = reaction["left"]
            start, end = (y + 44, y + 8) if value >= 0 else (y + 8, y + 44)
            canvas.create_line(x0 + 34, start, x0 + 34, end, fill=TEAL, width=2, arrow=tk.LAST)
            arrow = "↑" if value >= 0 else "↓"
            canvas.create_text(x0 + 40, y + 54, anchor="w", text=f"{fmt(value)} kip {arrow}", fill=TEAL, font=("Helvetica", 8))


def main() -> None:
    root = tk.Tk()
    BeamDesigner(root)
    root.mainloop()


if __name__ == "__main__":
    main()
