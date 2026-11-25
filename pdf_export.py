"""Create a dependency-free, vector PDF calculation sheet."""

from __future__ import annotations

import math
import textwrap
from pathlib import Path
from typing import Any


PAGE_W, PAGE_H = 612.0, 792.0
INK = (0.09, 0.16, 0.21)
MUTED = (0.39, 0.45, 0.48)
NAVY = (0.09, 0.22, 0.28)
TEAL = (0.03, 0.49, 0.47)
GOLD = (0.76, 0.43, 0.13)
BLUE = (0.28, 0.42, 0.60)
RED = (0.67, 0.20, 0.17)
GREEN = (0.09, 0.46, 0.30)
PALE = (0.95, 0.97, 0.98)
PALE_GOLD = (1.0, 0.98, 0.93)
WHITE = (1.0, 1.0, 1.0)


def _ascii(value: Any) -> str:
    text = str(value)
    for char, replacement in {
        "×": "x", "·": " | ", "–": "-", "—": "-", "−": "-",
        "²": "^2", "³": "^3", "⁴": "^4", "≤": "<=", "≥": ">=",
        "↑": "up", "↓": "down", "δ": "deflection", "φ": "phi",
        "ₓ": "x", "ₜ": "t", "ₛ": "s", "ₐ": "a",
    }.items():
        text = text.replace(char, replacement)
    return text.encode("ascii", "replace").decode("ascii")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _num(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


class Page:
    def __init__(self) -> None:
        self.ops: list[str] = []

    @staticmethod
    def _rgb(rgb: tuple[float, float, float]) -> str:
        return " ".join(f"{value:.3f}" for value in rgb)

    def text(self, x: float, y: float, value: Any, size: float = 9, *, bold: bool = False, color: tuple[float, float, float] = INK) -> None:
        font = "F2" if bold else "F1"
        text = _escape(_ascii(value))
        self.ops.append(f"{self._rgb(color)} rg BT /{font} {size:.2f} Tf {x:.2f} {y:.2f} Td ({text}) Tj ET")

    def line(self, x1: float, y1: float, x2: float, y2: float, *, color: tuple[float, float, float] = INK, width: float = 1, dash: bool = False) -> None:
        self.ops.append(f"{self._rgb(color)} RG {width:.2f} w {'[4 3] 0 d' if dash else '[] 0 d'} {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def rect(self, x: float, y: float, width: float, height: float, *, fill: tuple[float, float, float] | None = None, stroke: tuple[float, float, float] | None = None, line_width: float = 1) -> None:
        if fill is not None:
            self.ops.append(f"{self._rgb(fill)} rg {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f")
        if stroke is not None:
            self.ops.append(f"{self._rgb(stroke)} RG {line_width:.2f} w {x:.2f} {y:.2f} {width:.2f} {height:.2f} re S")

    def polygon(self, points: list[tuple[float, float]], *, fill: tuple[float, float, float] | None = None, stroke: tuple[float, float, float] | None = None, line_width: float = 1) -> None:
        if not points:
            return
        self.ops.append("q")
        if fill is not None:
            self.ops.append(f"{self._rgb(fill)} rg")
        if stroke is not None:
            self.ops.append(f"{self._rgb(stroke)} RG {line_width:.2f} w")
        self.ops.append(f"{points[0][0]:.2f} {points[0][1]:.2f} m")
        for x, y in points[1:]:
            self.ops.append(f"{x:.2f} {y:.2f} l")
        self.ops.append("h")
        self.ops.append("B" if fill is not None and stroke is not None else "f" if fill is not None else "S")
        self.ops.append("Q")

    def polyline(self, points: list[tuple[float, float]], *, color: tuple[float, float, float] = TEAL, width: float = 1.6) -> None:
        if len(points) < 2:
            return
        self.ops.append(f"{self._rgb(color)} RG {width:.2f} w 1 J 1 j")
        self.ops.append(f"{points[0][0]:.2f} {points[0][1]:.2f} m")
        for x, y in points[1:]:
            self.ops.append(f"{x:.2f} {y:.2f} l")
        self.ops.append("S")

    def arrow(self, x1: float, y1: float, x2: float, y2: float, *, color: tuple[float, float, float] = GOLD, width: float = 1.2) -> None:
        self.line(x1, y1, x2, y2, color=color, width=width)
        angle = math.atan2(y2 - y1, x2 - x1)
        head = 5.0
        left = (x2 - head * math.cos(angle - 0.48), y2 - head * math.sin(angle - 0.48))
        right = (x2 - head * math.cos(angle + 0.48), y2 - head * math.sin(angle + 0.48))
        self.polygon([(x2, y2), left, right], fill=color)

    def paragraph(self, x: float, y: float, value: str, *, width: int = 92, size: float = 8, leading: float = 11, color: tuple[float, float, float] = MUTED, bold: bool = False) -> float:
        lines = textwrap.wrap(_ascii(value), width=width, break_long_words=True, break_on_hyphens=False) or [""]
        for line in lines:
            self.text(x, y, line, size, bold=bold, color=color)
            y -= leading
        return y


def _header(page: Page, title: str, subtitle: str = "") -> None:
    page.text(44, 755, "BEAM DESIGNER  /  PRELIMINARY ANALYSIS", 8, bold=True, color=TEAL)
    page.text(44, 728, title, 20, bold=True, color=NAVY)
    if subtitle:
        page.text(44, 710, subtitle, 9, color=MUTED)
    page.line(44, 697, 568, 697, color=(0.86, 0.89, 0.90), width=0.8)


def _section_for_design(section: dict[str, Any]) -> list[str]:
    return [
        f"Designation: {section['label'].replace('X', 'x')}",
        f"Area: {_num(section['area'], 2)} in^2",
        f"d: {_num(section['depth'], 3)} in    bf: {_num(section['flangeWidth'], 3)} in",
        f"tw: {_num(section['webThickness'], 3)} in    tf: {_num(section['flangeThickness'], 3)} in",
        f"Ix: {_num(section['Ix'], 2)} in^4    Sx: {_num(section['Sx'], 2)} in^3    Zx: {_num(section['Zx'], 2)} in^3",
    ]


def _draw_input_pages(pages: list[Page], design: dict[str, Any], section: dict[str, Any], material: dict[str, Any], source: str) -> None:
    page = Page()
    pages.append(page)
    _header(page, "Calculation sheet", "Inputs and service-level load case")
    page.rect(44, 641, 524, 40, fill=PALE_GOLD, stroke=(0.91, 0.86, 0.75))
    page.text(54, 663, "PRELIMINARY EDUCATIONAL ANALYSIS ONLY", 9, bold=True, color=(0.40, 0.32, 0.18))
    page.text(54, 648, "Not a complete structural design, construction approval, or code certification.", 8, color=(0.40, 0.32, 0.18))

    page.text(44, 620, "DESIGN INPUTS", 10, bold=True, color=NAVY)
    support = "Cantilever" if design["support"] == "cantilever" else "Simply supported"
    limit = design["deflection_limit"]
    limit_text = f"L/{limit['denominator']}" if limit["mode"] == "ratio" else f"Custom: {_num(limit['inches'], 3)} in"
    left_rows = [
        ("Support condition", support),
        ("Span", f"{_num(design['span_ft'])} ft"),
        ("W-shape", section["label"].replace("X", "x")),
        ("Material", f"{material['grade']} steel  |  Fy = {_num(material['Fy'], 1)} ksi  |  E = {_num(material['E'], 0)} ksi"),
        ("Deflection limit", limit_text),
        ("Load case", "User-defined service-level loads; combinations are not generated"),
    ]
    y = 598
    for label, value in left_rows:
        page.text(48, y, label, 8, bold=True, color=MUTED)
        page.text(175, y, value, 8, color=INK)
        y -= 17

    y -= 5
    page.text(44, y, "SECTION PROPERTIES", 10, bold=True, color=NAVY)
    y -= 18
    for line in _section_for_design(section):
        page.text(48, y, line, 8, color=INK)
        y -= 15
    page.text(48, y - 1, f"Property source: {_ascii(source)}", 7, color=MUTED)
    y -= 26

    load_header = ("Load", "Magnitude", "Position / start", "End", "Direction")
    widths = (48, 160, 260, 365, 455)

    def draw_load_header(target: Page, row_y: float) -> None:
        target.rect(44, row_y - 5, 524, 19, fill=PALE)
        for x, label in zip(widths, load_header):
            target.text(x, row_y, label, 7, bold=True, color=NAVY)

    page.text(44, y, "APPLIED LOADS", 10, bold=True, color=NAVY)
    y -= 17
    draw_load_header(page, y)
    y -= 22
    loads = design.get("loads", [])
    if not loads:
        page.text(48, y, "No loads entered", 8, color=MUTED)
        y -= 17
    for index, load in enumerate(loads, start=1):
        if y < 55:
            page = Page()
            pages.append(page)
            _header(page, "Calculation sheet - continued", "Applied load schedule")
            y = 666
            draw_load_header(page, y)
            y -= 22
        if load["type"] == "point":
            label = f"Point {index}"
            magnitude = f"{_num(load['magnitude'])} kip"
            start = f"{_num(load['position_ft'])} ft"
            end = "-"
        else:
            label = f"Uniform {index}"
            magnitude = f"{_num(load['magnitude'])} kip/ft"
            start = f"{_num(load['start_ft'])} ft"
            end = f"{_num(load['end_ft'])} ft"
        values = (label, magnitude, start, end, load["direction"].capitalize())
        for x, value in zip(widths, values):
            page.text(x, y, value, 8, color=INK)
        page.line(44, y - 5, 568, y - 5, color=(0.90, 0.92, 0.93), width=0.5)
        y -= 18
    page.paragraph(44, max(38, y - 5), "Loads are service-level. Include member self-weight if applicable; the application does not add it or generate load combinations.", width=105, size=7, leading=9)


def _draw_results_page(pages: list[Page], design: dict[str, Any], section: dict[str, Any], material: dict[str, Any], result: dict[str, Any], source: str) -> None:
    page = Page()
    pages.append(page)
    _header(page, "Analysis results", "Calculated response and limited screening checks")
    page.text(44, 676, "SUPPORT REACTIONS", 10, bold=True, color=NAVY)
    reaction = result["reaction"]
    rows = [
        ("Left vertical reaction", f"{_num(reaction['left'])} kip  (upward positive)"),
        (("Fixed reaction moment" if design["support"] == "cantilever" else "Right vertical reaction"),
         f"{_num(reaction['fixed_moment'] / 12 if design['support'] == 'cantilever' else reaction['right'])} {'kip-ft (CCW positive)' if design['support'] == 'cantilever' else 'kip (upward positive)'}"),
        ("Maximum absolute moment", f"{_num(abs(result['moment_peak']['value']) / 12)} kip-ft at {_num(result['moment_peak']['x'] / 12)} ft"),
        ("Maximum absolute deflection", f"{_num(abs(result['deflection_peak']['value']), 4)} in at {_num(result['deflection_peak']['x'] / 12)} ft"),
    ]
    y = 657
    for label, value in rows:
        page.rect(44, y - 5, 524, 21, fill=PALE)
        page.text(52, y + 2, label, 8, bold=True, color=MUTED)
        page.text(245, y + 2, value, 8, color=INK)
        y -= 25

    y -= 3
    page.text(44, y, "CHECKS", 10, bold=True, color=NAVY)
    y -= 18
    strength = result["strength"]
    if strength["checked"]:
        status = "PASS" if strength["pass"] else "FAIL"
        strength_line = f"{status}: Demand {_num(strength['demand_kip_ft'])} kip-ft / allowable {_num(strength['allowable_kip_ft'])} kip-ft; utilization {_num(strength['utilization'] * 100, 1)}%."
    else:
        status = "NOT CHECKED"
        strength_line = f"NOT CHECKED: Compact-section screen not met. Elastic stress {_num(strength['stress_ksi'])} ksi; no ASD capacity reported."
    page.rect(44, y - 29, 524, 39, fill=PALE, stroke=(0.86, 0.89, 0.90))
    page.text(52, y, f"Flexural strength - AISC 360-22 ASD: {status}", 8, bold=True, color=GREEN if status == "PASS" else RED if status == "FAIL" else GOLD)
    page.paragraph(52, y - 13, strength_line.split(": ", 1)[-1], width=102, size=7, leading=9)
    y -= 48
    deflection_limit = result["deflection_limit_in"]
    status = "PASS" if result["deflection_pass"] else "FAIL"
    page.rect(44, y - 27, 524, 37, fill=PALE, stroke=(0.86, 0.89, 0.90))
    page.text(52, y, f"Service deflection: {status}", 8, bold=True, color=GREEN if result["deflection_pass"] else RED)
    page.text(52, y - 14, f"Demand {_num(abs(result['deflection_peak']['value']), 4)} in / limit {_num(deflection_limit, 4)} in.", 7, color=INK)
    y -= 47

    page.text(44, y, "COMPACTNESS SCREEN", 10, bold=True, color=NAVY)
    y -= 15
    compact = result["compactness"]
    page.text(48, y, f"Flange bf/(2tf) = {_num(compact['flange_ratio'], 2)} / limit {_num(compact['flange_limit'], 2)}", 7, color=INK)
    y -= 12
    page.text(48, y, f"Web estimated (d-2tf)/tw = {_num(compact['web_ratio'], 2)} / limit {_num(compact['web_limit'], 2)}", 7, color=INK)
    y -= 20

    page.text(44, y, "CALCULATION BASIS AND LIMITATIONS", 10, bold=True, color=NAVY)
    y -= 15
    basis = (
        f"Linear elastic, small-deflection, strong-axis analysis in U.S. customary units. {material['grade']} steel uses Fy = {material['Fy']:g} ksi and E = {material['E']:g} ksi. "
        "The ASD flexural screen uses Mn = Fy Zx and allowable moment Mn/1.67 only when the section passes the compactness screen and assumes continuous lateral bracing. "
        "Web slenderness uses (d-2tf)/tw because clear web depth is not in the catalog. No lateral-torsional buckling, shear strength, noncompact/slender local buckling, bearing, connections, vibration, fire, load combinations, or code certification is included. "
        "The deflection limit is a configurable screening criterion, not a universal requirement."
    )
    y = page.paragraph(48, y, basis, width=104, size=7, leading=9)
    page.rect(44, max(39, y - 38), 524, 35, fill=PALE_GOLD, stroke=(0.91, 0.86, 0.75))
    page.paragraph(52, max(58, y - 15), "Educational preliminary results only. This sheet is not a substitute for review by a qualified structural professional and does not establish that a beam is safe for construction.", width=103, size=7, leading=9, color=(0.40, 0.32, 0.18), bold=True)


def _draw_beam(page: Page, design: dict[str, Any], result: dict[str, Any], x: float, y: float, width: float, height: float) -> None:
    page.rect(x, y, width, height, fill=WHITE, stroke=(0.87, 0.90, 0.91))
    page.text(x + 10, y + height - 15, "BEAM AND LOADS", 8, bold=True, color=NAVY)
    x0, x1 = x + 42, x + width - 30
    beam_y = y + 57
    span_ft = design["span_ft"]
    map_x = lambda loc: x0 + loc / span_ft * (x1 - x0)
    page.line(x0, beam_y, x1, beam_y, color=NAVY, width=3)
    if design["support"] == "cantilever":
        page.rect(x0 - 9, beam_y - 24, 8, 48, fill=(0.91, 0.94, 0.95), stroke=MUTED)
        page.text(x0 - 15, beam_y - 35, "FIXED", 6, bold=True, color=MUTED)
    else:
        for sx in (x0, x1):
            page.polygon([(sx, beam_y - 2), (sx - 9, beam_y - 16), (sx + 9, beam_y - 16)], fill=WHITE, stroke=NAVY)
            page.line(sx - 13, beam_y - 18, sx + 13, beam_y - 18, color=MUTED, width=0.7)
        page.text(x0 - 8, beam_y - 31, "PIN", 6, bold=True, color=MUTED)
        page.text(x1 - 11, beam_y - 31, "ROLLER", 6, bold=True, color=MUTED)
    page.text(x0 - 5, beam_y + 8, "0 ft", 6, color=MUTED)
    page.text(x1 - 24, beam_y + 8, f"{_num(span_ft)} ft", 6, color=MUTED)
    for index, load in enumerate(design.get("loads", [])):
        down = load["direction"] == "down"
        target_y = beam_y + 3 if down else beam_y - 3
        start_y = beam_y + 32 + (index % 2) * 5 if down else beam_y - 32 - (index % 2) * 5
        if load["type"] == "point":
            loc = map_x(load["position_ft"])
            page.arrow(loc, start_y, loc, target_y, color=GOLD)
            label = f"{_num(load['magnitude'])} kip"
            page.text(loc - 18, start_y + (4 if down else -11), label, 6, bold=True, color=GOLD)
        else:
            a, b = map_x(load["start_ft"]), map_x(load["end_ft"])
            page.line(a, start_y, b, start_y, color=GOLD, width=0.8)
            for step in range(7):
                loc = a + (b - a) * step / 6
                page.arrow(loc, start_y, loc, target_y, color=GOLD, width=0.8)
            page.text((a + b) / 2 - 18, start_y + (4 if down else -11), f"{_num(load['magnitude'])} kip/ft", 6, bold=True, color=GOLD)
    reaction = result["reaction"]
    if design["support"] == "simple":
        for sx, value in ((x0, reaction["left"]), (x1, reaction["right"])):
            start_y, end_y = (beam_y - 32, beam_y - 5) if value >= 0 else (beam_y - 5, beam_y - 32)
            page.arrow(sx, start_y, sx, end_y, color=TEAL)
    else:
        value = reaction["left"]
        start_y, end_y = (beam_y - 34, beam_y - 5) if value >= 0 else (beam_y - 5, beam_y - 34)
        page.arrow(x0 + 18, start_y, x0 + 18, end_y, color=TEAL)


def _draw_plot(page: Page, x: float, y: float, width: float, height: float, title: str, units: str, series: list[tuple[float, float]], color: tuple[float, float, float], span_in: float, *, invert: bool = False, threshold: float | None = None) -> None:
    page.rect(x, y, width, height, fill=WHITE, stroke=(0.87, 0.90, 0.91))
    page.text(x + 9, y + height - 16, title, 8, bold=True, color=NAVY)
    left, right = x + 32, x + width - 10
    bottom, top = y + 29, y + height - 37
    values = [value for _, value in series] + ([threshold] if threshold is not None else [])
    low, high = min([0.0, *values]), max([0.0, *values])
    if abs(high - low) < 1e-12:
        low, high = -1.0, 1.0
    pad = (high - low) * 0.12
    low, high = low - pad, high + pad
    map_y = (lambda value: bottom + (value - low) / (high - low) * (top - bottom)) if invert else (lambda value: bottom + (value - low) / (high - low) * (top - bottom))
    # Deflection is drawn downward from zero by reversing the chart's vertical range.
    if invert:
        map_y = lambda value: top - (value - low) / (high - low) * (top - bottom)
    max_x = span_in or 1.0
    map_x = lambda value: left + value / max_x * (right - left)
    zero_y = map_y(0.0)
    page.line(left, bottom, right, bottom, color=(0.92, 0.94, 0.95), width=0.5)
    page.line(left, top, right, top, color=(0.92, 0.94, 0.95), width=0.5)
    page.line(left, zero_y, right, zero_y, color=(0.78, 0.82, 0.84), width=0.7)
    if threshold is not None:
        y_threshold = map_y(threshold)
        page.line(left, y_threshold, right, y_threshold, color=RED, width=0.8, dash=True)
        page.text(right - 76, y_threshold + 4, f"Allowable {_num(threshold)}", 5.5, color=RED)
    points = [(map_x(px), map_y(py)) for px, py in series]
    page.polyline(points, color=color, width=1.3)
    peak = max(series, key=lambda item: abs(item[1]))
    page.text(left, y + height - 28, f"Peak {_num(abs(peak[1]), 3)} {units}", 6, color=MUTED)
    page.text(left, y + 9, "0 ft", 6, color=MUTED)
    page.text(right - 20, y + 9, f"{_num(span_in / 12, 1)} ft", 6, color=MUTED)


def _draw_diagram_page(pages: list[Page], design: dict[str, Any], result: dict[str, Any]) -> None:
    page = Page()
    pages.append(page)
    _header(page, "Beam diagrams", "Diagram sign convention: positive sagging moment; downward deflection positive")
    _draw_beam(page, design, result, 44, 563, 524, 112)
    charts = result["diagrams"]
    _draw_plot(page, 44, 340, 252, 206, "Shear force", "kip", charts["shear"], TEAL, result["span_in"])
    _draw_plot(page, 316, 340, 252, 206, "Bending moment", "kip-ft", charts["moment"], GOLD, result["span_in"])
    _draw_plot(page, 44, 117, 252, 206, "Deflection", "in", charts["deflection"], BLUE, result["span_in"], invert=True)
    threshold = result["strength"]["allowable_kip_ft"] if result["strength"]["checked"] else None
    _draw_plot(page, 316, 117, 252, 206, "Moment vs allowable", "kip-ft", charts["capacity"], GOLD, result["span_in"], threshold=threshold)
    if not result["strength"]["checked"]:
        page.text(326, 128, "No allowable shown: compact-section screen not met.", 6, color=GOLD)
    page.text(44, 91, "Source: AISC Shapes Database v16.0, U.S. customary properties. This calculation sheet reports only the checks listed on page 2.", 7, color=MUTED)


def _pdf_bytes(pages: list[Page]) -> bytes:
    objects: list[bytes | None] = [None]

    def add(data: bytes) -> int:
        objects.append(data)
        return len(objects) - 1

    catalog_id = add(b"")
    pages_id = add(b"")
    regular_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    bold_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    page_ids: list[int] = []
    for page in pages:
        stream = ("\n".join(page.ops) + "\n").encode("ascii", "replace")
        content_id = add(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream")
        page_id = add(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_W:.0f} {PAGE_H:.0f}] ".encode("ascii")
            + f"/Resources << /Font << /F1 {regular_id} 0 R /F2 {bold_id} 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii")
        )
        page_ids.append(page_id)
    kids = " ".join(f"{obj_id} 0 R" for obj_id in page_ids)
    objects[catalog_id] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")
    objects[pages_id] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj_id, body in enumerate(objects[1:], start=1):
        assert body is not None
        offsets.append(len(output))
        output.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(objects)} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    return bytes(output)


def export_calculation_sheet(path: str | Path, design: dict[str, Any], section: dict[str, Any], material: dict[str, Any], result: dict[str, Any], source: str) -> None:
    pages: list[Page] = []
    _draw_input_pages(pages, design, section, material, source)
    _draw_results_page(pages, design, section, material, result, source)
    _draw_diagram_page(pages, design, result)
    Path(path).write_bytes(_pdf_bytes(pages))
