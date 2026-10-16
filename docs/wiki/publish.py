#!/usr/bin/env python3
"""Export reviewed wiki Markdown locally; never commit, push, or contact GitHub."""

import argparse
import re
from pathlib import Path
from urllib.parse import quote

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[1]
REPOSITORY_URL = "https://github.com/victron-venus/dbus-pump"
PAGES = (
    "Home.md",
    "Installation.md",
    "Configuration.md",
    "Calibration.md",
    "Control-and-safety.md",
    "Troubleshooting.md",
    "Localization.md",
    "_Sidebar.md",
    "_Footer.md",
)
LINK = re.compile(r"(?P<prefix>!?\[[^\]]*\]\()(?P<target>[^)\s]+)(?P<suffix>\))")


def export_text(content: str, revision: str) -> str:
    def rewrite(match):
        target = match.group("target")
        if target.startswith(("https://", "http://", "#", "mailto:")):
            return match.group(0)
        relative, separator, fragment = target.partition("#")
        path = (SOURCE / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f"Wiki source link does not resolve within the repository: {target}")
        if path.parent == SOURCE and path.name in PAGES:
            url = f"{REPOSITORY_URL}/wiki/{quote(path.stem)}"
        else:
            repository_path = quote(path.relative_to(ROOT).as_posix())
            if match.group("prefix").startswith("!["):
                url = (
                    f"https://raw.githubusercontent.com/victron-venus/dbus-pump/"
                    f"{revision}/{repository_path}"
                )
            else:
                url = f"{REPOSITORY_URL}/blob/{revision}/{repository_path}"
        if separator:
            url += "#" + fragment
        return match.group("prefix") + url + match.group("suffix")

    return LINK.sub(rewrite, content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--ref", required=True, help="published immutable 40-character Git SHA")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", args.ref):
        parser.error("--ref must be the published revision's full 40-character Git SHA")
    destination = args.destination.resolve()
    if destination == ROOT or destination.is_relative_to(SOURCE):
        parser.error("destination must not replace the project root or wiki sources")
    # Resolve every page first so invalid source links cannot leave a partial export.
    pages = {
        name: export_text((SOURCE / name).read_text(encoding="utf-8"), args.ref.lower())
        for name in PAGES
    }
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in pages.items():
        (destination / name).write_text(content, encoding="utf-8")
    print(f"Exported {len(pages)} pages to {destination}; no commit or push performed")


if __name__ == "__main__":
    main()
