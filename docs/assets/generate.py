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
TEAL = "#087e73"
PURPLE = "#6239bc"
CORAL = "#c53c41"
SNAPSHOT_AT = "2026-10-16T03:13:49Z"
SNAPSHOT_CM = 49.0
SNAPSHOT_VERSION = "0.1.7+units.2c5045f"


def calibrated_percent(cm):
    """The documented vertical-cylinder model, bounded to usable capacity."""
    liters = (cm - OFFSET_CM) * math.pi * RADIUS_CM**2 / 1000
    return max(0.0, min(100.0, liters / CAPACITY_L * 100))


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


def poster_header(eyebrow, title, subtitle, height):
    """Shared high-contrast visual treatment for the process/result pair."""
    return [
        f'<rect width="1040" height="{height}" rx="20" fill="#f3f6fc"/>',
        '<path d="M20 0 H1020 Q1040 0 1040 20 V116 H0 V20 Q0 0 20 0Z" fill="#172653"/>',
        '<circle cx="969" cy="17" r="109" fill="#2866d8" opacity=".23"/>',
        '<circle cx="1025" cy="105" r="106" fill="#1eb69b" opacity=".14"/>',
        text(32, 29, eyebrow, 13, "#99e8db", "bold"),
        text(32, 66, title, 29, "#ffffff", "bold"),
        text(32, 95, subtitle, 16, "#dce5ff"),
    ]


def process_step(x, number, title, caption, lines, color, fill):
    b = [
        box(x, 154, 174, 236, "#ffffff", "#d4deee"),
        f'<path d="M{x + 14} 154 H{x + 160} Q{x + 174} 154 {x + 174} 168 '
        f'V182 H{x} V168 Q{x} 154 {x + 14} 154Z" fill="{fill}"/>',
        text(x + 14, 174, f"0{number}  {caption}", 12, color, "bold"),
        text(x + 14, 220, title, 20, color, "bold"),
    ]
    for i, value in enumerate(lines):
        b.append(text(x + 14, 253 + 31 * i, value, 13.5))
    return b


def measurement_process():
    b = poster_header(
        "PROCESS / MEASUREMENT → PUBLICATION",
        "One measurement. One consistent tank level.",
        "Explicit units and one authoritative source keep the displayed level and volume aligned.",
        990,
    )
    b += [text(32, 141, "TELEMETRY FLOW", 12, MUTED, "bold")]
    stages = [
        (
            "Home Assistant",
            "SOURCE",
            [
                "Primary level entity",
                "Configured unit: cm / %",
                "HA unit metadata",
                "Pump + valve states",
            ],
            BLUE,
            "#e5efff",
        ),
        (
            "Validate",
            "ACCEPT / REJECT",
            ["Finite number", "Matching units", "Valid tank geometry", "Fresh acquisition time"],
            PURPLE,
            "#eee8fc",
        ),
        (
            "Normalize",
            "ONE VALUE",
            [
                "cm → liters → percent",
                "% → canonical percent",
                "Bounded to 0-100%",
                "Unrounded for control",
            ],
            TEAL,
            "#dff5ee",
        ),
        (
            "Native D-Bus",
            "PUBLISH",
            ["/Level = percent", "/Remaining = m³", "/Capacity = m³", "Stable names + IDs"],
            BLUE,
            "#e5efff",
        ),
        (
            "Display",
            "SUBSCRIBERS",
            ["GX / VRM / MQTT", "Readable, translated", "display labels", "Rounded for display"],
            PURPLE,
            "#eee8fc",
        ),
    ]
    for i, (title, caption, lines, color, fill) in enumerate(stages):
        x = 32 + 200 * i
        b += process_step(x, i + 1, title, caption, lines, color, fill)
        if i < 4:
            b.append(line(x + 178, 271, x + 194, 271, MUTED, 2.5, arrow=True))
    b += [
        box(32, 414, 976, 82, "#e0f3ec", "#acd7c8"),
        text(52, 445, "Shared canonical value", 19, TEAL, "bold"),
        text(
            52,
            474,
            "Level (%) → Remaining = capacity · level / 100 → AUTO thresholds, if enabled",
            17,
        ),
        box(32, 520, 472, 143, "#fff1ef", "#efc7c2"),
        text(52, 553, "Rejected samples never refresh the deadline", 18, CORAL, "bold"),
        text(52, 584, "Bad units, nonfinite data, future or expired samples", 15),
        text(52, 610, "cannot become a new valid tank reading.", 15),
        text(52, 639, "Optional secondary cm sensor: diagnostics only.", 15, CORAL),
        box(528, 520, 480, 143, "#edf2ff", "#ccd8f5"),
        text(548, 553, "Freshness is a software acquisition check", 18, BLUE, "bold"),
        text(548, 584, "Cached readings keep their original expiry deadline.", 15),
        text(548, 610, "AUTO stale-close applies only when control is enabled.", 15),
        text(548, 639, "It does not prove a physical sensor changed.", 15, BLUE),
        box(32, 687, 472, 228, "#ffffff", "#d6c8f0"),
        text(52, 723, "CONTROL OWNERSHIP", 13, PURPLE, "bold"),
        text(52, 755, "Configured site: HA owns automation", 21, PURPLE, "bold"),
        text(52, 790, "Bridge automatic control = disabled", 17, weight="bold"),
        text(52, 822, "Normal operation still permits explicit manual writes.", 15),
        text(52, 848, "Normal shutdown can request valve closure.", 15),
        text(52, 883, "Multiple writers are not automatically arbitrated.", 15, CORAL),
        box(528, 687, 480, 228, "#ffffff", "#acd7c8"),
        text(548, 723, "READ-ONLY DRY-RUN", 13, TEAL, "bold"),
        text(548, 755, "HA snapshot → memory → printed preview", 20, TEAL, "bold"),
        text(548, 790, "No native D-Bus connection or registration.", 16),
        text(548, 822, "No actuator commands. No service heartbeat.", 16),
        text(548, 848, "The HTTP session closes when the preview ends.", 15),
        text(548, 883, "The preview does not test physical actuation.", 15, TEAL),
        text(
            32,
            950,
            "Static process diagram · describes the configured design, not a live status.",
            15,
            MUTED,
        ),
        text(
            32,
            975,
            "Sensor state and reported switch state are not proof of "
            "physical water level or valve position.",
            14,
            MUTED,
        ),
    ]
    return svg(
        "Measurement process, control ownership and read-only preview",
        "Home Assistant supplies one primary measurement in cm or percent. Validation checks "
        "finite data, unit metadata, geometry and acquisition age before normalization. The same "
        "canonical percent drives D-Bus level and remaining volume, and control if enabled. "
        "Displays receive formatted values. HA owns automation at this site, bridge AUTO is off; "
        "normal manual and shutdown operations can actuate. Dry-run reads HA, uses only in-memory "
        "services, writes neither actuators nor heartbeat, and closes its HTTP session. This is "
        "a static design diagram, not live telemetry or a physical acceptance test.",
        b,
        height=990,
    )


