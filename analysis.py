"""Stateless beam analysis routines. Loads use downward-positive signs."""

from __future__ import annotations

import math
from typing import Any


def get_breaks(span_in: float, points: list[dict], uniforms: list[dict]) -> list[float]:
    return sorted({0.0, span_in, *(load["x"] for load in points), *(v for load in uniforms for v in (load["a"], load["b"]))})


def reactions(span_in: float, support: str, points: list[dict], uniforms: list[dict]) -> dict[str, float]:
    total = sum(load["p"] for load in points) + sum(load["q"] * (load["b"] - load["a"]) for load in uniforms)
    moment = sum(load["p"] * load["x"] for load in points) + sum(
        load["q"] * (load["b"] - load["a"]) * (load["a"] + load["b"]) / 2 for load in uniforms
    )
    if support == "cantilever":
        return {"left": total, "right": 0.0, "fixed_moment": moment, "total": total}
    right = moment / span_in
    return {"left": total - right, "right": right, "fixed_moment": 0.0, "total": total}


def shear_at(x: float, support: str, points: list[dict], uniforms: list[dict], reaction: dict) -> float:
    if support == "cantilever":
        point_right = sum(load["p"] for load in points if load["x"] > x)
        uniform_right = sum(load["q"] * max(0.0, load["b"] - max(x, load["a"])) for load in uniforms)
        return point_right + uniform_right
    point_left = sum(load["p"] for load in points if load["x"] <= x)
    uniform_left = sum(load["q"] * max(0.0, min(x, load["b"]) - load["a"]) for load in uniforms)
    return reaction["left"] - point_left - uniform_left


def moment_at(x: float, support: str, points: list[dict], uniforms: list[dict], reaction: dict) -> float:
    if support == "cantilever":
        point_moment = sum(load["p"] * max(0.0, load["x"] - x) for load in points)
        uniform_moment = sum(load["q"] * (max(0.0, load["b"] - x) ** 2 - max(0.0, load["a"] - x) ** 2) / 2 for load in uniforms)
        return -(point_moment + uniform_moment)
    point_moment = sum(load["p"] * max(0.0, x - load["x"]) for load in points)
    uniform_moment = sum(load["q"] * (max(0.0, x - load["a"]) ** 2 - max(0.0, x - load["b"]) ** 2) / 2 for load in uniforms)
    return reaction["left"] * x - point_moment - uniform_moment


def _integrals_to(x: float, breaks: list[float], moment_fn) -> tuple[float, float]:
    bounds = [0.0, *(v for v in breaks if 0.0 < v < x), x]
    integral_m = integral_xm = 0.0
    gauss = 1 / math.sqrt(3)
    for start, end in zip(bounds, bounds[1:]):
        if end <= start:
            continue
        midpoint, half = (start + end) / 2, (end - start) / 2
        x1, x2 = midpoint - half * gauss, midpoint + half * gauss
        m1, m2 = moment_fn(x1), moment_fn(x2)
        integral_m += half * (m1 + m2)
        integral_xm += half * (x1 * m1 + x2 * m2)
    return integral_m, integral_xm


