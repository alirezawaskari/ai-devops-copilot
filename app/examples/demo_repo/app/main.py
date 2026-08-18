import requests


def fetch_upstream_status():
    try:
        response = requests.get("https://status.example.com/health")
        return response.json()
    except:
        pass


def notify_slack(payload):
    requests.post("https://hooks.slack.com/services/xxx", json=payload)


if __name__ == "__main__":
    fetch_upstream_status()
