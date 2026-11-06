import json
import unittest

import handler


class HealthHandlerTests(unittest.TestCase):
    def test_health_endpoint_returns_healthy(self):
        response = handler.lambda_handler({}, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            response["headers"]["Content-Type"],
            "application/json",
        )

        body = json.loads(response["body"])
        self.assertEqual(body, {"status": "healthy"})


if __name__ == "__main__":
    unittest.main()
