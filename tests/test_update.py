"""Exercise the real installer in a temporary Venus filesystem layout."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


def device_paths(text, root):
    """Redirect literal Venus roots in every executable fixture, not just update.sh."""
    text = re.sub(r"""(?<=[\s"'=])/data(?=/|\b)""", str(root / "data"), text)
    text = re.sub(r"""(?<=[\s"'=])/service(?=/|\b)""", str(root / "service"), text)
    return text.replace("/opt/victronenergy/", str(root / "opt") + "/")


@pytest.fixture(name="venus")
def venus_layout_fixture(tmp_path):
    """Create isolated device roots and record supervisor commands."""
    repo = Path(__file__).resolve().parents[1]
    name = "dbus-pump"  # independent of checkout/worktree directory name
    root = tmp_path / "venus"
    install = root / "data" / name
    install.mkdir(parents=True)
    (root / "service").mkdir()
    (root / "data" / "rc.local").write_text("#!/bin/sh\nexit 0\n")
    script = (repo / "update.sh").read_text()
    runtime = re.search(r'^RUNTIME_ITEMS="([^"]+)"', script, re.MULTILINE).group(1).split()
    script = device_paths(script, root)
    commands = tmp_path / "bin"
    commands.mkdir()
    stubs = {
        "svc": (
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "$SVC_LOG"\n'
            'if [ "$1" = -d ] && [ "${FAIL_STOP:-0}" = 1 ]; then\n'
            '  printf "supervisor control unavailable\\n" >&2; exit 1\n'
            "fi\n"
            'if [ "$1" = -u ]; then\n'
            '  count=$(cat "$UP_COUNT_FILE" 2>/dev/null || printf 0)\n'
            '  count=$((count + 1)); printf "%s\\n" "$count" > "$UP_COUNT_FILE"\n'
            '  [ "${ALWAYS_FAIL_UP:-0}" != 1 ] || exit 1\n'
            '  [ "$count" -gt "${FAIL_UP_COUNT:-0}" ] || exit 1\n'
            "fi\nexit 0\n"
        ),
        "sleep": (
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "$SLEEP_LOG"\n'
            'count=$(cat "$SLEEP_COUNT_FILE" 2>/dev/null || printf 0)\n'
            'count=$((count + 1)); printf "%s\\n" "$count" > "$SLEEP_COUNT_FILE"\n'
            'if [ "${CREATE_SERVICE_PARENT_AFTER:-0}" -gt 0 ] && '
            '[ "$count" -eq "$CREATE_SERVICE_PARENT_AFTER" ]; then\n'
            '  mkdir -p "$TEST_SERVICE_PARENT"\n'
            "fi\nexit 0\n"
        ),
        "python3": "#!/bin/sh\nexit 0\n",
        "svstat": (
            '#!/bin/sh\nif [ "${STAY_UP:-0}" = 1 ]; then\n'
            'printf "%s: up (pid 123) 10 seconds\\n" "$1"\n'
            'else printf "%s: down 0 seconds\\n" "$1"; fi\n'
        ),
    }
    for command, body in stubs.items():
        stub = commands / command
        stub.write_text(body)
        stub.chmod(0o755)
    if shutil.which("gsed"):
        (commands / "sed").symlink_to(shutil.which("gsed"))
    calls = tmp_path / "svc-calls"
    environment = dict(
        os.environ,
        PATH=str(commands) + os.pathsep + os.environ["PATH"],
        SVC_LOG=str(calls),
        UP_COUNT_FILE=str(tmp_path / "up-count"),
        SLEEP_LOG=str(tmp_path / "sleeps"),
        SLEEP_COUNT_FILE=str(tmp_path / "sleep-count"),
        TEST_SERVICE_PARENT=str(root / "service"),
    )
    layout = SimpleNamespace(
        repo=repo,
        name=name,
        root=root,
        install=install,
        runtime=runtime,
        script=script,
        env=environment,
        calls=calls,
        service=install / "service" / name,
        link=root / "service" / "dbus-pump-ha",
        legacy=root / "service" / name,
    )
    copy_payload(layout, install)
    layout.config = install / ("config.json" if name == "dbus-emporia-vue" else "local_config.py")
    layout.config.write_text("device-local configuration must survive\n")
    return layout


def copy_payload(layout, destination):
    """Copy tracked runtime inputs and redirect only literal device roots."""
    destination.mkdir(parents=True, exist_ok=True)
    for item in [*layout.runtime, "services"]:
        source = layout.repo / item
        if not source.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, destination / item)
        else:
            shutil.copy2(source, destination / item)
            if item in ("boot.sh", "setup"):
                (destination / item).write_text(device_paths(source.read_text(), layout.root))
    (destination / "update.sh").write_text(layout.script)


