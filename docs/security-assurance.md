# Security assurance argument

## Goal, scope and assumptions

The goal is to preserve integrity and availability of the documented dbus-pump
service under malformed telemetry, unavailable dependencies and routine updates.
The OS, configured D-Bus policy, administrator-controlled files and authenticated
Home Assistant/provider endpoints are trusted within their stated boundaries.
A compromised host or unrestricted administrator is outside this argument.
Use independent physical protections for equipment; software tests are not a
safety certification.

## Claims and evidence

- Claim: missing or stale telemetry does not become an apparently valid command.
  Argument: configuration/state validation and command reconciliation distinguish
  unavailable state, enforce bounds and preserve the stale-closed valve behavior.
  Evidence: dbus_pump/config.py, control.py, main.py and worker.py;
  tests/test_invalid_sensor.py, test_control.py and test_app_tick.py.
- Claim: network failures do not silently authorize arbitrary operations.
  Argument: production callers pass configured entities to the HA client, which
  forwards the supplied entity_id and surfaces failed operations. This trusts
  administrator-controlled entity configuration; the client does not enforce an
  entity allowlist. Evidence: dbus_pump/main.py, dbus_pump/ha_client.py and
  tests/test_ha_client.py.
- Claim: startup/update integration preserves the native Venus OS pump service.
  Evidence: tests/test_registration.py and test_update.py cover the supervised
  service/installation contract; physical hardware behavior is not inferred.

- Claim: source changes and updates remain reviewable. Argument: public history,
  contributor policy, required CI and release input manifests identify the code
  under review. Evidence: CONTRIBUTING.md, RELEASING.md, release contract tests.
  The release policy enables a separate post-build Sigstore signing job. The
  verifier authenticates the expected repository, branch and reviewed commit
  before reading the inventory, then checks all original assets and source bytes.
  Evidence: docs/release-signatures.md, scripts/release_signing.py and its negative
  contract tests. Actual published signed-release verification remains required.

## Residual obligations

Review the exact deployed TLS/credential configuration and permission model.
Re-run relevant negative tests after changing a boundary. Keep dependencies
monitored and replace compromised credentials; never claim that deleting a
credential from Git revokes it. Use SECURITY.md for coordinated disclosure.

The coverage and regression inventories support this argument only within their
declared scope. Remaining OpenSSF obligations include verified continuity,
published signed-release verification. The maintained-source coverage bound
counts shell and embedded code at zero credit, as documented in quality evidence.
The defect-level regression review now records a conservative lower bound. The 2026-10-12 review found no GitHub issue/advisory reports,
and the owner confirmed no outside-GitHub reports during the prior 12 months. Python coverage is
measured in docs/quality-evidence.md; hardware and shell coverage are not implied. No Passing or Silver award is asserted here.
