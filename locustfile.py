"""Load test: mostly scans (redirects), few creates.
Run:  locust -f locustfile.py --host http://localhost:5000 --headless -u 100 -r 10 -t 60s --csv results
"""
import random

from locust import HttpUser, between, task


class QRUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.codes = []
        for i in range(5):
            r = self.client.post("/api/create", json={"url": f"https://example.com/page/{i}"})
            if r.status_code == 201:
                self.codes.append(r.json()["code"])

    @task(10)
    def scan(self):
        if self.codes:
            # allow_redirects=False -> measure our service only, not the target site
            self.client.get(f"/r/{random.choice(self.codes)}", allow_redirects=False, name="/r/[code]")

    @task(1)
    def create(self):
        r = self.client.post("/api/create", json={"url": "https://example.com/new"})
        if r.status_code == 201:
            self.codes.append(r.json()["code"])

    @task(1)
    def health(self):
        self.client.get("/health")
