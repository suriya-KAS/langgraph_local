from locust import HttpUser, task, between
import uuid

class ChatUser(HttpUser):
    wait_time = between(0.2, 1.0)

    @task
    def send_message(self):
        self.client.post(
            "/api/chat/message",
            json={
                "message": "Will you marry me?",
                "conversationId": "new",
                "messageType": "text",
                "context": {
                    "userId": f"user_{uuid.uuid4().hex[:8]}",
                    "username": "LoadTest",
                    "wallet_balance": 100,
                    "loginLocation": "IN",
                    "marketplaces_registered": ["Amazon"],
                    "clientInfo": {
                        "device": "desktop",
                        "appVersion": "1.0.0",
                        "timezone": "Asia/Kolkata",
                        "platform": "web",
                        "userAgent": "Locust/1.0",
                        "country": "IN"
                    }
                },
                "language": "English"
            },
        )