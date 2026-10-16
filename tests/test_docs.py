"""Documentation artifacts remain linkable and safe to export without network writes."""

import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_helper(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def diagrams():
    return load_helper("diagram_generator", "docs/assets/generate.py")


@pytest.fixture
def wiki():
    return load_helper("wiki_exporter", "docs/wiki/publish.py")


def test_operator_documentation_links_resolve():
    files = [
        *ROOT.glob("README*.md"),
        ROOT / "docs/architecture.md",
        *ROOT.glob("docs/operator/*.md"),
        *ROOT.glob("docs/wiki/*.md"),
        ROOT / "docs/assets/README.md",
    ]
    for document in files:
        for target in re.findall(r"!?\[[^\]]*\]\(([^)\s]+)\)", document.read_text()):
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            path = document.parent / target.split("#", 1)[0]
            assert path.exists(), f"Broken link in {document}: {target}"


def test_diagrams_are_accessible_and_have_calibration_units(diagrams):
    for build in (
        diagrams.architecture,
        diagrams.calibration,
        diagrams.hysteresis,
        diagrams.measurement_process,
        diagrams.measured_result,
    ):
        source = build()
        parsed = ET.fromstring(source)
        ns = "{http://www.w3.org/2000/svg}"
        assert parsed.get("role") == "img"
        assert parsed.find(f"{ns}title").text
        assert parsed.find(f"{ns}desc").text
        assert parsed.find(f"{ns}script") is None
        assert parsed.get("viewBox")
        for element in parsed.iter():
            assert element.tag.split("}")[-1] not in ("script", "foreignObject", "image")
            for name, value in element.attrib.items():
                assert not name.lower().startswith("on")
                if name.split("}")[-1] == "href":
                    assert value.startswith("#"), "Diagrams must not fetch remote resources"
    calibration = diagrams.calibration()
    for expected in ("297.94", "76.99", "115.418", "Level (%)", "Volume (L)"):
        assert expected in calibration
    assert "not measured data" in calibration


def test_process_diagram_separates_telemetry_ownership_and_read_only_preview(diagrams):
    process = diagrams.measurement_process()
    for expected in (
        "Home Assistant",
        "Validate",
        "Normalize",
        "Native D-Bus",
        "Display",
        "CONTROL OWNERSHIP",
        "Bridge automatic control = disabled",
        "READ-ONLY DRY-RUN",
        "No native D-Bus connection or registration.",
        "No actuator commands. No service heartbeat.",
        "not a live status",
    ):
        assert expected in process


def test_result_distinguishes_mathematical_model_from_saved_observation(diagrams):
    assert diagrams.calibrated_percent(18) == 0
    assert diagrams.calibrated_percent(49) == pytest.approx(31.82, abs=0.005)
    assert diagrams.calibrated_percent(93) == pytest.approx(76.99, abs=0.005)
    assert diagrams.calibrated_percent(120) == 100
    result = diagrams.measured_result()
    for expected in (
        "Wrong mapping: raw cm as %",
        "Calibrated: usable volume / capacity",
        "SAVED READ-ONLY OBSERVATION",
        "2026-10-16T03:13:49Z",
        "SNAPSHOT · NOT LIVE",
        "49.0% wrong mapping",
        "31.8% calibrated",
        "123 L",
        "0.123 m³",
        "0.1.7+units.2c5045f",
        "Heartbeat age: 0.98 s",
        "Automatic: false",
        "Connected: 1",
        "Pump: 1",
        "Valve: 0",
        "counterfactual, not an earlier measurement",
        "Physical valve position and water level were not verified.",
    ):
        assert expected in result


def test_diagram_check_detects_drift_without_overwriting(diagrams, tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "OUT", tmp_path)
    monkeypatch.setattr("sys.argv", ["generate.py"])
    diagrams.main()
    expected = {p.name: p.read_bytes() for p in tmp_path.glob("*.svg")}
    assert set(expected) == {
        "architecture.svg",
        "calibration.svg",
        "hysteresis.svg",
        "measurement-process.svg",
        "measured-result.svg",
    }
    monkeypatch.setattr("sys.argv", ["generate.py", "--check"])
    diagrams.main()
    stale = tmp_path / "calibration.svg"
    stale.write_text("outdated")
    with pytest.raises(SystemExit) as error:
        diagrams.main()
    assert error.value.code == 1
    assert stale.read_text() == "outdated"
    stale.unlink()
    with pytest.raises(SystemExit):
        diagrams.main()
    monkeypatch.setattr("sys.argv", ["generate.py"])
    diagrams.main()
    assert {p.name: p.read_bytes() for p in tmp_path.glob("*.svg")} == expected


def test_wiki_export_uses_pinned_source_links_and_preserves_external_urls(wiki):
    sha = "a" * 40
    source = (
        "[Install](Installation.md) [Config](../operator/configuration.md#tank-geometry) "
        "![Curve](../assets/calibration.svg) [Publish](README.md) "
        "[External](https://example.com) [Section](#heading) [Email](mailto:test@example.com)"
    )
    result = wiki.export_text(source, sha)
    assert "https://github.com/victron-venus/dbus-pump/wiki/Installation" in result
    assert f"/blob/{sha}/docs/operator/configuration.md#tank-geometry" in result
    assert f"raw.githubusercontent.com/victron-venus/dbus-pump/{sha}/docs/assets/" in result
    assert f"/blob/{sha}/docs/wiki/README.md" in result
    assert "[External](https://example.com)" in result
    assert "[Section](#heading)" in result
    assert "[Email](mailto:test@example.com)" in result


@pytest.mark.parametrize("target", ["missing.md", "../../../../outside.md"])
def test_wiki_export_rejects_missing_or_escaping_source(wiki, target):
    with pytest.raises(ValueError, match="does not resolve"):
        wiki.export_text(f"[Invalid]({target})", "a" * 40)


def test_wiki_export_preserves_unowned_pages_and_needs_immutable_ref(wiki, tmp_path, monkeypatch):
    existing = tmp_path / "Other-page.md"
    existing.write_text("Do not replace another author's page")
    monkeypatch.setattr(
        "sys.argv",
        ["publish.py", "--destination", str(tmp_path), "--ref", "B" * 40],
    )
    wiki.main()
    assert existing.read_text() == "Do not replace another author's page"
    assert (tmp_path / "Home.md").is_file()
    assert (tmp_path / "_Sidebar.md").is_file()
    assert "/blob/" + "b" * 40 in (tmp_path / "Home.md").read_text()
    monkeypatch.setattr("sys.argv", ["publish.py", "--destination", str(tmp_path), "--ref", "main"])
    with pytest.raises(SystemExit) as error:
        wiki.main()
    assert error.value.code == 2


@pytest.mark.parametrize("relative", [".", "docs/wiki", "docs/wiki/export"])
def test_wiki_export_cannot_overwrite_source(wiki, relative, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["publish.py", "--destination", str(ROOT / relative), "--ref", "a" * 40],
    )
    with pytest.raises(SystemExit) as error:
        wiki.main()
    assert error.value.code == 2
