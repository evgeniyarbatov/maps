import unittest
from unittest import mock

import requests

from scripts.ollama_client import ensure_model, generate_json


class EnsureModelTests(unittest.TestCase):
    def test_no_pull_when_model_already_installed(self) -> None:
        tags_response = mock.Mock()
        tags_response.json.return_value = {"models": [{"name": "mistral-nemo:latest"}]}

        with (
            mock.patch("scripts.ollama_client.requests.get", return_value=tags_response) as get,
            mock.patch("scripts.ollama_client.requests.post") as post,
        ):
            ensure_model("mistral-nemo")

        get.assert_called_once()
        post.assert_not_called()

    def test_pulls_when_model_missing(self) -> None:
        tags_response = mock.Mock()
        tags_response.json.return_value = {"models": []}
        pull_response = mock.Mock()

        with (
            mock.patch("scripts.ollama_client.requests.get", return_value=tags_response),
            mock.patch("scripts.ollama_client.requests.post", return_value=pull_response) as post,
        ):
            ensure_model("llama3")

        post.assert_called_once()
        _, kwargs = post.call_args
        self.assertEqual(kwargs["json"]["name"], "llama3")

    def test_raises_when_tags_request_fails(self) -> None:
        tags_response = mock.Mock()
        tags_response.raise_for_status.side_effect = requests.HTTPError("boom")

        with (
            mock.patch("scripts.ollama_client.requests.get", return_value=tags_response),
            self.assertRaises(requests.HTTPError),
        ):
            ensure_model("mistral-nemo")


class GenerateJsonTests(unittest.TestCase):
    def test_parses_valid_json_response(self) -> None:
        response = mock.Mock()
        response.json.return_value = {"response": '{"valid": true, "reason": "ok"}'}

        with mock.patch("scripts.ollama_client.requests.post", return_value=response):
            result = generate_json("prompt")

        self.assertEqual(result, {"valid": True, "reason": "ok"})

    def test_returns_error_dict_on_unparseable_json(self) -> None:
        response = mock.Mock()
        response.json.return_value = {"response": "not json"}

        with mock.patch("scripts.ollama_client.requests.post", return_value=response):
            result = generate_json("prompt")

        self.assertIn("error", result)

    def test_passes_model_and_temperature_to_request(self) -> None:
        response = mock.Mock()
        response.json.return_value = {"response": "{}"}

        with mock.patch("scripts.ollama_client.requests.post", return_value=response) as post:
            generate_json("prompt", model="llama3", temperature=0.5)

        _, kwargs = post.call_args
        self.assertEqual(kwargs["json"]["model"], "llama3")
        self.assertEqual(kwargs["json"]["options"]["temperature"], 0.5)


if __name__ == "__main__":
    unittest.main()
