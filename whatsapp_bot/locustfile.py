"""
Load test for the WhatsApp bot Cloud Run service.

Usage:
    pip install locust
    locust -f whatsapp_bot/locustfile.py --host=https://YOUR-CLOUD-RUN-URL

Then open http://localhost:8089 to start the test and watch live metrics.

Or headless (no UI):
    locust -f whatsapp_bot/locustfile.py --host=https://YOUR-CLOUD-RUN-URL \
        --headless --users=20 --spawn-rate=2 --run-time=60s
"""

from locust import HttpUser, task, between
import random
import string

# Simulated conversation messages in rough order a real user might send.
# Cycle through these per-user to mimic a realistic conversation flow.
CONVERSATION_FLOW = [
    "Hello",
    "SurveyMode2025Demo",           # joining an event
    "John",               # name response
    "34",                 # age response
    "Male",               # gender response
    "Nairobi",            # region response
    "I think the proposed policy will have a big impact on local farmers.",
    "The government should provide more support for smallholder farmers.",
    "Access to credit is also a major barrier for rural communities.",
    "We need better infrastructure to connect farmers to markets.",
    "Climate variability is making things much harder than before.",
]


def random_phone() -> str:
    """Generate a fake but realistic-looking WhatsApp phone number."""
    return "whatsapp:+1" + "".join(random.choices(string.digits, k=10))


class WhatsAppUser(HttpUser):
    """Simulates a single WhatsApp user sending messages over time."""

    wait_time = between(1, 5)  # seconds between tasks (adjust to simulate think time)

    def on_start(self):
        # Each simulated user gets a stable unique phone number for the session
        self.phone = random_phone()
        self._step = 0

    @task(10)
    def send_text_message(self):
        """Primary task: send a text message (weighted 10x)."""
        body = CONVERSATION_FLOW[self._step % len(CONVERSATION_FLOW)]
        self._step += 1

        with self.client.post(
            "/message",
            data={"Body": body, "From": self.phone},
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}: {resp.text[:200]}")

    @task(1)
    def health_check(self):
        """Lightweight sanity check that the service is up (weighted 1x)."""
        with self.client.get("/health", catch_response=True) as resp:
            if resp.status_code in (200, 404):
                # 404 is fine — there's no /health route, but it proves the server responds
                resp.success()
            else:
                resp.failure(f"Health check got {resp.status_code}")
