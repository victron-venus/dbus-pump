# Documentation

A Venus OS D-Bus service that drives a water pump from Home Assistant sensors,
with a tank calibration model and an operator guide.

## Operator guide

- [Operator guide](operator/README.md) — the version scope and where each operator page starts.
- [Installation, updates and recovery](operator/installation.md) — installing and updating the service on the GX device.
- [Configuration and interfaces](operator/configuration.md) — the settings and the interfaces they expose.
- [Sensor units and tank calibration](operator/calibration.md) — converting a reading into a tank level.
- [Control ownership and failure behavior](operator/control.md) — who owns the pump state and what happens on failure.
- [Process and results](operator/process-and-results.md) — a worked path from a Home Assistant reading to a verified tank display.
- [Localization and translation guide](operator/localization.md) — the supported languages and how to add one.
- [Troubleshooting and acceptance checks](operator/troubleshooting.md) — the checks to run when the display disagrees.

## Wiki source

- [dbus-pump wiki](wiki/Home.md) — the wiki home page as tracked in this repository.
- [Maintaining and publishing the wiki](wiki/README.md) — the canonical source lives here; this page explains publishing.
- [Installation](wiki/Installation.md) — the wiki installation page.
- [Configuration](wiki/Configuration.md) — the wiki configuration page.
- [Calibration](wiki/Calibration.md) — the wiki calibration page.
- [Control and safety](wiki/Control-and-safety.md) — the wiki control and safety page.
- [Measurement process and recorded result](wiki/Process-and-results.md) — the wiki version of the process page.
- [Troubleshooting](wiki/Troubleshooting.md) — the wiki troubleshooting page.
- [Localization](wiki/Localization.md) — the wiki localization page.
- [Maintained with the dbus-pump source](wiki/_Footer.md) — the shared wiki footer text.
- [dbus-pump](wiki/_Sidebar.md) — the wiki navigation sidebar.

## Design

- [Architecture and trust boundaries](architecture.md) — what the configuration layer loads and where trust ends.
- [dbus-pump deployment notes](DEPLOYMENT-NOTES.md) — findings from the first bring-up in August 2026.
- [Documentation diagrams](assets/README.md) — the diagram assets used across the guide.

## Assurance

- [Quality evidence and reproducibility](quality-evidence.md) — the testing rules new functionality and fixes must meet.
- [Security assurance argument](security-assurance.md) — the integrity and availability goal for the service.
- [Static analysis review](STATIC_ANALYSIS.md) — the dated review that retains every finding.
- [Reproducing the maintained-source coverage bound](evidence/coverage-scope-method.md) — inventorying reviewed source without executing it.
- [OpenSSF Best Practices evidence: dbus-pump](openssf-evidence.md) — the index behind the Passing assessment.

## Releases

- [Release operations](release-packaging.md) — what `release.sh` delegates and which events validate what.
- [Signed stable release and target acceptance](release-acceptance.md) — the stable baseline and its acceptance.
- [Staged native installation](staged-installation.md) — capturing the declared native payload without a Venus device.
- [Verify a signed release](release-signatures.md) — checking a signed artefact.
- [Release version inputs](release-versioning.md) — the `versioning` fields that identify a release.
- [CI and release operations](release-workflow.md) — `.release-policy.json` and the required status.
- [CI orchestration](CI-ORCHESTRATION.md) — how the quality gate and release pipeline divide the events.
- [Version plans and manifest synchronization](VERSIONING.md) — the versioning opt-in.
- [Release-candidate fuzz testing](fuzzing.md) — the illustrated RC fuzzing process.
- [Fuzzing release candidates](rc-fuzzing.md) — the reusable bounded fuzz workflow.
- [Release read recovery and rerun validation](release-read-safety.md) — the two fixes carried from the shared toolkit.
- [Early final-build runner check](runner-preflight.md) — why the check runs before the final build.
