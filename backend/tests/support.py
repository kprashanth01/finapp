"""Keep pre-auth financial behavior tests focused on their original assertions.

Dedicated auth/private-data tests exercise real anonymous and cross-account calls.
"""

from fastapi.testclient import TestClient


TEST_PASSWORD = "a secure passphrase 123"


class AuthenticatedTestClient(TestClient):
    def __init__(self, app):
        super().__init__(app, base_url="http://127.0.0.1")
        self.headers.update({"X-FinApp-Request": "1"})

    def post(self, url, *args, **kwargs):
        if url == "/users" and isinstance(kwargs.get("json"), dict):
            kwargs["json"] = {"password": TEST_PASSWORD, **kwargs["json"]}
        return super().post(url, *args, **kwargs)

    def sign_in(self, email):
        return self.post("/auth/login", json={"email": email, "password": TEST_PASSWORD})
