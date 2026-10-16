# Maintaining and publishing the wiki

The canonical, reviewable wiki source lives in this directory. Start at
[Home](Home.md). It uses repository-relative links so source pages and images
also work before publication. `publish.py` exports a prepared wiki tree; it does
not clone, commit, push, delete remote content or change GitHub settings.

## Prepare a reviewed export

After the documentation revision exists on GitHub, use its immutable commit SHA
as `--ref`. That pins source-code links and diagrams to the documented revision.
Run from the main repository with a separate checkout of the GitHub wiki:

```sh
git clone git@github.com:victron-venus/dbus-pump.wiki.git ../dbus-pump.wiki
python3 docs/wiki/publish.py --destination ../dbus-pump.wiki --ref <published-commit-sha>
git -C ../dbus-pump.wiki diff --check
git -C ../dbus-pump.wiki diff
```

The exporter changes sibling page links to wiki page URLs and repository links
or SVG images to GitHub blob/raw URLs at the supplied revision. It writes only
the maintained page filenames, `_Sidebar.md` and `_Footer.md`; other wiki pages
are preserved. Review any previously maintained pages that need retirement
separately. If the wiki has not been initialized, enable it and create its first
page in GitHub before cloning; do not describe an export as a live publication.

After reviewing the prepared diff, publish with the normal authorized Git
workflow. A successful local export is not evidence of a successful push.

## Keep code, documents and translations aligned

When changing source units, geometry, control ownership, installation paths or
locale behavior, update the operator guide, the four root READMEs and these wiki
summaries together. Run the SVG regeneration check. Keep evidence documents
explicitly dated and do not invent deployment, reboot or physical-actuation tests.
