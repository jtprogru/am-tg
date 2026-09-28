import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def test_chart_versions_match_pyproject():
    # `make bump VERSION=X.Y.Z` keeps these in sync; the release workflow checks them against the tag
    chart = yaml.safe_load((ROOT / "deploy/helm/am-tg/Chart.yaml").read_text())
    assert chart["version"] == VERSION
    assert chart["appVersion"] == VERSION


def test_readme_helm_example_matches_pyproject():
    readme = (ROOT / "README.md").read_text()
    assert re.findall(r"charts/am-tg --version (\S+)", readme) == [VERSION]
