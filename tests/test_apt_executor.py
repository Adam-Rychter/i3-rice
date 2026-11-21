import subprocess

import pytest

from i3_rice_gui.apt_executor import (
    AptExecutionError, InstallState, execute_apt_plan,
)
from i3_rice_gui.install_catalog import AptPlan


def test_apt_executor_uses_argument_arrays_and_reports_each_package():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    result = execute_apt_plan(
        AptPlan(("i3", "rofi"), (), (), ()),
        runner=runner,
        which=lambda name: f"/usr/bin/{name}",
    )

    assert result.refreshed
    assert [operation.state for operation in result.operations] == [
        InstallState.SUCCEEDED, InstallState.SUCCEEDED,
    ]
    assert calls == [
        ["/usr/bin/pkexec", "/usr/bin/apt-get", "update"],
        ["/usr/bin/pkexec", "/usr/bin/apt-get", "install", "-y",
         "--no-install-recommends", "i3"],
        ["/usr/bin/pkexec", "/usr/bin/apt-get", "install", "-y",
         "--no-install-recommends", "rofi"],
    ]


def test_refresh_failure_skips_package_operations():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, "", "locked")

    result = execute_apt_plan(
        AptPlan(("i3",), (), (), ()),
        runner=runner,
        which=lambda name: f"/usr/bin/{name}",
    )

    assert not result.refreshed
    assert result.operations[0].state is InstallState.SKIPPED
    assert calls == [["/usr/bin/pkexec", "/usr/bin/apt-get", "update"]]


def test_package_failure_is_reported_without_hiding_other_results():
    count = 0

    def runner(command, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            return subprocess.CompletedProcess(command, 1, "", "unavailable")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    result = execute_apt_plan(
        AptPlan(("i3", "rofi"), (), (), ()),
        runner=runner,
        which=lambda name: f"/usr/bin/{name}",
    )

    assert [operation.state for operation in result.operations] == [
        InstallState.FAILED, InstallState.SUCCEEDED,
    ]


@pytest.mark.parametrize(
    "plan",
    [
        AptPlan(("bad/name",), (), (), ()),
        AptPlan(("i3",), ("st",), (), ()),
        AptPlan(("i3",), (), (), ("i3",)),
    ],
)
def test_unsafe_plans_are_rejected_before_authorization(plan):
    with pytest.raises(AptExecutionError):
        execute_apt_plan(plan, which=lambda name: f"/usr/bin/{name}")


def test_missing_pkexec_does_not_attempt_apt():
    with pytest.raises(AptExecutionError, match="pkexec"):
        execute_apt_plan(
            AptPlan(("i3",), (), (), ()),
            which=lambda name: None if name == "pkexec" else f"/usr/bin/{name}",
        )
