from app.analyzers.config_analyzer import analyze_docker_compose, analyze_env_example
from app.github.schemas import RepoFile


def _rule_ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


def test_db_port_bound_to_all_interfaces_flagged():
    content = """
services:
  db:
    image: postgres:15
    ports:
      - "0.0.0.0:5432:5432"
"""
    findings = analyze_docker_compose(RepoFile(path="docker-compose.yml", content=content))
    assert "CONF001" in _rule_ids(findings)


def test_hardcoded_secret_flagged():
    content = """
services:
  web:
    image: myapp
    environment:
      DATABASE_PASSWORD: hunter2super
"""
    findings = analyze_docker_compose(RepoFile(path="docker-compose.yml", content=content))
    assert "CONF002" in _rule_ids(findings)


def test_interpolated_secret_not_flagged():
    content = """
services:
  web:
    image: myapp
    environment:
      DATABASE_PASSWORD: ${DATABASE_PASSWORD}
"""
    findings = analyze_docker_compose(RepoFile(path="docker-compose.yml", content=content))
    assert "CONF002" not in _rule_ids(findings)


def test_missing_restart_policy_flagged():
    content = """
services:
  web:
    image: myapp
"""
    findings = analyze_docker_compose(RepoFile(path="docker-compose.yml", content=content))
    assert "CONF004" in _rule_ids(findings)


def test_env_example_placeholder_not_flagged():
    content = "API_SECRET_KEY=changeme\n"
    findings = analyze_env_example(RepoFile(path=".env.example", content=content))
    assert "CONF003" not in _rule_ids(findings)


def test_env_example_real_looking_secret_flagged():
    content = "API_SECRET_KEY=aB3xQ9mZ7pL2vN8kT5yH1wR4sD6fG0jC9uE7iO2qA\n"
    findings = analyze_env_example(RepoFile(path=".env.example", content=content))
    assert "CONF003" in _rule_ids(findings)
