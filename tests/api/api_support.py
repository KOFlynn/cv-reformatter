"""The key every API test's app expects (``conftest`` sets ``CVR_API_KEY`` to
it) and the header that sends it."""

API_KEY = "test-api-key-0123456789"
AUTH = {"X-API-Key": API_KEY}
