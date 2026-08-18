from app.github.demo_loader import load_demo_snapshot


def test_demo_snapshot_collects_expected_categories():
    snapshot = load_demo_snapshot()

    assert len(snapshot.dockerfiles) == 1
    assert len(snapshot.workflows) == 1
    assert any(f.path == "requirements.txt" for f in snapshot.dependency_files)
    assert any(f.path == "docker-compose.yml" for f in snapshot.config_files)
    assert any(f.path.endswith(".py") for f in snapshot.source_samples)
