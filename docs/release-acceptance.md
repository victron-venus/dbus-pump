# Signed stable release and target acceptance

[Stable v0.1.6](https://github.com/victron-venus/dbus-pump/releases/tag/v0.1.6)
was published by [the successful promotion run](https://github.com/victron-venus/dbus-pump/actions/runs/38340663478)
from accepted `v0.1.6-rc.2`, source `b44fdb6856ab371feb5a287a28440bd7d7894f21`.

## Recipient verification

All eight published assets were downloaded and compared with the accepted RC2;
every asset was byte-identical. Cosign 3.1.3 and the reviewed source verifier
accepted the expected repository, workflow, ref, source and complete inventory
of four signed payloads. Verification with an incorrect expected source failed.
[The signature guide](release-signatures.md) documents how recipients repeat
these checks. Historical unsigned releases are not retroactively authenticated.

## Target acceptance and limits

The [exact RC2 acceptance record](https://github.com/victron-venus/dbus-pump/pull/110#issuecomment-6137372123)
describes the installed-file comparison and runtime observation on a Cerbo GX,
Venus OS v3.75, ARMv7, Python 3.12.13. Installed application files matched the
accepted release mapping; process identity and connected D-Bus services remained
stable while telemetry advanced. The unchanged stable assets preserve that
acceptance; they do not establish behavior on every firmware or configuration.

The final observation window included a recovered Home Assistant read timeout.
All three checked services reported connected at the final observation; the process
identity was unchanged.
`ENABLE_CONTROL=False` was preserved. No physical pump or valve operation,
physical valve position, or cold boot was accepted by these checks; the native
Venus OS pump service was unchanged.

These checks do not establish uninterrupted upstream availability, exercise
all failure modes, or certify physical equipment safety. Reapply the
[release policy](../RELEASING.md) to future candidates, changed dependencies,
installation procedures and supported targets. Keep recovery material until
the deployment is accepted under the operator's maintenance policy.
