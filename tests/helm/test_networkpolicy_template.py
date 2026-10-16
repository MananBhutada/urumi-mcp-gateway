from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_mysql_ingress_is_limited_to_wordpress_and_setup_job():
    policy = (ROOT / "infrastructure/helm/urumi/templates/networkpolicy.yaml").read_text()
    wordpress = (ROOT / "infrastructure/helm/urumi/templates/wordpress.yaml").read_text()

    assert 'metadata: {name: allow-wordpress-to-mysql}' in policy
    assert 'metadata: {name: allow-wpsetup-to-mysql}' in policy
    assert 'matchLabels: {app: wp-setup}' in policy
    assert 'metadata: {name: allow-same-namespace-to-mysql}' not in policy
    assert 'metadata: {labels: {app: wp-setup}}' in wordpress


def test_egress_policies_cover_only_known_service_dependencies():
    policy = (ROOT / "infrastructure/helm/urumi/templates/networkpolicy.yaml").read_text()

    for name in ("gateway", "dashboard", "woo-mcp", "wordpress", "wp-setup", "weather-mcp", "currency-mcp"):
        assert f'"name" "{name}" "selector"' in policy
    assert '{{- range $database := list "mysql" "postgres" }}' in policy
    assert '"protocol" "UDP" "port" 53' in policy
    assert '"protocol" "TCP" "port" 53' in policy
    assert '"protocol" "TCP" "port" 3306' in policy
    assert '"protocol" "TCP" "port" 5432' in policy
    assert '"protocol" "TCP" "port" 8000' in policy
    assert '"protocol" "TCP" "port" 443' in policy
