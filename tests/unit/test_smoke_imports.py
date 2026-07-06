import importlib


def test_key_packages_are_importable() -> None:
    package_names = [
        "mcp_server",
        "core",
        "ingestion",
        "libs",
        "observability",
    ]

    for package_name in package_names:
        assert importlib.import_module(package_name)