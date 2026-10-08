"""Contract and pipeline tests for Jev without external API calls."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import yaml

from config import load_config
from pipeline.jev_client import API_URL, JevClient
from pipeline.llm_factory import create_llm_client, create_ranking_client
from pipeline.ranking_stage import load_retry_papers, rank_papers
from pipeline.summary_stage import generate_summaries, select_top_papers
from tools.models import Paper
from tools.test_scoring import TestCase, score_test_cases


def paper(paper_id: str) -> Paper:
    return Paper(paper_id, "Paper title", ["Author"], "Abstract", "test", "https://example.com", None)


def response(*scores: float) -> Mock:
    result = Mock()
    result.json.return_value = {
        "answers": {f"paper_{i}": {"type": "score", "score": score} for i, score in enumerate(scores)}
    }
    return result


class JevTests(unittest.TestCase):
    """Verify wire format, score bounds, retries, and stage integration."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        data = yaml.safe_load(Path("config.example.yaml").read_text())
        data["llm"].update(ranking_provider="jev", mock_mode=True, max_retries=2, retry_delay=0)
        data["output"]["cache_dir"] = self.temp.name
        config_path = Path(self.temp.name) / "config.yaml"
        config_path.write_text(yaml.safe_dump(data))
        self.config = load_config(str(config_path))

    @patch("pipeline.jev_client.requests.post")
    def test_request_and_fractional_score_conversion(self, post: Mock) -> None:
        post.return_value = response(0, 2.75, 4)
        client = JevClient(api_key="test-key", timeout=7)
        self.assertEqual(
            client.score_papers([paper("a"), paper("b"), paper("c")], "My rubric"), {"a": 1.0, "b": 3.75, "c": 5.0}
        )
        args, kwargs = post.call_args
        self.assertEqual(args, (API_URL,))
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer test-key"})
        self.assertEqual(kwargs["timeout"], 7)
        body = kwargs["json"]
        self.assertEqual(body["state"]["relevance_spec"], "My rubric")
        self.assertEqual(body["state"]["papers"]["paper_1"]["id"], "b")
        self.assertEqual(body["model"], "jev-latest")
        self.assertEqual(len(body["questions"]), 3)
        self.assertEqual(len(body["questions"]["paper_0"]["criteria"]), 5)
        self.assertEqual(body["questions"]["paper_0"]["type"], "score")

    @patch("pipeline.jev_client.requests.post")
    def test_invalid_or_missing_answers_fail(self, post: Mock) -> None:
        client = JevClient(api_key="test-key", max_retries=1)
        for score in [-1, 5, float("nan"), float("inf"), True, "2"]:
            with self.subTest(score=score):
                post.return_value = response(score)
                with self.assertRaises(ValueError):
                    client.score_papers([paper("a")], "rubric")
        post.return_value = response()
        with self.assertRaises(KeyError):
            client.score_papers([paper("a")], "rubric")

    @patch("pipeline.jev_client.requests.post")
    def test_transient_failure_retried(self, post: Mock) -> None:
        post.side_effect = [requests.Timeout(), response(4)]
        client = JevClient(api_key="test-key", max_retries=2, retry_delay=0)
        self.assertEqual(client.score_papers([paper("a")], "rubric"), {"a": 5})
        self.assertEqual(post.call_count, 2)

    def test_factory_keeps_summary_provider(self) -> None:
        self.assertIsInstance(create_ranking_client(self.config), JevClient)
        self.assertNotIsInstance(create_llm_client(self.config), JevClient)
        self.config.llm.ranking_provider = "llm"
        self.assertNotIsInstance(create_ranking_client(self.config), JevClient)

    @patch("pipeline.jev_client.requests.post")
    def test_batch_failure_persisted_and_recovered(self, post: Mock) -> None:
        self.config.llm.batch_size = 1
        post.side_effect = [response(1), requests.Timeout()]
        client = JevClient(api_key="test-key", max_retries=1)
        ranked = rank_papers([paper("a"), paper("b")], self.config, client)
        self.assertEqual([p.id for p in ranked], ["a"])
        self.assertEqual([p.id for p in load_retry_papers(self.temp.name)], ["b"])
        post.side_effect = None
        post.return_value = response(4)
        ranked = rank_papers([], self.config, client)
        self.assertEqual([(p.id, p.relevance_score) for p in ranked], [("b", 5)])
        self.assertEqual(load_retry_papers(self.temp.name), [])

    @patch("pipeline.jev_client.requests.post")
    def test_mock_evaluation_without_api(self, post: Mock) -> None:
        actual = score_test_cases(
            [TestCase("a", "Title", "Abstract", 3)], self.config, create_ranking_client(self.config)
        )
        self.assertEqual(actual, {"a": 3.0})
        post.assert_not_called()

    def test_missing_credentials(self) -> None:
        with self.assertRaisesRegex(ValueError, "TYPESAFE_API_KEY"):
            JevClient()

    @patch("pipeline.jev_client.requests.post")
    def test_sort_selection_and_summary_provider(self, post: Mock) -> None:
        post.return_value = response(1, 3.5, 2.25)
        client = JevClient(api_key="test-key", max_retries=1)
        ranked = rank_papers([paper("a"), paper("b"), paper("c")], self.config, client)
        self.assertEqual([p.id for p in ranked], ["b", "c", "a"])
        self.config.output.top_n = 1
        self.config.output.score_threshold = 4
        selected = select_top_papers(ranked, self.config)
        self.assertEqual([p.id for p in selected], ["b"])
        summaries = generate_summaries(selected, create_llm_client(self.config))
        self.assertTrue(summaries[0].summary)
        self.assertEqual(post.call_count, 1)

    def test_existing_config_defaults_to_llm(self) -> None:
        data = yaml.safe_load(Path("config.example.yaml").read_text())
        del data["llm"]["ranking_provider"]
        del data["llm"]["jev"]
        config_path = Path(self.temp.name) / "legacy.yaml"
        config_path.write_text(yaml.safe_dump(data))
        self.assertEqual(load_config(str(config_path)).llm.ranking_provider, "llm")

    @patch.dict("os.environ", {"TYPESAFE_API_KEY": "environment-key"})
    def test_environment_key_precedence(self) -> None:
        data = yaml.safe_load(Path("config.example.yaml").read_text())
        data["llm"]["jev"]["api_key"] = "config-key"
        config_path = Path(self.temp.name) / "keys.yaml"
        config_path.write_text(yaml.safe_dump(data))
        self.assertEqual(load_config(str(config_path)).llm.jev.api_key, "environment-key")


if __name__ == "__main__":
    unittest.main()
