import json
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import local_model_client  # noqa: E402


class ResolveConfigTests(unittest.TestCase):
    def test_defaults_to_omlx_provider(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            config = local_model_client.resolve_client_config()

        self.assertEqual(config["provider"], "omlx")
        self.assertEqual(config["api_base"], "http://127.0.0.1:8000/v1")
        self.assertIsNone(config["api_key"])

    def test_cli_values_override_environment(self):
        with mock.patch.dict(
            "os.environ",
            {
                "LOCAL_LLM_PROVIDER": "ollama",
                "LOCAL_LLM_API_BASE": "http://env.example",
                "LOCAL_LLM_API_KEY": "env-key",
            },
            clear=True,
        ):
            config = local_model_client.resolve_client_config(
                provider="omlx",
                api_base="http://cli.example/v1",
                api_key="cli-key",
            )

        self.assertEqual(
            config,
            {
                "provider": "omlx",
                "api_base": "http://cli.example/v1",
                "api_key": "cli-key",
            },
        )


class GenerateTextTests(unittest.TestCase):
    def test_omlx_uses_openai_chat_completions_shape(self):
        response_body = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "translated text",
                    }
                }
            ]
        }

        response = mock.MagicMock()
        response.read.return_value = json.dumps(response_body).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        with mock.patch.object(local_model_client.request, "urlopen", return_value=response) as urlopen_mock:
            result = local_model_client.generate_text(
                "translate me",
                model="gemma-4-e4b-it-mxfp8",
                provider="omlx",
                api_base="http://127.0.0.1:8000/v1",
                api_key="secret",
                temperature=0.2,
            )

        self.assertEqual(result, "translated text")
        req = urlopen_mock.call_args.args[0]
        self.assertEqual(req.full_url, "http://127.0.0.1:8000/v1/chat/completions")
        self.assertEqual(req.get_header("Authorization"), "Bearer secret")
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["model"], "gemma-4-e4b-it-mxfp8")
        self.assertEqual(payload["messages"][0]["content"], "translate me")
        self.assertEqual(payload["temperature"], 0.2)

    def test_ollama_uses_generate_endpoint_shape(self):
        response_body = {"response": "draft text"}

        response = mock.MagicMock()
        response.read.return_value = json.dumps(response_body).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        with mock.patch.object(local_model_client.request, "urlopen", return_value=response) as urlopen_mock:
            result = local_model_client.generate_text(
                "translate me",
                model="gemma-4-e4b-it-mxfp8",
                provider="ollama",
                api_base="http://127.0.0.1:11434/api/generate",
                api_key=None,
                temperature=0.2,
            )

        self.assertEqual(result, "draft text")
        req = urlopen_mock.call_args.args[0]
        self.assertEqual(req.full_url, "http://127.0.0.1:11434/api/generate")
        self.assertIsNone(req.get_header("Authorization"))
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["model"], "gemma-4-e4b-it-mxfp8")
        self.assertEqual(payload["prompt"], "translate me")
        self.assertEqual(payload["options"]["temperature"], 0.2)


if __name__ == "__main__":
    unittest.main()
