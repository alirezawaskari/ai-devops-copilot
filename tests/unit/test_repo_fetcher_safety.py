from app.github.repo_fetcher import categorize_path, is_path_safe


def test_rejects_path_traversal():
    assert is_path_safe("../../etc/passwd") is False
    assert is_path_safe("/etc/passwd") is False


def test_rejects_secret_like_files():
    assert is_path_safe(".env") is False
    assert is_path_safe("secrets/id_rsa") is False
    assert is_path_safe("certs/server.pem") is False


def test_rejects_excluded_directories():
    assert is_path_safe("node_modules/lodash/index.js") is False
    assert is_path_safe("vendor/lib/thing.go") is False


def test_accepts_normal_source_file():
    assert is_path_safe("app/main.py") is True


def test_categorizes_known_file_types():
    assert categorize_path("Dockerfile") == "dockerfile"
    assert categorize_path("backend/Dockerfile.prod") == "dockerfile"
    assert categorize_path(".github/workflows/ci.yml") == "workflow"
    assert categorize_path("requirements.txt") == "dependency"
    assert categorize_path("docker-compose.yml") == "config"
    assert categorize_path("app/main.py") == "source"
    assert categorize_path("README.md") is None
