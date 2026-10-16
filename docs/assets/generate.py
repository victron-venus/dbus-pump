#!/usr/bin/env python3
"""Generate documented example SVGs without third-party packages.

These are explanatory diagrams, not live telemetry or hardware-test evidence.
Run from any directory; --check verifies checked-in output without writing it.
"""

import argparse
import math
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent
CAPACITY_L = 387.0
OFFSET_CM = 18.0
RADIUS_CM = 35.56
BLUE = "#165ea8"
GREEN = "#176443"
ORANGE = "#a04a08"
INK = "#172b4d"
MUTED = "#435777"


def text(x, y, value, size=17, color=INK, weight="normal", anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def line(x1, y1, x2, y2, color=MUTED, width=2, dash="", arrow=False):
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    if arrow:
        extra += ' marker-end="url(#arrow)"'
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="{width}"{extra}/>'
    )


def box(x, y, w, h, fill="#edf3fb", stroke="#9db4d1"):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}"/>'
    )


def svg(title, description, body, height=600):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="{height}" '
        f'viewBox="0 0 1040 {height}" role="img" aria-labelledby="title desc">\n'
        f'<title id="title">{escape(title)}</title>\n'
        f'<desc id="desc">{escape(description)}</desc>\n'
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#435777"/></marker></defs>\n'
        f'<rect width="1040" height="{height}" rx="20" fill="#fff"/>\n'
        '<g font-family="DejaVu Sans, Arial, sans-serif">\n' + "\n".join(body) + "\n</g>\n</svg>\n"
    )


def architecture():
    b = [
        text(36, 47, "Water system · data and commands", 28, weight="bold"),
        text(36, 78, "One primary measurement; explicit units; stable protocol identities", 18),
        box(36, 112, 282, 262),
        text(56, 148, "Home Assistant", 22, weight="bold"),
        text(56, 183, "Primary level: cm or %"),
        text(56, 213, "Unit attribute checked"),
        text(56, 243, "Pump + valve states"),
        text(56, 273, "Optional raw cm: diagnostics"),
        text(56, 316, "Existing HA automations", 17, ORANGE, "bold"),
        text(56, 343, "Site actuator owner"),
        box(366, 112, 310, 262, "#eaf5ef", "#8dbba2"),
        text(386, 148, "Cerbo · dbus-pump", 22, weight="bold"),
        text(386, 183, "HTTP worker + circuit breaker"),
        text(386, 213, "Unit / geometry validation"),
        text(386, 243, "One normalized % + volume"),
        text(386, 273, "Main-loop freshness checks"),
        text(386, 316, "AUTO disabled at this site", 17, ORANGE, "bold"),
        text(386, 343, "Manual / shutdown can actuate"),
        box(724, 112, 280, 262),
        text(744, 148, "Native D-Bus", 22, weight="bold"),
        text(744, 183, "Tank · /Level (%)"),
        text(744, 213, "/Capacity, /Remaining (m³)"),
        text(744, 243, "Pump / valve · /State"),
        text(744, 273, "Commands · /Mode"),
        text(744, 316, "Translated display labels", 17, GREEN, "bold"),
        text(744, 343, "IDs + numeric values stable"),
        line(318, 204, 366, 204, BLUE, 3, arrow=True),
        line(676, 204, 724, 204, BLUE, 3, arrow=True),
        line(864, 397, 178, 397, ORANGE, 2, "7 5", True),
        line(864, 374, 864, 397, ORANGE, 2, "7 5"),
        line(178, 397, 178, 375, ORANGE, 2, "7 5", True),
        text(435, 426, "Explicit manual / shutdown; AUTO only when enabled", 15, ORANGE),
        box(724, 465, 280, 86, "#f2f4f8"),
        text(744, 500, "GX / VRM + Cerbo MQTT", 18, weight="bold"),
        text(744, 529, "Displays and subscribers", 16),
        line(864, 398, 864, 458, BLUE, 3, arrow=True),
        line(36, 477, 85, 477, BLUE, 3, arrow=True),
        text(99, 483, "Telemetry", 17),
        line(265, 477, 314, 477, ORANGE, 2, "7 5", True),
        text(328, 483, "Actuation path", 17),
        text(36, 527, "No arbitration between HA and other switch writers.", 17, ORANGE),
        text(
            36,
            562,
            "Diagram describes the configured site; not a live status or safety certification.",
            15,
        ),
    ]
    return svg(
        "dbus-pump architecture and command ownership",
        "HA supplies primary level, unit and switch states. Cerbo validates and normalizes the "
        "measurement, then publishes native D-Bus and MQTT telemetry. HA automations own site "
        "actuation. Bridge AUTO stays disabled, but manual requests and shutdown "
        "can still actuate.",
        b,
    )


