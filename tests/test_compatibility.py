from pathlib import Path

import pytest
import yaml
from astrbot.core.star import star_manager


@pytest.mark.parametrize("version", ["4.29.1", "4.29.4"])
def test_supported_astrbot_versions_pass_loader_check(monkeypatch, version):
    metadata = yaml.safe_load((Path(__file__).resolve().parents[1] / "metadata.yaml").read_text())
    monkeypatch.setattr(star_manager, "VERSION", version)
    supported, error = star_manager.PluginManager._validate_astrbot_version_specifier(
        metadata["astrbot_version"]
    )
    assert supported, error
