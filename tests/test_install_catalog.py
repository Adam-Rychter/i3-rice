from i3_rice_gui.install_catalog import (
    PackageSpec, PackageState, PackageStatus, build_apt_plan, detect_apt_packages,
)


def test_detection_uses_package_query_results():
    catalog = (
        PackageSpec("i3", "i3", "window manager"),
        PackageSpec("polybar", "polybar", "status bar"),
    )
    results = {"i3": (PackageState.INSTALLED, "install ok installed"),
               "polybar": (PackageState.MISSING, "Package is not installed")}

    statuses = detect_apt_packages(catalog, results.__getitem__)

    assert [status.state for status in statuses] == [
        PackageState.INSTALLED, PackageState.MISSING,
    ]


def test_detection_preserves_unknown_query_state():
    spec = PackageSpec("rofi", "rofi", "launcher")
    status = detect_apt_packages((spec,), lambda _: (PackageState.UNKNOWN, "query failed"))[0]

    assert status.state is PackageState.UNKNOWN
    assert status.detail == "query failed"


def test_plan_separates_missing_installed_unknown_and_unsupported():
    statuses = (
        PackageStatus(PackageSpec("i3", "i3", "window manager"), PackageState.INSTALLED),
        PackageStatus(PackageSpec("polybar", "polybar", "status bar"), PackageState.MISSING),
        PackageStatus(PackageSpec("rofi", "rofi", "launcher"), PackageState.UNKNOWN),
    )

    plan = build_apt_plan(("i3", "polybar", "rofi", "st"), statuses)

    assert plan.packages == ("polybar",)
    assert plan.already_installed == ("i3",)
    assert plan.unknown_packages == ("rofi",)
    assert plan.unsupported_components == ("st",)