def calibration():
    left, top, width, height = 90, 145, 790, 320

    def px(cm):
        return left + cm / 130 * width

    def py(percent):
        return top + height - percent / 100 * height

    liters_per_cm = math.pi * RADIUS_CM**2 / 1000
    full_cm = OFFSET_CM + CAPACITY_L / liters_per_cm
    sample_l = (93 - OFFSET_CM) * liters_per_cm
    sample_pct = 100 * sample_l / CAPACITY_L
    b = [
        text(36, 47, "Calibration · height to usable volume", 28, weight="bold"),
        text(
            36, 78, "Vertical cylinder · 387 L capacity · 35.56 cm radius · empty reading 18 cm", 18
        ),
        text(90, 121, "Level (%)", 17, BLUE, "bold"),
        text(902, 121, "Volume (L)", 17, GREEN, "bold"),
    ]
    for percent in (0, 25, 50, 75, 100):
        y = py(percent)
        b += [
            line(left, y, left + width, y, "#dbe3ef", 1),
            text(left - 15, y + 6, percent, 16, BLUE, anchor="end"),
            text(902, y + 6, f"{CAPACITY_L * percent / 100:g}", 16, GREEN),
        ]
    for cm in (0, 18, 40, 60, 80, 100, 130):
        x = px(cm)
        b += [
            line(x, top, x, top + height, "#e7edf5", 1),
            text(x, top + height + 28, cm, 16, anchor="middle"),
        ]
    points = [
        (px(0), py(0)),
        (px(OFFSET_CM), py(0)),
        (px(full_cm), py(100)),
        (px(130), py(100)),
    ]
    coords = " ".join(f"{x:.3f},{y:.3f}" for x, y in points)
    b += [
        f'<polyline points="{coords}" fill="none" stroke="{BLUE}" stroke-width="4"/>',
        line(px(93), py(0), px(93), py(sample_pct), ORANGE, 2, "6 5"),
        f'<circle cx="{px(93):.3f}" cy="{py(sample_pct):.3f}" r="6" fill="{ORANGE}"/>',
        box(132, 165, 390, 88, "#fff6e9", "#d5b488"),
        text(149, 197, f"93 cm → {sample_l:.2f} L → {sample_pct:.2f}%", 20, ORANGE, "bold"),
        text(149, 229, "One primary sample drives both outputs", 16),
        text(px(full_cm) - 9, top - 16, f"Full at {full_cm:.3f} cm", 16, anchor="end"),
        text(485, 530, "Primary sensor reading (cm)", 18, anchor="middle"),
        text(
            36, 570, "Calculated example, not measured data. Output clamps to 0-100% / 0-387 L.", 16
        ),
    ]
    return svg(
        "Example tank calibration curve",
        f"Calculated vertical-cylinder curve using capacity 387 L, radius 35.56 cm and "
        f"empty offset 18 cm. Each usable centimetre is {liters_per_cm:.3f} L. "
        f"93 cm gives {sample_l:.2f} L and {sample_pct:.2f} percent; full is "
        f"{full_cm:.3f} cm. Values below empty and above capacity are clamped.",
        b,
    )


def hysteresis():
    b = [
        text(36, 47, "Valve control · hysteresis and freshness", 28, weight="bold"),
        text(36, 78, "Applies only with ENABLE_CONTROL=True and AUTO mode", 18, ORANGE),
        box(36, 122, 286, 136, "#eaf5ef", "#8dbba2"),
        text(58, 160, "Fresh level ≤ 30%", 23, GREEN, "bold"),
        text(58, 195, "Request OPEN", 21),
        text(58, 229, "Normal transition timer applies", 15),
        box(360, 122, 320, 136, "#f2f4f8"),
        text(380, 160, "30% < level < 85%", 23, weight="bold"),
        text(380, 195, "Keep previous decision", 21),
        text(380, 229, "After stale-close: remain CLOSED", 15),
        box(718, 122, 286, 136, "#edf3fb"),
        text(740, 160, "Fresh level ≥ 85%", 23, BLUE, "bold"),
        text(740, 195, "Request CLOSED", 21),
        text(740, 229, "Normal transition timer applies", 15),
        line(68, 294, 972, 294, MUTED, 2, arrow=True),
        text(68, 324, "0%", 16),
        text(331, 324, "30%", 16),
        text(834, 324, "85%", 16),
        text(975, 324, "100% level", 16, anchor="end"),
        box(36, 362, 595, 134, "#fff6e9", "#d5b488"),
        text(57, 397, "No fresh level for 120 s → request CLOSED", 21, ORANGE, "bold"),
        text(57, 429, "Stale-close bypasses the normal transition timer.", 17),
        text(57, 461, "Recovery needs a low reading to open again.", 17),
        box(662, 362, 342, 134, "#f2f4f8"),
        text(682, 397, "Normal minimum interval: 60 s", 18, weight="bold"),
        text(682, 429, "Manual ON/OFF has priority.", 17),
        text(682, 461, "Pump: manual control only.", 17),
        text(
            36,
            538,
            "Numbers are configurable defaults. Requested state is not proof "
            "of physical valve position.",
            16,
        ),
        text(
            36,
            568,
            "Site: HA automations own control; bridge AUTO disabled. "
            "Shutdown may still close the valve.",
            16,
        ),
    ]
    return svg(
        "Default valve hysteresis and stale-data behavior",
        "When AUTO is enabled, fresh level at or below 30 percent requests opening; at or above "
        "85 percent requests closure. Between thresholds the prior decision is held. Normal "
        "transitions wait 60 seconds. No fresh sample for 120 seconds requests closure. "
        "Manual ON and OFF override AUTO. At this site HA owns automation and bridge AUTO is off.",
        b,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify output without writing")
    args = parser.parse_args()
    diagrams = {
        "architecture.svg": architecture(),
        "calibration.svg": calibration(),
        "hysteresis.svg": hysteresis(),
    }
    different = []
    for name, content in diagrams.items():
        path = OUT / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                different.append(name)
        else:
            path.write_text(content, encoding="utf-8")
    if different:
        parser.exit(1, "Out-of-date diagrams: " + ", ".join(different) + "\n")
    print("SVG diagrams are current" if args.check else "Generated 3 SVG diagrams")


if __name__ == "__main__":
    main()