def _bisect(fn, lo: float, hi: float) -> float:
    f_lo = fn(lo)
    for _ in range(60):
        mid = (lo + hi) / 2
        f_mid = fn(mid)
        if abs(f_mid) < 1e-11 or hi - lo < 1e-8:
            return mid
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def analyze(
    span_ft: float,
    support: str,
    section: dict[str, Any],
    points: list[dict],
    uniforms: list[dict],
    elastic_modulus_ksi: float,
    yield_strength_ksi: float,
    limit_ratio: int | None = 360,
    custom_limit_in: float | None = None,
) -> dict[str, Any]:
    """Analyze one span. Input loads: P in kip, x/a/b in inches, q in kip/in."""
    span_in = span_ft * 12
    reaction = reactions(span_in, support, points, uniforms)
    breaks = get_breaks(span_in, points, uniforms)
    moment_fn = lambda x: moment_at(x, support, points, uniforms, reaction)
    shear_fn = lambda x: shear_at(x, support, points, uniforms, reaction)
    total_integral_m, total_integral_xm = _integrals_to(span_in, breaks, moment_fn)
    ei = elastic_modulus_ksi * section["Ix"]

    def deflection_at(x: float) -> float:
        integral_m, integral_xm = _integrals_to(x, breaks, moment_fn)
        if support == "cantilever":
            return -(x * integral_m - integral_xm) / ei
        slope_constant = (total_integral_m - total_integral_xm / span_in) / ei
        return slope_constant * x - (x * integral_m - integral_xm) / ei

    def slope_at(x: float) -> float:
        integral_m, _ = _integrals_to(x, breaks, moment_fn)
        if support == "cantilever":
            return -integral_m / ei
        return (total_integral_m - total_integral_xm / span_in - integral_m) / ei

    moment_candidates = list(breaks)
    for start, end in zip(breaks, breaks[1:]):
        if end - start < 1e-8:
            continue
        inset = min((end - start) * 1e-7, 1e-7)
        left, right = start + inset, end - inset
        if shear_fn(left) * shear_fn(right) < 0:
            moment_candidates.append(_bisect(shear_fn, left, right))
    max_moment_x = max(moment_candidates, key=lambda x: abs(moment_fn(x)))

    deflection_candidates = [0.0, span_in]
    scan_count = 1000
    previous_x, previous_slope = 0.0, slope_at(0.0)
    for i in range(1, scan_count + 1):
        x = span_in * i / scan_count
        slope = slope_at(x)
        deflection_candidates.append(x)
        if previous_slope * slope < 0:
            deflection_candidates.append(_bisect(slope_at, previous_x, x))
        previous_x, previous_slope = x, slope
    max_deflection_x = max(deflection_candidates, key=lambda x: abs(deflection_at(x)))

    root = math.sqrt(elastic_modulus_ksi / yield_strength_ksi)
    flange_ratio = section["flangeWidth"] / (2 * section["flangeThickness"])
    web_ratio = (section["depth"] - 2 * section["flangeThickness"]) / section["webThickness"]
    flange_limit, web_limit = 0.38 * root, 3.76 * root
    compact = flange_ratio <= flange_limit and web_ratio <= web_limit
    allowable_moment_kip_in = yield_strength_ksi * section["Zx"] / 1.67 if compact else None
    moment_demand_kip_in = abs(moment_fn(max_moment_x))
    utilization = moment_demand_kip_in / allowable_moment_kip_in if allowable_moment_kip_in else None
    deflection_limit = custom_limit_in if custom_limit_in is not None else span_in / (limit_ratio or 360)

    count = 281
    positions = {span_in * i / (count - 1) for i in range(count)}
    positions.update(breaks)
    for x in breaks:
        delta = min(span_in / 100000, 0.01)
        if x > 0:
            positions.add(x - delta)
        if x < span_in:
            positions.add(x + delta)
    ordered_positions = sorted(x for x in positions if 0 <= x <= span_in)
    return {
        "span_in": span_in,
        "support": support,
        "reaction": reaction,
        "moment_peak": {"x": max_moment_x, "value": moment_fn(max_moment_x)},
        "deflection_peak": {"x": max_deflection_x, "value": deflection_at(max_deflection_x)},
        "deflection_limit_in": deflection_limit,
        "deflection_pass": abs(deflection_at(max_deflection_x)) <= deflection_limit,
        "compactness": {
            "compact": compact,
            "flange_ratio": flange_ratio,
            "web_ratio": web_ratio,
            "flange_limit": flange_limit,
            "web_limit": web_limit,
        },
        "strength": {
            "checked": compact,
            "demand_kip_ft": moment_demand_kip_in / 12,
            "stress_ksi": moment_demand_kip_in / section["Sx"],
            "allowable_kip_ft": allowable_moment_kip_in / 12 if allowable_moment_kip_in else None,
            "utilization": utilization,
            "pass": utilization <= 1 if utilization is not None else None,
        },
        "diagrams": {
            "shear": [(x, shear_fn(x)) for x in ordered_positions],
            "moment": [(x, moment_fn(x) / 12) for x in ordered_positions],
            "deflection": [(x, deflection_at(x)) for x in ordered_positions],
            "capacity": [(x, abs(moment_fn(x)) / 12) for x in ordered_positions],
        },
    }
