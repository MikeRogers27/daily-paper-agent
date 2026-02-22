import time
from datetime import date
from typing import Any

import requests

from config import Config
from tools.models import Paper


class SlackNotifier:
    """Handles posting papers to Slack via webhook."""

    def __init__(self, webhook_url: str, channel: str | None = None):
        self.webhook_url = webhook_url
        self.channel = channel

    def format_paper_message(self, paper: Paper, report_date: date) -> dict[str, Any]:
        """Format a paper as Slack blocks."""
        # Score emoji
        score = paper.relevance_score or 0
        if score >= 5:
            emoji = "⭐"
        elif score >= 4:
            emoji = "🔥"
        else:
            emoji = "📄"

        # Authors
        authors_str = ", ".join(paper.authors[:3]) if paper.authors else "Unknown"
        if paper.authors and len(paper.authors) > 3:
            authors_str += " et al."

        # Build message text
        text = f"*{emoji} {paper.title}* (Score: {score:.1f})\n"
        text += f"*Authors:* {authors_str}\n\n"
        if paper.summary:
            text += f"_{paper.summary}_"

        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Paper"},
                    "url": paper.url,
                },
            },
            {"type": "divider"},
        ]

        return {"blocks": blocks}

    def post_paper(self, paper: Paper, report_date: date) -> bool:
        """Post a single paper to Slack. Returns True on success."""
        try:
            message = self.format_paper_message(paper, report_date)

            if self.channel:
                message["channel"] = self.channel

            response = requests.post(self.webhook_url, json=message, timeout=10)

            if response.status_code == 200:
                return True
            else:
                print(f"Slack API error: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"Network error posting to Slack: {e}")
            return False
        except Exception as e:
            print(f"Error posting to Slack: {e}")
            return False

    def post_papers(self, papers: list[Paper], report_date: date) -> dict[str, Any]:
        """Post multiple papers to Slack with rate limiting. Returns stats."""
        stats = {"posted": 0, "failed": 0, "skipped": 0}

        if not papers:
            return stats

        # Add header message
        header = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📚 Daily Papers - {report_date.isoformat()}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Found *{len(papers)}* highly relevant papers today!",
                    },
                },
                {"type": "divider"},
            ]
        }

        if self.channel:
            header["channel"] = self.channel  # type: ignore

        try:
            requests.post(self.webhook_url, json=header, timeout=10)
            time.sleep(1)  # Rate limit
        except Exception as e:
            print(f"Error posting header: {e}")

        # Post each paper
        for paper in papers:
            success = self.post_paper(paper, report_date)
            if success:
                stats["posted"] += 1
            else:
                stats["failed"] += 1

            # Rate limiting: 1 message per second
            time.sleep(1)

        return stats


def notify_slack(papers: list[Paper], report_date: date, config: Config) -> dict[str, Any]:
    """
    Send high-scoring papers to Slack.

    Args:
        papers: List of papers with summaries
        report_date: Date of the report
        config: Configuration with Slack settings

    Returns:
        Dict with stats: posted, failed, skipped counts
    """
    stats = {"posted": 0, "failed": 0, "skipped": 0}

    # Check if Slack is enabled
    if not config.notifications or not config.notifications.slack.enabled:
        stats["skipped"] = len(papers)
        return stats

    # Check if webhook URL is configured
    if not config.notifications.slack.webhook_url:
        print("Slack enabled but no webhook URL configured")
        stats["skipped"] = len(papers)
        return stats

    # Filter papers by min_score
    min_score = config.notifications.slack.min_score
    high_score_papers = [p for p in papers if (p.relevance_score or 0) >= min_score]

    stats["skipped"] = len(papers) - len(high_score_papers)

    if not high_score_papers:
        return stats

    # Post to Slack
    notifier = SlackNotifier(
        webhook_url=config.notifications.slack.webhook_url,
        channel=config.notifications.slack.channel,
    )

    post_stats = notifier.post_papers(high_score_papers, report_date)
    stats["posted"] = post_stats["posted"]
    stats["failed"] = post_stats["failed"]

    return stats
