"""Capture the native package under DESTDIR without activating device services.

Use a private staging directory with no concurrent writers. This installer never
contacts a device, installs dependencies, creates service links or changes boot.
"""

import argparse
import json
import os
import shutil
from pathlib import Path

PACKAGE = "dbus-pump"
PAYLOAD = (
    ".python-version",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "LICENSE",
    "README.de.md",
    "README.md",
    "README.nl.md",
    "README.ru.md",
    "RELEASING.md",
    "ROADMAP.md",
    "SECURITY.md",
    "boot.sh",
    "dbus_pump/__init__.py",
    "dbus_pump/__main__.py",
    "dbus_pump/config.py",
    "dbus_pump/control.py",
    "dbus_pump/ha_client.py",
    "dbus_pump/i18n.py",
    "dbus_pump/main.py",
    "dbus_pump/service.py",
    "dbus_pump/tank.py",
    "dbus_pump/worker.py",
    "docs/CI-ORCHESTRATION.md",
    "docs/DEPLOYMENT-NOTES.md",
    "docs/STATIC_ANALYSIS.md",
    "docs/VERSIONING.md",
    "docs/architecture.md",
    "docs/assets/README.md",
    "docs/assets/architecture.svg",
    "docs/assets/calibration.svg",
    "docs/assets/generate.py",
    "docs/assets/hysteresis.svg",
    "docs/evidence/bandit-review-2026-10-12.json",
    "docs/evidence/coverage-scope-2026-10-12.json",
    "docs/evidence/coverage-scope-method.md",
    "docs/evidence/defect-level-review-2026-10-12.json",
    "docs/evidence/low-uptime-regression-2026-10-12.json",
    "docs/evidence/native-archive-repeatability-2026-10-12.json",
    "docs/evidence/python-coverage-2026-10-12.json",
    "docs/evidence/python-package-build-2026-10-12.json",
    "docs/evidence/regression-history-2026-10-12.json",
    "docs/evidence/service-regression-replay-2026-10-12.json",
    "docs/fuzzing.md",
    "docs/openssf-evidence.md",
    "docs/operator/README.md",
    "docs/operator/calibration.md",
    "docs/operator/configuration.md",
    "docs/operator/control.md",
    "docs/operator/installation.md",
    "docs/operator/localization.md",
    "docs/operator/troubleshooting.md",
    "docs/quality-evidence.md",
    "docs/rc-fuzzing.md",
    "docs/release-acceptance.md",
    "docs/release-packaging.md",
    "docs/release-signatures.md",
    "docs/release-versioning.md",
    "docs/release-workflow.md",
    "docs/runner-preflight.md",
    "docs/security-assurance.md",
    "docs/staged-installation.md",
    "docs/wiki/Calibration.md",
    "docs/wiki/Configuration.md",
    "docs/wiki/Control-and-safety.md",
    "docs/wiki/Home.md",
    "docs/wiki/Installation.md",
    "docs/wiki/Localization.md",
    "docs/wiki/README.md",
    "docs/wiki/Troubleshooting.md",
    "docs/wiki/_Footer.md",
    "docs/wiki/_Sidebar.md",
    "docs/wiki/publish.py",
    "gitHubInfo",
    "install.py",
    "local_config.example.py",
    "pyproject.toml",
    "restart.sh",
    "services/dbus-pump/log/run",
    "services/dbus-pump/run",
    "setup",
    "update.sh",
    "uv.lock",
    "version",
)
MANIFEST = ".installed-files.json"


def reject_links(path: Path) -> None:
    """Reject links and special files before touching a staging path."""
    for component in (*reversed(path.parents), path):
        if component.is_symlink():
            raise ValueError(f"Staging paths must not contain symlinks: {component}")
        if component != path and component.exists() and not component.is_dir():
            raise ValueError(f"Parent staging paths must be directories: {component}")
        if component.exists() and not component.is_dir():
            if not component.is_file() or component.stat().st_nlink > 1:
                raise ValueError(f"Staging paths must be regular, unlinked files: {component}")


def package_path(destdir: str) -> Path:
    """Require a staging root, never the live filesystem root."""
    if not destdir:
        raise ValueError("DESTDIR must select a non-root staging directory")
    root = Path(os.path.abspath(destdir))
    if root == Path(root.anchor):
        raise ValueError("DESTDIR must not be the live filesystem root")
    package = root / "data" / PACKAGE
    reject_links(package)
    return package


def stage(source: Path, destdir: str) -> None:
    """Copy declared release files, excluding credentials and operator settings."""
    package = package_path(destdir)
    # Complete validation before the first write: missing inputs must not leave
    # a partial package or overwrite a previous valid installation.
    for name in PAYLOAD:
        path = source / name
        reject_links(path)
        if not path.is_file():
            raise ValueError(f"Missing regular package input: {name}")
    for name in (*PAYLOAD, MANIFEST):
        target = package / name
        reject_links(target)
        if target.is_dir():
            raise ValueError(f"Package file is occupied by a directory: {name}")
    for name in PAYLOAD:
        source_path, target = source / name, package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        target.chmod(0o755 if source_path.stat().st_mode & 0o111 else 0o644)
    manifest = package / MANIFEST
    manifest.write_text(json.dumps(list(PAYLOAD), indent=2) + "\n")
    manifest.chmod(0o644)


def unstage(destdir: str) -> None:
    """Remove only manifest-owned files, retaining operator-added files."""
    package = package_path(destdir)
    manifest = package / MANIFEST
    reject_links(manifest)
    names = json.loads(manifest.read_text())
    if not isinstance(names, list) or not all(
        isinstance(name, str) and name in PAYLOAD for name in names
    ):
        raise ValueError("Invalid staged installation manifest")
    for name in names:
        target = package / name
        reject_links(target)
        if target.is_dir():
            raise ValueError(f"Package file is occupied by a directory: {name}")
    for name in names:
        (package / name).unlink(missing_ok=True)
    manifest.unlink()
    directories = {package}
    for name in names:
        parent = (package / name).parent
        while parent != package:
            directories.add(parent)
            parent = parent.parent
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


def main() -> None:
    """Provide equivalent environment-variable and command-line staging APIs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"), nargs="?", default="install")
    parser.add_argument("--destdir", default=os.environ.get("DESTDIR", ""))
    args = parser.parse_args()
    if args.action == "install":
        stage(Path(__file__).resolve().parent, args.destdir)
    else:
        unstage(args.destdir)


if __name__ == "__main__":
    main()
