"""
Context enrichment for conversation threads.

Fetches thread history from Slack threads and GitHub PRs to provide
context for the agent when processing follow-up messages.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


async def fetch_slack_thread_context(
    bot_token: str,
    channel_id: str,
    thread_ts: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Fetch messages from a Slack thread.

    Args:
        bot_token: Slack bot token (xoxb-...)
        channel_id: Channel ID
        thread_ts: Thread timestamp (parent message ts)
        limit: Maximum number of messages to fetch

    Returns:
        List of messages with user, text, and timestamp
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://slack.com/api/conversations.replies",
                headers={"Authorization": f"Bearer {bot_token}"},
                params={
                    "channel": channel_id,
                    "ts": thread_ts,
                    "limit": limit,
                },
            )

            data = response.json()

            if not data.get("ok"):
                logger.warning(
                    "slack_thread_fetch_failed",
                    error=data.get("error"),
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                )
                return []

            messages = []
            for msg in data.get("messages", []):
                messages.append(
                    {
                        "user_id": msg.get("user", "unknown"),
                        "text": msg.get("text", ""),
                        "ts": msg.get("ts", ""),
                        "bot_id": msg.get("bot_id"),  # Present if message is from a bot
                    }
                )

            logger.info(
                "slack_thread_context_fetched",
                channel_id=channel_id,
                thread_ts=thread_ts,
                message_count=len(messages),
            )
            return messages

    except Exception as e:
        logger.error(
            "slack_thread_fetch_error",
            error=str(e),
            channel_id=channel_id,
            thread_ts=thread_ts,
        )
        return []


async def fetch_github_pr_comments(
    token: str,
    repo: str,
    pr_number: int,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Fetch comments from a GitHub pull request.

    Args:
        token: GitHub token (installation token or PAT)
        repo: Repository in format "owner/repo"
        pr_number: Pull request number
        limit: Maximum number of comments to fetch

    Returns:
        List of comments with author, body, and timestamp
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get issue comments (general PR comments)
            response = await client.get(
                f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                params={"per_page": limit},
            )

            if response.status_code != 200:
                logger.warning(
                    "github_pr_comments_fetch_failed",
                    status=response.status_code,
                    repo=repo,
                    pr_number=pr_number,
                )
                return []

            comments = []
            for comment in response.json():
                comments.append(
                    {
                        "author": comment.get("user", {}).get("login", "unknown"),
                        "body": comment.get("body", ""),
                        "created_at": comment.get("created_at", ""),
                        "id": comment.get("id"),
                    }
                )

            logger.info(
                "github_pr_context_fetched",
                repo=repo,
                pr_number=pr_number,
                comment_count=len(comments),
            )
            return comments

    except Exception as e:
        logger.error(
            "github_pr_comments_fetch_error",
            error=str(e),
            repo=repo,
            pr_number=pr_number,
        )
        return []


def format_slack_thread_context(
    messages: List[Dict[str, Any]],
    current_message_ts: str,
    bot_user_id: Optional[str] = None,
) -> Optional[str]:
    """
    Format Slack thread messages as context for the agent.

    Only includes messages AFTER the agent's last response in the thread.
    This avoids duplicating context that's already in the OpenAI conversation history.

    Filters out:
    - Messages before the agent's last response
    - The current message (the one triggering the agent)
    - Bot messages (identified by bot_id field)

    Args:
        messages: List of thread messages from fetch_slack_thread_context
        current_message_ts: Timestamp of the current message (to exclude)
        bot_user_id: Bot's user ID to filter out its own messages

    Returns:
        Formatted context string, or None if no relevant messages
    """
    # First, find the timestamp of the last bot message (agent's last response)
    last_bot_message_ts = "0"
    for msg in messages:
        if msg.get("bot_id"):
            msg_ts = msg.get("ts", "0")
            if float(msg_ts) > float(last_bot_message_ts):
                last_bot_message_ts = msg_ts

    relevant_messages = []

    for msg in messages:
        msg_ts = msg.get("ts", "0")

        # Skip the current triggering message
        if msg_ts == current_message_ts:
            continue

        # Skip messages from bots (they have bot_id field)
        if msg.get("bot_id"):
            continue

        # Skip bot's own messages if bot_user_id is provided
        if bot_user_id and msg.get("user_id") == bot_user_id:
            continue

        # Only include messages AFTER the last bot response
        # This avoids duplicating context already in OpenAI conversation history
        if float(msg_ts) <= float(last_bot_message_ts):
            continue

        text = msg.get("text", "").strip()
        if not text:
            continue

        # Format timestamp for human readability
        try:
            ts_float = float(msg_ts)
            dt = datetime.fromtimestamp(ts_float)
            time_str = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            time_str = "??:??"

        user_id = msg.get("user_id", "unknown")
        relevant_messages.append(f"[{time_str}] <@{user_id}>: {text}")

    if not relevant_messages:
        return None

    context = "<thread_context>\n"
    context += "Messages in this thread since my last response:\n\n"
    context += "\n".join(relevant_messages)
    context += "\n</thread_context>\n\n"

    return context


def format_github_pr_context(
    comments: List[Dict[str, Any]],
    bot_username: Optional[str] = None,
) -> Optional[str]:
    """
    Format GitHub PR comments as context for the agent.

    Only includes comments AFTER the agent's last comment on the PR.
    This avoids duplicating context that's already in the OpenAI conversation history.

    Args:
        comments: List of PR comments from fetch_github_pr_comments
        bot_username: Bot's GitHub username to filter out its own comments

    Returns:
        Formatted context string, or None if no relevant comments
    """
    # First, find the timestamp of the last bot comment (agent's last response)
    last_bot_comment_time = ""
    for comment in comments:
        author = comment.get("author", "")
        # Check if this is a bot comment
        is_bot = (
            (bot_username and author.lower() == bot_username.lower())
            or author.endswith("[bot]")
            or author.startswith("github-actions")
            or "incidentfox" in author.lower()
        )
        if is_bot:
            created_at = comment.get("created_at", "")
            if created_at > last_bot_comment_time:
                last_bot_comment_time = created_at

    relevant_comments = []

    for comment in comments:
        author = comment.get("author", "unknown")
        created_at = comment.get("created_at", "")

        # Skip bot's own comments if bot_username provided
        if bot_username and author.lower() == bot_username.lower():
            continue

        # Skip bot comments (common patterns)
        if author.endswith("[bot]") or author.startswith("github-actions"):
            continue

        # Only include comments AFTER the last bot response
        if last_bot_comment_time and created_at <= last_bot_comment_time:
            continue

        body = comment.get("body", "").strip()
        if not body:
            continue

        # Format timestamp
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            time_str = "????-??-??"

        # Truncate very long comments
        if len(body) > 500:
            body = body[:500] + "..."

        relevant_comments.append(f"[{time_str}] @{author}:\n{body}")

    if not relevant_comments:
        return None

    context = "<pr_context>\n"
    context += "Comments on this PR since my last response:\n\n"
    context += "\n\n".join(relevant_comments)
    context += "\n</pr_context>\n\n"

    return context


def build_enriched_message(
    context: Optional[str],
    current_message: str,
) -> str:
    """
    Combine thread context with the current message.

    Args:
        context: Formatted context string (or None)
        current_message: The current message that triggered the agent

    Returns:
        Enriched message with context prepended
    """
    if not context:
        return current_message

    return f"{context}<current_message>\n{current_message}\n</current_message>"
