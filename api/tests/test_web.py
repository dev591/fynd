import importlib
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def served(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>CROSSOVER-SPA</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    monkeypatch.setenv("WEB_DIST", str(tmp_path))
    sys.modules.pop("app.main", None)
    mod = importlib.import_module("app.main")
    yield TestClient(mod.app)
    sys.modules.pop("app.main", None)
    importlib.import_module("app.main")


def test_site_is_served_and_client_routes_fall_back_to_index(served):
    assert "CROSSOVER-SPA" in served.get("/").text
    assert "CROSSOVER-SPA" in served.get("/app/compare/rfq_1").text and "CROSSOVER-SPA" in served.get("/share/shr_x").text
    assert served.get("/assets/app.js").text == "console.log(1)" and served.get("/favicon.svg").text == "<svg/>"


def test_api_paths_never_fall_back_to_the_site(served):
    r = served.get("/api/nope")
    assert r.status_code == 404 and "CROSSOVER-SPA" not in r.text
    assert served.get("/health").status_code == 200


def test_files_outside_the_site_folder_are_not_served(served):
    for attempt in ("/../../../../etc/passwd", "/..%2f..%2f..%2fetc/passwd", "/%2e%2e/%2e%2e/etc/passwd"):
        assert "root:" not in served.get(attempt).text, attempt