def install_existing_service(layout, *, legacy=False):
    """Model existing service directories and live supervisor state."""
    shutil.copytree(layout.install / "services" / layout.name, layout.service)
    (layout.legacy if legacy else layout.link).symlink_to(layout.service)
    for directory in (layout.service, layout.service / "log"):
        (directory / "supervise").mkdir()
        (directory / "supervise" / "status").write_bytes(b"live supervisor state")
        directory.chmod(0o751)


def run_update(layout, source=None):
    """Run the real installer without invoking actual device commands."""
    source = source or layout.install
    return subprocess.run(
        ["sh", str(source / "update.sh"), str(layout.install)],
        cwd=layout.install,
        env=layout.env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )


def run_boot(layout, action="boot"):
    """Execute the installed helper with only sandboxed paths and service stubs."""
    return subprocess.run(
        ["sh", str(layout.install / "boot.sh"), action],
        cwd=layout.install,
        env=layout.env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def recorded_calls(layout):
    return layout.calls.read_text().splitlines() if layout.calls.exists() else []


def native_firmware_service(layout):
    """Create an unrelated firmware service and disabled marker under its real name."""
    layout.legacy.mkdir()
    (layout.legacy / "log").mkdir()
    (layout.legacy / "down").write_text("native service stays disabled\n")
    (layout.legacy / "run").write_text("native firmware service\n")
    firmware = layout.root / "opt" / layout.name
    firmware.mkdir(parents=True)
    (firmware / "keep").write_text("firmware payload\n")
    return {
        layout.legacy: layout.legacy.lstat(),
        layout.legacy / "down": (layout.legacy / "down").lstat(),
        layout.legacy / "run": (layout.legacy / "run").lstat(),
        firmware: firmware.lstat(),
        firmware / "keep": (firmware / "keep").lstat(),
    }


def assert_directory_metadata(before):
    """Check directory and symlink inode, ownership and permissions."""
    for path, original in before.items():
        current = path.lstat()
        assert (current.st_ino, current.st_uid, current.st_gid, current.st_mode) == (
            original.st_ino,
            original.st_uid,
            original.st_gid,
            original.st_mode,
        )


def test_repeated_in_place_updates_preserve_live_supervisors_and_boot(venus):
    """Retain directory handles, metadata and unrelated files across updates."""
    install_existing_service(venus)
    stale = venus.install / "inverter_control"
    has_stale_package = 'STALE_TOP_LEVEL="main.py inverter_control"' in venus.script
    if has_stale_package:
        stale.mkdir()
        (stale / "obsolete.py").write_text("old package")
    untouched = venus.install / "operator-backup"
    untouched.mkdir()
    (untouched / "keep").write_text("operator data")
    paths = [venus.service, venus.service / "log", venus.link]
    before = {path: path.lstat() for path in paths}
    descriptors = [os.open(path, os.O_RDONLY) for path in paths[:2]]
    try:
        for _ in range(2):
            result = run_update(venus)
            assert result.returncode == 0, result.stdout + result.stderr
            assert venus.config.read_text() == "device-local configuration must survive\n"
            assert (untouched / "keep").read_text() == "operator data"
            if has_stale_package:
                assert not stale.exists()
            assert_directory_metadata(before)
            for descriptor, directory in zip(descriptors, paths[:2], strict=True):
                assert os.fstat(descriptor).st_ino == directory.stat().st_ino
                assert (directory / "supervise" / "status").read_bytes() == b"live supervisor state"
            boot = (venus.root / "data" / "rc.local").read_text()
            marker = f"# === {venus.name} service persistence ==="
            assert boot.count(marker) == 1
            assert boot.index(marker) < boot.index("exit 0")
            assert f"sh {venus.install}/boot.sh" in boot
            assert venus.link.resolve() == venus.service
            for item in venus.runtime:
                if (venus.repo / item).exists():
                    assert (venus.install / item).exists(), item
            # The installed package uses service/, even without services/.
            shutil.rmtree(venus.install / "services", ignore_errors=True)
    finally:
        for descriptor in descriptors:
            os.close(descriptor)
    calls = venus.calls.read_text().splitlines()
    assert calls == [
        f"-d {venus.link}",
        f"-u {venus.link}/log",
        f"-u {venus.link}",
        f"-d {venus.link}",
        f"-u {venus.link}/log",
        f"-u {venus.link}",
    ]


def test_release_update_replaces_run_files_atomically(venus, tmp_path):
    """Open old run files remain intact while their paths receive new content."""
    install_existing_service(venus)
    release = tmp_path / "release"
    copy_payload(venus, release)
    for relative in ("run", "log/run"):
        (venus.service / relative).write_text("old running script\n")
    with (venus.service / "run").open() as worker, (venus.service / "log/run").open() as logger:
        result = run_update(venus, release)
        assert result.returncode == 0, result.stdout + result.stderr
        for opened, relative in ((worker, "run"), (logger, "log/run")):
            current = venus.service / relative
            assert opened.read() == "old running script\n"
            assert os.fstat(opened.fileno()).st_ino != current.stat().st_ino
            assert (
                current.read_bytes() == (release / "services" / venus.name / relative).read_bytes()
            )
            assert current.stat().st_mode & 0o111
    calls = recorded_calls(venus)
    assert f"-d {venus.link}" in calls
    assert f"-d {venus.link}/log" in calls


def test_first_install_creates_service_without_touching_other_services(venus):
    """A first install starts only the two owned service paths."""
    result = run_update(venus)
    assert result.returncode == 0, result.stdout + result.stderr
    assert venus.link.is_symlink()
    assert venus.link.resolve() == venus.service
    assert venus.calls.read_text().splitlines() == [f"-u {venus.link}/log", f"-u {venus.link}"]


@pytest.mark.parametrize("existing", ["valid", "missing", "directory"])
def test_boot_hook_only_creates_a_missing_canonical_link(venus, existing):
    """Boot replay preserves existing links and refuses foreign directories."""
    result = run_update(venus)
    assert result.returncode == 0, result.stdout + result.stderr
    inode = venus.link.lstat().st_ino
    if existing != "valid":
        venus.link.unlink()
    if existing == "directory":
        venus.link.mkdir()
        (venus.link / "keep").write_text("foreign service")
    venus.calls.write_text("")
    boot = venus.root / "data" / "rc.local"
    result = subprocess.run(
        ["sh", str(boot)],
        env=venus.env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if existing == "directory":
        # rc.local may deliberately continue to its final exit 0; the helper
        # itself must reject the conflict and never control that directory.
        assert run_boot(venus).returncode != 0
        assert not venus.link.is_symlink()
        assert (venus.link / "keep").read_text() == "foreign service"
        assert not venus.calls.read_text()
    else:
        assert result.returncode == 0, result.stderr
        assert venus.link.is_symlink()
        assert venus.link.resolve() == venus.service
        if existing == "valid":
            assert venus.link.lstat().st_ino == inode
        assert venus.calls.read_text().splitlines() == [f"-u {venus.link}/log", f"-u {venus.link}"]


@pytest.mark.parametrize(
    "layout", ["directory", "foreign_link", "service_link", "target_link", "legacy_link"]
)
def test_unexpected_layout_is_rejected_before_stopping_or_replacing(venus, tmp_path, layout):
    """Reject conflicting layouts without stopping or modifying any service."""
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    sentinel = foreign / "keep"
    sentinel.write_text("do not touch")
    if layout == "directory":
        venus.link.mkdir()
    elif layout == "foreign_link":
        venus.link.symlink_to(foreign)
    elif layout == "service_link":
        (venus.install / "service").symlink_to(foreign)
    elif layout == "target_link":
        venus.service.parent.mkdir()
        venus.service.symlink_to(foreign)
    else:
        venus.legacy.symlink_to(foreign)
    before = (venus.install / "version").read_bytes()
    result = run_update(venus)
    assert result.returncode != 0
    assert not venus.calls.exists()
    assert sentinel.read_text() == "do not touch"
    assert (venus.install / "version").read_bytes() == before


def test_missing_service_definition_is_rejected_before_stop(venus):
    """A partial release must not take down the installed application."""
    (venus.install / "services" / venus.name / "log" / "run").unlink()
    result = run_update(venus)
    assert result.returncode != 0
    assert "Missing service definition" in result.stderr
    assert not venus.calls.exists()


def test_native_firmware_service_and_payload_survive_install_and_boot(venus):
    before = native_firmware_service(venus)
    result = run_update(venus)
    assert result.returncode == 0, result.stdout + result.stderr
    assert venus.link.resolve() == venus.service
    assert_directory_metadata(before)
    assert (venus.legacy / "down").read_text() == "native service stays disabled\n"
    assert (venus.legacy / "run").read_text() == "native firmware service\n"
    result = run_boot(venus)
    assert result.returncode == 0, result.stdout + result.stderr
    assert_directory_metadata(before)
    assert all(str(venus.legacy) not in call.split()[1:] for call in recorded_calls(venus))


def test_owned_legacy_alias_migrates_without_replacing_live_directory_handles(venus):
    install_existing_service(venus, legacy=True)
    legacy_inode = venus.legacy.lstat().st_ino
    before = {path: path.lstat() for path in (venus.service, venus.service / "log")}
    descriptor = os.open(venus.service, os.O_RDONLY)
    try:
        result = run_update(venus)
        assert result.returncode == 0, result.stdout + result.stderr
        assert os.fstat(descriptor).st_ino == venus.service.stat().st_ino
    finally:
        os.close(descriptor)
    assert_directory_metadata(before)
    assert not venus.legacy.exists()
    assert not venus.legacy.is_symlink()
    assert venus.link.lstat().st_ino == legacy_inode
    assert venus.link.resolve() == venus.service
    # A positively identified legacy alias can safely stop the owned worker
    # before the exact symlink is moved to its collision-free final name.
    assert recorded_calls(venus)[0] in (f"-d {venus.link}", f"-d {venus.legacy}")


def test_boot_deduplicates_only_an_exact_owned_legacy_alias(venus):
    install_existing_service(venus)
    venus.legacy.symlink_to(venus.service)
    inode = venus.link.lstat().st_ino
    result = run_boot(venus)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not venus.legacy.exists()
    assert not venus.legacy.is_symlink()
    assert venus.link.lstat().st_ino == inode


def test_boot_waits_for_service_parent_without_creating_global_root(venus):
    install_existing_service(venus)
    venus.link.unlink()
    venus.link.parent.rmdir()
    venus.env["CREATE_SERVICE_PARENT_AFTER"] = "3"
    result = run_boot(venus)
    assert result.returncode == 0, result.stdout + result.stderr
    assert venus.link.resolve() == venus.service
    assert int(Path(venus.env["SLEEP_COUNT_FILE"]).read_text()) >= 3
    assert recorded_calls(venus) == [f"-u {venus.link}/log", f"-u {venus.link}"]


def test_boot_missing_service_parent_fails_after_a_bounded_wait(venus):
    install_existing_service(venus)
    venus.link.unlink()
    venus.link.parent.rmdir()
    result = run_boot(venus)
    assert result.returncode != 0
    assert not venus.link.parent.exists()
    assert not recorded_calls(venus)
    assert 1 <= len(Path(venus.env["SLEEP_LOG"]).read_text().splitlines()) <= 20
    assert result.stderr.strip() or result.stdout.strip()


def test_boot_retries_transient_supervisor_failures_and_clears_owned_down_flags(venus):
    install_existing_service(venus)
    for path in (venus.service, venus.service / "log"):
        (path / "down").write_text("owned stop marker\n")
    venus.env["FAIL_UP_COUNT"] = "3"
    result = run_boot(venus)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (venus.service / "down").exists()
    assert not (venus.service / "log" / "down").exists()
    calls = recorded_calls(venus)
    assert len(calls) > 3
    assert set(calls) == {f"-u {venus.link}/log", f"-u {venus.link}"}
    assert calls[-1] == f"-u {venus.link}"
    assert len(calls) <= 40


def test_boot_permanent_supervisor_failure_is_bounded_and_reported(venus):
    install_existing_service(venus)
    venus.env["ALWAYS_FAIL_UP"] = "1"
    result = run_boot(venus)
    assert result.returncode != 0
    calls = recorded_calls(venus)
    assert 1 <= len(calls) <= 40
    assert set(calls) <= {f"-u {venus.link}/log", f"-u {venus.link}"}
    assert 1 <= len(Path(venus.env["SLEEP_LOG"]).read_text().splitlines()) <= 20
    assert result.stderr.strip() or result.stdout.strip()


def test_uninstall_removes_owned_alias_but_preserves_native_firmware(venus):
    install_existing_service(venus)
    before = native_firmware_service(venus)
    result = run_boot(venus, "uninstall")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not venus.link.exists()
    assert not venus.link.is_symlink()
    assert_directory_metadata(before)
    assert (venus.legacy / "down").read_text() == "native service stays disabled\n"
    assert venus.config.read_text() == "device-local configuration must survive\n"
    calls = recorded_calls(venus)
    assert calls
    assert all(
        path in {str(venus.link), str(venus.link / "log")}
        for call in calls
        for path in call.split()[1:]
    )


def test_uninstall_refuses_foreign_alias_without_service_commands(venus, tmp_path):
    foreign = tmp_path / "foreign-service"
    foreign.mkdir()
    (foreign / "keep").write_text("foreign data\n")
    venus.link.symlink_to(foreign)
    result = run_boot(venus, "uninstall")
    assert result.returncode != 0
    assert venus.link.resolve() == foreign
    assert (foreign / "keep").read_text() == "foreign data\n"
    assert not recorded_calls(venus)


def test_uninstall_missing_supervisor_control_preserves_owned_and_native_links(venus):
    """A missing control FIFO cannot prove that the owned worker has stopped."""
    install_existing_service(venus)
    before = native_firmware_service(venus)
    before[venus.link] = venus.link.lstat()
    venus.env["FAIL_STOP"] = "1"
    result = run_boot(venus, "uninstall")
    assert result.returncode != 0
    assert "supervisor control unavailable" in result.stderr
    assert_directory_metadata(before)
    assert venus.link.resolve() == venus.service
    assert (venus.legacy / "down").read_text() == "native service stays disabled\n"
    assert recorded_calls(venus) == [f"-d {venus.link}"]


def test_stuck_worker_aborts_without_replacing_runtime_or_logger(venus):
    """Never replace live runtime files after a worker fails to terminate."""
    install_existing_service(venus)
    venus.env["STAY_UP"] = "1"
    before = (venus.install / "update.sh").stat().st_ino
    result = run_update(venus)
    assert result.returncode != 0
    assert "runtime files were not changed" in result.stderr
    assert (venus.install / "update.sh").stat().st_ino == before
    assert venus.calls.read_text().splitlines() == [f"-d {venus.link}", f"-k {venus.link}"]


def test_missing_dependencies_fail_before_install_changes(tmp_path):
    """Missing interpreter dependencies stop the update before mutations."""
    repo = Path(__file__).resolve().parents[1]
    commands = tmp_path / "bin"
    commands.mkdir()
    interpreter = commands / "python3"
    interpreter.write_text("#!/bin/sh\nexit 42\n")
    interpreter.chmod(0o755)
    script = (repo / "update.sh").read_text()
    script = script.split("# Stage the release before stopping anything.")[0]
    script += '\nprintf "unexpected continuation"\n'
    result = subprocess.run(
        ["sh", "-c", script],
        cwd=tmp_path,
        env=dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"]),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 42
    assert "unexpected continuation" not in result.stdout