def measured_result():
    left, top, width, height = 104, 238, 800, 270

    def px(cm):
        return left + cm / 120 * width

    def py(percent):
        return top + height - percent / 120 * height

    full_cm = OFFSET_CM + CAPACITY_L * 1000 / (math.pi * RADIUS_CM**2)
    sample_pct = calibrated_percent(SNAPSHOT_CM)
    b = poster_header(
        "RESULT / MATHEMATICAL COMPARISON + SAVED OBSERVATION",
        "Height is not percentage.",
        "A calibrated tank model replaces the incorrect assumption "
        "that a centimeter equals one percent.",
        1050,
    )
    b += [
        box(32, 136, 976, 482, "#ffffff", "#d4deee"),
        text(52, 171, "Calculated model comparison", 22, weight="bold"),
        line(52, 199, 90, 199, CORAL, 3, "7 5"),
        text(100, 204, "Wrong mapping: raw cm as %", 15, CORAL, "bold"),
        line(491, 199, 529, 199, TEAL, 4),
        text(539, 204, "Calibrated: usable volume / capacity", 15, TEAL, "bold"),
        text(104, 228, "Tank level (%)", 13, MUTED, "bold"),
        text(904, 228, f"Full tank at {full_cm:.3f} cm", 13, TEAL, "bold", "end"),
        f'<rect x="{left}" y="{top}" width="{px(OFFSET_CM) - left:.3f}" '
        f'height="{height}" fill="#edf1f7"/>',
    ]
    for percent in (0, 25, 50, 75, 100, 120):
        y = py(percent)
        b += [
            line(left, y, left + width, y, "#dbe3ef", 1),
            text(left - 16, y + 5, percent, 13, MUTED, anchor="end"),
        ]
    for cm in (0, 18, 40, 60, 80, 100, 120):
        x = px(cm)
        b += [
            line(x, top, x, top + height, "#e6edf6", 1),
            text(x, top + height + 24, cm, 13, MUTED, anchor="middle"),
        ]
    b += [
        line(px(full_cm), py(0), px(full_cm), py(100), TEAL, 1.5, "3 5"),
        line(px(0), py(0), px(120), py(120), CORAL, 3, "7 5"),
    ]
    points = [(px(cm), py(calibrated_percent(cm))) for cm in (0, OFFSET_CM, full_cm, 120)]
    coords = " ".join(f"{x:.3f},{y:.3f}" for x, y in points)
    b += [
        f'<polyline points="{coords}" fill="none" stroke="{TEAL}" stroke-width="4"/>',
        line(px(SNAPSHOT_CM), py(0), px(SNAPSHOT_CM), py(SNAPSHOT_CM), "#92641d", 1.5, "3 4"),
        f'<circle cx="{px(SNAPSHOT_CM):.3f}" cy="{py(SNAPSHOT_CM):.3f}" '
        f'r="6" fill="{CORAL}" stroke="#ffffff" stroke-width="2"/>',
        f'<circle cx="{px(SNAPSHOT_CM):.3f}" cy="{py(sample_pct):.3f}" '
        f'r="7" fill="{TEAL}" stroke="#ffffff" stroke-width="2"/>',
        text(px(SNAPSHOT_CM) - 180, py(SNAPSHOT_CM) - 30, "49.0% wrong mapping", 14, CORAL, "bold"),
        text(
            px(SNAPSHOT_CM) + 15,
            py(sample_pct) + 24,
            f"{sample_pct:.1f}% calibrated",
            14,
            TEAL,
            "bold",
        ),
        text(px(9), py(95), "offset", 12, MUTED, anchor="middle"),
        text(px(SNAPSHOT_CM), top + height + 25, "49", 14, "#82520e", "bold", "middle"),
        text(504, 564, "Primary sensor reading (cm)", 15, MUTED, anchor="middle"),
        text(
            52,
            593,
            "Model: 387 L capacity · 18 cm empty offset · 35.56 cm radius · "
            "output bounded to 0-100%",
            14,
        ),
        box(32, 642, 976, 311, "#ffffff", "#acd7c8"),
        text(52, 674, "SAVED READ-ONLY OBSERVATION", 12, TEAL, "bold"),
        text(52, 708, "2026-10-16 03:13:49 UTC", 25, weight="bold"),
        text(988, 705, "SNAPSHOT · NOT LIVE", 13, CORAL, "bold", "end"),
    ]
    results = [
        (52, "PRIMARY READING", "49", "cm", BLUE, "#e7f0ff"),
        (370, "D-BUS LEVEL", "31.8", "%", TEAL, "#e1f5ed"),
        (688, "D-BUS REMAINING", "123", "L", PURPLE, "#eee9fc"),
    ]
    for x, caption, value, unit, color, fill in results:
        b += [
            box(x, 730, 300, 102, fill, fill),
            text(x + 18, 755, caption, 12, color, "bold"),
            text(x + 18, 808, value, 45, color, "bold"),
            text(x + 275, 806, unit, 23, color, "bold", "end"),
        ]
    b += [
        text(52, 862, "Connected: 1", 16, TEAL, "bold"),
        text(232, 862, "Pump: 1", 16, BLUE, "bold"),
        text(375, 862, "Valve: 0", 16, PURPLE, "bold"),
        text(518, 862, "Automatic: false", 16, CORAL, "bold"),
        text(756, 862, "Heartbeat age: 0.98 s", 16, weight="bold"),
        text(52, 895, f"Observed version: {SNAPSHOT_VERSION}", 15, MUTED),
        text(
            52,
            926,
            "123 L is the reported 0.123 m³, rounded for publication; "
            "the model at 49 cm is 123.15 L.",
            14,
            MUTED,
        ),
        text(
            32,
            986,
            "The curves are mathematical; the old mapping is a counterfactual, "
            "not an earlier measurement.",
            14,
            MUTED,
        ),
        text(
            32,
            1012,
            "The saved snapshot is software telemetry. "
            "Physical valve position and water level were not verified.",
            14,
            MUTED,
        ),
        text(
            32,
            1037,
            "No live connection · no actuator test · "
            "timestamp applies only to the recorded observation above.",
            14,
            MUTED,
        ),
    ]
    return svg(
        "Calibrated tank result and timestamped software observation",
        "Mathematical comparison, not a measured time series: the incorrect old mapping uses raw "
        "centimeters as percent. The calibrated vertical-cylinder model uses 387 L capacity, "
        "18 cm empty offset and 35.56 cm radius, bounded to 0-100 percent. "
        "At 49 cm the model gives "
        f"{sample_pct:.2f} percent. Separately, the saved read-only observation at {SNAPSHOT_AT} "
        f"from version {SNAPSHOT_VERSION} reported 49 cm, D-Bus level 31.8 percent, remaining "
        "0.123 cubic meters or 123 L, connected 1, pump 1, valve 0, automatic control false, "
        "and heartbeat age 0.98 seconds. This snapshot is not live and does not verify physical "
        "valve position or water level.",
        b,
        height=1050,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify output without writing")
    args = parser.parse_args()
    diagrams = {
        "architecture.svg": architecture(),
        "calibration.svg": calibration(),
        "hysteresis.svg": hysteresis(),
        "measurement-process.svg": measurement_process(),
        "measured-result.svg": measured_result(),
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
    print("SVG diagrams are current" if args.check else f"Generated {len(diagrams)} SVG diagrams")


if __name__ == "__main__":
    main()
