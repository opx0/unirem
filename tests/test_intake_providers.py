import json
import unittest
from unittest.mock import MagicMock, patch

from intake import providers


class IntakeProvidersTestCase(unittest.TestCase):
    def test_validate_input_text_length(self):
        with self.assertRaises(ValueError) as ctx:
            providers._validate_input_text("a" * 20001)
        self.assertIn(
            "Text exceeds the configured processing limit", str(ctx.exception)
        )

    def test_validate_and_extract_items_valid(self):
        valid_json = '{"items": [{"kind": "event", "title": "Exam"}]}'
        items = providers._validate_and_extract_items(valid_json)
        self.assertEqual(items, [{"kind": "event", "title": "Exam"}])

    def test_validate_and_extract_items_invalid_json(self):
        with self.assertRaises(ValueError) as ctx:
            providers._validate_and_extract_items("{bad json")
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_validate_and_extract_items_missing_items_key(self):
        with self.assertRaises(ValueError) as ctx:
            providers._validate_and_extract_items('{"wrong_key": []}')
        self.assertIn("expected {'items': [...]}", str(ctx.exception))

    @patch("intake.providers.urlopen")
    @patch.dict(
        "os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-2.5-flash"}
    )
    def test_gemini_success(self, mock_urlopen):
        mock_response = MagicMock()
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "items": [
                                            {
                                                "kind": "task",
                                                "title": "Submit assignment",
                                            }
                                        ]
                                    }
                                )
                            }
                        ]
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        mock_response.read.return_value = json.dumps(payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        items = providers.gemini("Notice text")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Submit assignment")

    @patch("intake.providers.urlopen")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_gemini_blocked_prompt(self, mock_urlopen):
        mock_response = MagicMock()
        payload = {"promptFeedback": {"blockReason": "SAFETY"}}
        mock_response.read.return_value = json.dumps(payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(ValueError) as ctx:
            providers.gemini("Blocked content")
        self.assertIn("Gemini blocked prompt: SAFETY", str(ctx.exception))
