#!/usr/bin/env python3
"""
IncidentFox CLI - Interactive terminal for AI-powered investigations.

Uses the Planner agent as entry point, which delegates to sub-agents:
- Investigation Agent (full toolkit, autonomous)
- K8s Agent (Kubernetes specialist)
- AWS Agent (AWS specialist)
- Metrics Agent (performance analysis)
- Coding Agent (code analysis)
"""

import asyncio
import json
import os
import sys
from typing import Optional

try:
    import click
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install click prompt-toolkit rich httpx")
    sys.exit(1)

from .client import AgentClient

console = Console()


@click.command()
@click.option("--agent", "-a", default="planner", help="Entry agent (default: planner)")
@click.option("--list-agents", is_flag=True, help="List available agents")
@click.option(
    "--agent-url",
    envvar="AGENT_URL",
    default="http://localhost:8081",
    help="Agent service URL",
)
@click.option(
    "--token",
    envvar="TEAM_TOKEN",
    default=None,
    help="Team token (or set TEAM_TOKEN env var)",
)
def main(agent: str, list_agents: bool, agent_url: str, token: Optional[str]):
    """IncidentFox AI SRE - Interactive Terminal"""

    # Get team token
    team_token = token or os.getenv("TEAM_TOKEN", "")
    if not team_token:
        console.print("[red]❌ TEAM_TOKEN not set[/red]")
        console.print("[yellow]Set TEAM_TOKEN in .env or pass --token[/yellow]")
        sys.exit(1)

    # Initialize client
    client = AgentClient(base_url=agent_url, team_token=team_token)

    # Check health
    if not client.check_health():
        console.print(f"[red]❌ Cannot connect to agent at {agent_url}[/red]")
        console.print("[yellow]Run 'make start' to start services[/yellow]")
        sys.exit(1)

    if list_agents:
        display_agents(client)
        return

    # Show welcome banner
    console.print(
        Panel.fit(
            "[bold blue]IncidentFox AI SRE[/bold blue] - Local Edition\n\n"
            f"Entry Agent: [green]{agent}[/green]\n"
            f"Connected to: [cyan]{agent_url}[/cyan]\n\n"
            "The planner agent orchestrates investigations by delegating to\n"
            "specialized sub-agents: K8s, AWS, Metrics, Coding, Investigation.\n\n"
            "Type [yellow]help[/yellow] for commands, [yellow]quit[/yellow] to exit.",
            title="🦊 IncidentFox",
        )
    )
    console.print()

    # Run REPL
    asyncio.run(run_repl(client, agent))


async def run_repl(client: AgentClient, agent_name: str):
    """Main REPL loop."""
    history_file = os.path.expanduser("~/.incidentfox_history")
    session = PromptSession(history=FileHistory(history_file))

    # Track conversation across prompts for follow-up questions
    session_response_id: str | None = None

    while True:
        try:
            # Show conversation indicator in prompt
            prompt_indicator = (
                "incidentfox" + (" (follow-up)" if session_response_id else "") + "> "
            )
            prompt = await session.prompt_async(prompt_indicator)
            prompt = prompt.strip()

            if not prompt:
                continue

            # Built-in commands
            cmd = prompt.lower()

            if cmd in ("quit", "exit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if cmd == "help":
                display_help()
                continue

            if cmd == "agents":
                display_agents(client)
                continue

            if cmd == "clear":
                console.clear()
                continue

            if cmd == "new":
                session_response_id = None
                console.print("[green]Started new conversation[/green]")
                continue

            if cmd.startswith("use "):
                agent_name = prompt[4:].strip()
                session_response_id = None  # Reset conversation when switching agents
                console.print(
                    f"[green]Switched to {agent_name} (new conversation)[/green]"
                )
                continue

            if cmd.startswith("config "):
                integration = prompt[7:].strip().lower()
                await configure_integration(client, session, integration)
                continue

            if cmd == "config":
                await show_config_status(client)
                continue

            # Run investigation with streaming, passing previous response_id for follow-ups
            console.print()
            new_response_id = await run_with_streaming(
                client,
                agent_name,
                prompt,
                session,
                previous_response_id=session_response_id,
            )
            # Update session_response_id for next follow-up
            if new_response_id:
                session_response_id = new_response_id
            console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'quit' to exit[/dim]")
        except EOFError:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


async def run_with_streaming(
    client: AgentClient,
    agent_name: str,
    message: str,
    session=None,
    previous_response_id: str | None = None,
) -> str | None:
    """
    Run agent with SSE streaming and display events in real-time.

    Shows execution trace like Claude Code/Cursor, including nested sub-agent calls.
    Handles human input requests by prompting the user and resuming the conversation.

    Args:
        client: Agent client instance
        agent_name: Name of agent to run
        message: User message/query
        session: Prompt session for user input
        previous_response_id: Optional response ID for resumption (continues from previous state)

    Returns:
        The last_response_id from the agent run, for chaining follow-up queries
    """
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.text import Text

    tool_calls = []
    final_result = None
    # Track nested agent depth for indentation
    agent_stack = [agent_name]
    # Track config issues encountered during the run
    config_issues = []
    # Track response_id for potential resumption
    current_conversation_id = previous_response_id
    # Track if we need human input
    pending_human_input = None

    def get_indent(depth: int = None) -> str:
        """Get indentation based on agent nesting depth."""
        if depth is None:
            depth = len(agent_stack) - 1
        return "  " * (depth + 1)

    def check_for_config_required(output_preview: str) -> dict | None:
        """Check if tool output indicates config is required."""
        if not output_preview:
            return None
        # Check if this looks like a config_required response
        if (
            '"config_required": true' not in output_preview
            and '"config_required":true' not in output_preview
        ):
            return None

        try:
            # Try to parse as complete JSON first
            data = json.loads(output_preview)
            if data.get("config_required"):
                return data
        except json.JSONDecodeError:
            # JSON is truncated - use regex to extract key fields
            import re

            integration_match = re.search(r'"integration":\s*"([^"]+)"', output_preview)
            tool_match = re.search(r'"tool":\s*"([^"]+)"', output_preview)
            if integration_match:
                return {
                    "config_required": True,
                    "integration": integration_match.group(1),
                    "tool": tool_match.group(1) if tool_match else "unknown",
                }
        except Exception:
            pass
        return None

    def check_for_human_input_required(output_preview: str) -> dict | None:
        """Check if tool output indicates human input is required."""
        if not output_preview:
            return None
        if (
            '"human_input_required": true' not in output_preview
            and '"human_input_required":true' not in output_preview
        ):
            return None

        try:
            data = json.loads(output_preview)
            if data.get("human_input_required"):
                return data
        except json.JSONDecodeError:
            # Try regex extraction for truncated JSON
            import re

            question_match = re.search(r'"question":\s*"([^"]+)"', output_preview)
            if question_match:
                return {
                    "human_input_required": True,
                    "question": question_match.group(1),
                    "response_type": "text",
                }
        except Exception:
            pass
        return None

    try:
        # Initial status
        if current_conversation_id:
            console.print(
                f"[dim]Resuming {agent_name} (conversation continues)...[/dim]"
            )
        else:
            console.print(f"[dim]Starting {agent_name}...[/dim]")

        async for event in client.run_agent_stream(
            agent_name, message, previous_response_id=current_conversation_id
        ):
            event_type = event.get("event_type", "unknown")
            depth = event.get("depth", 0)
            indent = get_indent(depth)

            if event_type == "agent_started":
                console.print(
                    f"[green]{indent}Agent started[/green] [dim]({event.get('correlation_id', '')[:8]})[/dim]"
                )

            elif event_type == "subagent_started":
                # Sub-agent started - show nesting
                subagent_name = event.get("agent", "unknown")
                parent = event.get("parent_agent", "")
                agent_stack.append(subagent_name)
                console.print(
                    f"[magenta]{indent}▶ {subagent_name}[/magenta] [dim](delegated from {parent})[/dim]"
                )

            elif event_type == "subagent_completed":
                # Sub-agent completed
                subagent_name = event.get("agent", "unknown")
                success = event.get("success", True)
                if agent_stack and agent_stack[-1] == subagent_name:
                    agent_stack.pop()
                if success:
                    console.print(f"[green]{indent}◀ {subagent_name} done[/green]")
                else:
                    error = event.get("error", "")
                    console.print(
                        f"[red]{indent}◀ {subagent_name} failed:[/red] {error[:50]}"
                    )

            elif event_type == "tool_started":
                tool_name = event.get("tool", "unknown")
                tool_input = event.get("input", {})
                input_preview = event.get("input_preview", "")
                seq = event.get("sequence", 0)
                agent = event.get("agent", "")

                # Format input preview with proper truncation
                if not input_preview and tool_input:
                    if isinstance(tool_input, dict):
                        # Show first few key=value pairs, truncate long values cleanly
                        def format_value(v, max_len=30):
                            if isinstance(v, str):
                                # For strings: show without quotes, truncate cleanly
                                if len(v) > max_len:
                                    return v[:max_len] + "..."
                                return v
                            else:
                                # For other types: use repr
                                s = repr(v)
                                if len(s) > max_len:
                                    return s[:max_len] + "..."
                                return s

                        pairs = [
                            f"{k}={format_value(v)}"
                            for k, v in list(tool_input.items())[:2]
                        ]
                        input_preview = ", ".join(pairs)
                    else:
                        s = str(tool_input)
                        input_preview = s[:50] + "..." if len(s) > 50 else s

                # Truncate overall preview to avoid very long lines
                if input_preview:
                    if len(input_preview) > 80:
                        input_preview = input_preview[:80] + "..."
                    input_preview = f"({input_preview})"

                # Show which agent is calling the tool
                agent_prefix = (
                    f"[dim]{agent}:[/dim] " if agent and agent != agent_name else ""
                )
                console.print(
                    f"[yellow]{indent}→ {agent_prefix}[/yellow][cyan]{tool_name}[/cyan]{input_preview}"
                )
                tool_calls.append({"tool": tool_name, "seq": seq, "agent": agent})

            elif event_type == "tool_completed":
                seq = event.get("sequence", 0)
                output_preview = event.get("output_preview", "")

                # Check if tool output indicates config is required
                config_data = check_for_config_required(output_preview)
                if config_data:
                    # Track this config issue
                    integration = config_data.get("integration", "unknown")
                    if integration not in [c.get("integration") for c in config_issues]:
                        config_issues.append(config_data)
                    # Show user-friendly message
                    console.print(
                        f"[yellow]{indent}⚠ {integration.upper()} not configured[/yellow]"
                    )
                else:
                    # Check if tool output indicates human input is required
                    human_input_data = check_for_human_input_required(output_preview)
                    if human_input_data:
                        pending_human_input = human_input_data
                        console.print(f"[cyan]{indent}⏸ Agent needs your input[/cyan]")
                    else:
                        # Show brief output preview
                        if output_preview and len(output_preview) > 80:
                            output_preview = output_preview[:80] + "..."
                        console.print(
                            f"[green]{indent}✓[/green] [dim]{output_preview if output_preview else ''}[/dim]"
                        )

            elif event_type == "human_input_required":
                # Direct human input request event (from SSE)
                pending_human_input = event
                console.print(f"[cyan]{indent}⏸ Agent needs your input[/cyan]")

            elif event_type == "message":
                content = event.get("content_preview", "")
                if content:
                    console.print(f"[blue]{indent}Message:[/blue] {content[:100]}")

            elif event_type == "agent_handoff":
                new_agent = event.get("new_agent", "unknown")
                console.print(f"[magenta]{indent}→ Handoff to {new_agent}[/magenta]")

            elif event_type == "agent_completed":
                final_result = event
                success = event.get("success", False)
                duration = event.get("duration_seconds", 0)
                tc_count = event.get("tool_calls_count", len(tool_calls))
                # Capture last_response_id for follow-up queries (chains without pre-created conversations)
                current_conversation_id = (
                    event.get("last_response_id") or current_conversation_id
                )

                if success:
                    console.print(
                        f"[green]{indent}Completed[/green] in {duration:.1f}s ({tc_count} tool calls)"
                    )
                else:
                    error = event.get("error", "Unknown error")
                    console.print(f"[red]{indent}Failed:[/red] {error}")

            elif event_type == "error":
                error = event.get("error", "Unknown error")
                console.print(f"[red]Error: {error}[/red]")
                return

        # Handle human input request if detected
        if pending_human_input and session:
            console.print()
            human_response = await handle_human_input_request(
                pending_human_input, session
            )
            if human_response:
                # Resume the conversation with the human's response
                console.print("\n[dim]Resuming with your input...[/dim]\n")
                return await run_with_streaming(
                    client,
                    agent_name,
                    human_response,
                    session,
                    previous_response_id=current_conversation_id,
                )

        # Display config issues if any were encountered
        if config_issues:
            console.print()
            should_retry = await display_config_issues(config_issues, session, client)
            if should_retry:
                # Retry with conversation_id to resume from where we left off
                if current_conversation_id:
                    console.print(
                        "\n[dim]Resuming your query with new configuration (previous work preserved)...[/dim]\n"
                    )
                else:
                    console.print(
                        "\n[dim]Retrying your query with new configuration...[/dim]\n"
                    )
                return await run_with_streaming(
                    client,
                    agent_name,
                    message,
                    session,
                    previous_response_id=current_conversation_id,
                )

        # Display final output
        if final_result:
            console.print()
            output = final_result.get("output")
            if output:
                display_result({"output": output, "success": True})
            elif not final_result.get("success"):
                display_error(final_result)

        # Return last_response_id for chaining follow-up queries
        return current_conversation_id

    except Exception as e:
        console.print(f"[red]Stream error: {e}[/red]")
        return None


async def handle_human_input_request(request: dict, session) -> str | None:
    """
    Handle a human input request from the agent.

    Displays the question and prompts the user for input based on the response type.

    Args:
        request: The human input request data containing question, context, etc.
        session: Prompt session for user input

    Returns:
        The user's response, or None if cancelled
    """
    question = request.get("question", "The agent needs your input")
    context = request.get("context")
    action_required = request.get("action_required")
    response_type = request.get("response_type", "text")
    choices = request.get("choices", [])

    # Display the request
    console.print(
        Panel.fit(
            f"[bold cyan]{question}[/bold cyan]",
            title="🤖 Agent Request",
            border_style="cyan",
        )
    )

    # Show context if provided
    if context:
        console.print(f"\n[dim]Context:[/dim] {context}")

    # Show action required if provided
    if action_required:
        console.print(f"\n[yellow]Action needed:[/yellow] {action_required}")

    console.print()

    # Get response based on type
    try:
        if response_type == "yes_no":
            response = await session.prompt_async("Your answer [Y/n]: ")
            response = response.strip().lower()
            if response in ("", "y", "yes"):
                return "yes"
            elif response in ("n", "no"):
                return "no"
            else:
                return response  # Pass through other responses

        elif response_type == "choice" and choices:
            console.print("[dim]Options:[/dim]")
            for i, choice in enumerate(choices, 1):
                console.print(f"  {i}. {choice}")
            console.print()
            response = await session.prompt_async("Your choice (number or text): ")
            response = response.strip()
            # Handle numeric selection
            try:
                idx = int(response) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            except ValueError:
                pass
            return response  # Return as-is if not a number

        elif response_type == "action_done":
            response = await session.prompt_async(
                "Type 'done' when ready (or 'skip' to continue without): "
            )
            response = response.strip().lower()
            if response == "skip":
                return "User chose to skip this action and continue without it."
            elif response in ("done", "ready", "ok", "yes", ""):
                return "done"
            else:
                return response

        else:  # Default text response
            response = await session.prompt_async("Your response: ")
            return response.strip() if response.strip() else None

    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled.[/dim]")
        return None


async def display_config_issues(
    config_issues: list[dict], session=None, client=None
) -> bool:
    """
    Display configuration issues encountered during the run.

    Shows what integrations need to be configured and offers to configure them.

    Returns:
        True if configuration was successful and query should be retried
    """
    # Get unique integrations
    integrations = list(
        {issue.get("integration", "unknown") for issue in config_issues}
    )

    console.print(
        Panel.fit(
            "[bold yellow]Configuration Required[/bold yellow]\n\n"
            "Some integrations are not configured. The agent worked around these\n"
            "limitations, but you can enable them now for full functionality.",
            title="⚠ Missing Configuration",
            border_style="yellow",
        )
    )

    for issue in config_issues:
        integration = issue.get("integration", "unknown").upper()
        missing = issue.get("missing_config", [])

        console.print(f"\n[bold cyan]{integration}[/bold cyan]")

        if missing:
            console.print("[dim]Missing:[/dim]")
            for item in missing:
                console.print(f"  [red]•[/red] {item}")

    # Offer to configure if we have a session
    if session and len(integrations) > 0:
        console.print()
        if len(integrations) == 1:
            integration = integrations[0]
            response = await session.prompt_async(
                f"Configure {integration} now? [Y/n]: "
            )
            if response.lower() in ("", "y", "yes"):
                success = await configure_integration(client, session, integration)
                return success
        else:
            console.print(f"[dim]Unconfigured: {', '.join(integrations)}[/dim]")
            response = await session.prompt_async(
                "Configure which integration? (or press Enter to skip): "
            )
            if response.strip():
                success = await configure_integration(client, session, response.strip())
                return success
    else:
        console.print()
        console.print(
            "[dim]Type 'config <integration>' to configure (e.g., 'config kubernetes')[/dim]"
        )

    return False


def display_result(result: dict):
    """Display successful agent result."""
    output = result.get("output", "No output")
    duration = result.get("duration")

    # Try to render as markdown
    try:
        if isinstance(output, dict):
            import json

            output = json.dumps(output, indent=2)
        console.print(Markdown(str(output)))
    except Exception:
        console.print(output)

    if duration:
        console.print(f"\n[dim]Completed in {duration:.1f}s[/dim]")


def display_error(result: dict):
    """Display error result."""
    error = result.get("error", "Unknown error")
    console.print(f"[red]❌ Error: {error}[/red]")


def display_agents(client: AgentClient):
    """Display available agents."""
    agents = client.list_agents()

    table = Table(title="Available Agents")
    table.add_column("Agent", style="cyan")
    table.add_column("Description")

    descriptions = {
        "planner": "Entry point - orchestrates sub-agents (recommended)",
        "investigation_agent": "Full toolkit - autonomous investigation",
        "k8s_agent": "Kubernetes specialist - pods, logs, events",
        "aws_agent": "AWS specialist - EC2, Lambda, RDS, CloudWatch",
        "metrics_agent": "Performance analysis - anomaly detection",
        "coding_agent": "Code analysis - GitHub, git operations",
        "ci_agent": "CI/CD - GitHub Actions, pipelines",
    }

    for a in agents:
        desc = descriptions.get(a, "")
        table.add_row(a, desc)

    console.print(table)


def display_help():
    """Display help message."""
    help_text = """
## Commands

| Command | Description |
|---------|-------------|
| `help` | Show this help |
| `agents` | List available agents |
| `use <agent>` | Switch to different agent |
| `config` | Show integration config status |
| `config <name>` | Configure an integration (e.g., `config kubernetes`) |
| `clear` | Clear screen |
| `quit` | Exit CLI |

## How It Works

The **planner** agent is the entry point. It analyzes your query and delegates
to specialized sub-agents:

- **K8s Agent** - Kubernetes issues (pods, logs, events, deployments)
- **AWS Agent** - AWS resources (EC2, Lambda, RDS, CloudWatch)
- **Metrics Agent** - Performance analysis and anomaly detection
- **Coding Agent** - Code review, GitHub operations
- **Investigation Agent** - Full autonomous investigation with all tools

## Example Prompts

```
Check if there are any pods crashing in the default namespace
```

```
Investigate why the API service is returning 500 errors
```

```
Analyze the performance of our payment service
```

```
Find recent changes in the auth service that might have caused issues
```

```
What GitHub PRs were merged in the last 24 hours?
```
"""
    console.print(Markdown(help_text))


async def show_config_status(client: AgentClient):
    """Show status of all integration configurations."""
    table = Table(title="Integration Configuration Status")
    table.add_column("Integration", style="cyan")
    table.add_column("Status")
    table.add_column("Notes")

    # Check Kubernetes
    k8s_status, k8s_notes = check_k8s_config()
    table.add_row("Kubernetes", k8s_status, k8s_notes)

    # Check AWS
    aws_status, aws_notes = check_aws_config()
    table.add_row("AWS", aws_status, aws_notes)

    # Check GitHub
    github_status, github_notes = check_github_config()
    table.add_row("GitHub", github_status, github_notes)

    # Check Slack
    slack_status, slack_notes = check_slack_config()
    table.add_row("Slack", slack_status, slack_notes)

    console.print(table)
    console.print("\n[dim]Use 'config <integration>' to configure an integration[/dim]")


def check_k8s_config() -> tuple[str, str]:
    """Check Kubernetes configuration status."""
    from pathlib import Path

    k8s_enabled = os.getenv("K8S_ENABLED", "false").lower() == "true"
    kubeconfig = Path.home() / ".kube" / "config"

    if k8s_enabled and kubeconfig.exists():
        return "[green]✓ Configured[/green]", "~/.kube/config found"
    elif kubeconfig.exists():
        return "[yellow]⚠ Disabled[/yellow]", "Set K8S_ENABLED=true in .env"
    else:
        return "[red]✗ Not configured[/red]", "No kubeconfig found"


def check_aws_config() -> tuple[str, str]:
    """Check AWS configuration status."""
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    has_creds = os.getenv("AWS_ACCESS_KEY_ID") or os.path.exists(
        os.path.expanduser("~/.aws/credentials")
    )

    if region and has_creds:
        return "[green]✓ Configured[/green]", f"Region: {region}"
    elif has_creds:
        return "[yellow]⚠ Partial[/yellow]", "Set AWS_REGION"
    else:
        return "[red]✗ Not configured[/red]", "No AWS credentials"


def check_github_config() -> tuple[str, str]:
    """Check GitHub configuration status."""
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return "[green]✓ Configured[/green]", "Token set"
    return "[red]✗ Not configured[/red]", "Set GITHUB_TOKEN"


def check_slack_config() -> tuple[str, str]:
    """Check Slack configuration status."""
    token = os.getenv("SLACK_BOT_TOKEN")
    if token:
        return "[green]✓ Configured[/green]", "Token set"
    return "[dim]○ Optional[/dim]", "Set SLACK_BOT_TOKEN if needed"


def get_env_file_path() -> str:
    """Get the path to the .env file."""
    # Look for .env in current directory or local/ directory
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.getcwd(), "local", ".env"),
        os.path.expanduser("~/.incidentfox/.env"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    # Default to local/.env if none found
    return os.path.join(os.getcwd(), "local", ".env")


def read_env_file(path: str) -> dict[str, str]:
    """Read .env file into a dictionary."""
    env_vars = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    env_vars[key.strip()] = value
    return env_vars


def write_env_file(path: str, env_vars: dict[str, str], preserve_comments: bool = True):
    """Write environment variables to .env file, preserving comments and order."""
    lines = []
    existing_keys = set()

    # Read existing file to preserve comments and order
    if os.path.exists(path) and preserve_comments:
        with open(path) as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if key in env_vars:
                        # Update existing value
                        lines.append(f"{key}={env_vars[key]}\n")
                        existing_keys.add(key)
                    else:
                        lines.append(line)
                else:
                    lines.append(line)

    # Add new keys at the end
    for key, value in env_vars.items():
        if key not in existing_keys:
            lines.append(f"{key}={value}\n")

    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w") as f:
        f.writelines(lines)


def update_env_var(key: str, value: str) -> bool:
    """Update a single environment variable in .env file."""
    try:
        env_path = get_env_file_path()
        env_vars = read_env_file(env_path)
        env_vars[key] = value
        write_env_file(env_path, env_vars)
        # Also update current process environment
        os.environ[key] = value
        return True
    except Exception as e:
        console.print(f"[red]Failed to update .env: {e}[/red]")
        return False


async def restart_agent_service():
    """Recreate agent container to apply new config."""
    console.print("\n[dim]Recreating agent service to apply new config...[/dim]")
    try:
        import subprocess

        cli_dir = os.path.dirname(os.path.abspath(__file__))
        local_dir = os.path.dirname(cli_dir)

        # Check if dev compose file exists (mounts local source code)
        dev_compose = os.path.join(local_dir, "docker-compose.dev.yml")
        if os.path.exists(dev_compose):
            # Use dev compose to mount local source code
            cmd = [
                "docker-compose",
                "-f",
                "docker-compose.yml",
                "-f",
                "docker-compose.dev.yml",
                "up",
                "-d",
                "--force-recreate",
                "agent",
            ]
        else:
            # Standard compose (pre-built image)
            cmd = ["docker-compose", "up", "-d", "--force-recreate", "agent"]

        # Must use 'up -d --force-recreate' to reload .env file
        # docker-compose restart does NOT reload env vars
        result = subprocess.run(
            cmd,
            cwd=local_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            console.print("[green]✓ Agent service recreated with new config![/green]")
            console.print("[dim]Waiting for service to be ready...[/dim]")
            import asyncio

            await asyncio.sleep(5)
            return True
        else:
            console.print(f"[yellow]Could not recreate: {result.stderr}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Could not recreate: {e}[/yellow]")

    console.print("\n[yellow]Please recreate the agent manually:[/yellow]")
    console.print(
        "  [cyan]cd local && docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --force-recreate agent[/cyan]"
    )
    return False


async def configure_integration(client: AgentClient, session, integration: str) -> bool:
    """Interactive configuration for an integration.

    Returns:
        True if configuration was successful
    """
    integration = integration.lower()

    if integration in ("kubernetes", "k8s"):
        return await configure_kubernetes(session)
    elif integration == "aws":
        return await configure_aws(session)
    elif integration == "github":
        return await configure_github(session)
    elif integration == "slack":
        return await configure_slack(session)
    else:
        console.print(f"[red]Unknown integration: {integration}[/red]")
        console.print("[dim]Available: kubernetes, aws, github, slack[/dim]")
        return False


async def configure_kubernetes(session) -> bool:
    """Interactive Kubernetes configuration - auto-enables if kubeconfig exists.

    Returns:
        True if configuration was successful
    """
    from pathlib import Path

    console.print(
        Panel.fit(
            "[bold cyan]Kubernetes Configuration[/bold cyan]",
            title="🔧 Configure Kubernetes",
        )
    )

    kubeconfig = Path.home() / ".kube" / "config"
    k8s_enabled = os.getenv("K8S_ENABLED", "false").lower() == "true"

    if kubeconfig.exists():
        console.print(f"[green]✓[/green] Found kubeconfig at {kubeconfig}")

        # Read current context
        try:
            import yaml

            with open(kubeconfig) as f:
                kc = yaml.safe_load(f)
                current = kc.get("current-context", "unknown")
                contexts = [c["name"] for c in kc.get("contexts", [])]
                console.print(
                    f"[green]✓[/green] Current context: [cyan]{current}[/cyan]"
                )
                if len(contexts) > 1:
                    console.print(f"[dim]  Available: {', '.join(contexts)}[/dim]")
        except Exception:
            pass

        if not k8s_enabled:
            # Auto-enable K8s
            console.print("\n[yellow]K8S_ENABLED is currently 'false'[/yellow]")
            response = await session.prompt_async(
                "Enable Kubernetes integration? [Y/n]: "
            )
            if response.lower() in ("", "y", "yes"):
                if update_env_var("K8S_ENABLED", "true"):
                    console.print("[green]✓ K8S_ENABLED=true saved to .env[/green]")
                    await restart_agent_service()
                    console.print("\n[green]✓ Kubernetes is now configured![/green]")
                    return True
                else:
                    console.print("[red]Failed to update .env file[/red]")
                    return False
            else:
                console.print("[dim]Skipped.[/dim]")
                return False
        else:
            console.print("\n[green]✓ Kubernetes is fully configured![/green]")
            return True  # Already configured
    else:
        console.print(f"[red]✗[/red] No kubeconfig found at {kubeconfig}")
        console.print("\n[yellow]To set up Kubernetes:[/yellow]")
        console.print("  1. If you have kubectl configured elsewhere:")
        console.print("     [cyan]cp /path/to/kubeconfig ~/.kube/config[/cyan]")
        console.print("  2. Or connect to a cluster:")
        console.print("     [cyan]kubectl config set-cluster ...[/cyan]")
        console.print("\nThen run [cyan]config kubernetes[/cyan] again.")
        return False


async def configure_aws(session) -> bool:
    """Interactive AWS configuration - prompts for region and credentials.

    Returns:
        True if configuration was successful
    """
    console.print(
        Panel.fit(
            "[bold cyan]AWS Configuration[/bold cyan]",
            title="🔧 Configure AWS",
        )
    )

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    has_creds = os.getenv("AWS_ACCESS_KEY_ID") or os.path.exists(
        os.path.expanduser("~/.aws/credentials")
    )
    changes_made = False

    # Check credentials
    if has_creds:
        console.print("[green]✓[/green] AWS credentials found")
    else:
        console.print("[red]✗[/red] No AWS credentials found")
        console.print("\n[yellow]Do you want to configure AWS credentials?[/yellow]")
        response = await session.prompt_async(
            "Enter AWS Access Key ID (or press Enter to skip): "
        )
        if response.strip():
            access_key = response.strip()
            secret_key = await session.prompt_async("Enter AWS Secret Access Key: ")
            if secret_key.strip():
                update_env_var("AWS_ACCESS_KEY_ID", access_key)
                update_env_var("AWS_SECRET_ACCESS_KEY", secret_key.strip())
                console.print("[green]✓ AWS credentials saved to .env[/green]")
                changes_made = True
                has_creds = True

    # Check region
    if region:
        console.print(f"[green]✓[/green] AWS_REGION: [cyan]{region}[/cyan]")
    else:
        console.print("\n[yellow]AWS_REGION not set[/yellow]")
        response = await session.prompt_async(
            "Enter AWS region (e.g., us-west-2, us-east-1): "
        )
        if response.strip():
            update_env_var("AWS_REGION", response.strip())
            console.print(
                f"[green]✓ AWS_REGION={response.strip()} saved to .env[/green]"
            )
            changes_made = True
            region = response.strip()

    if changes_made:
        await restart_agent_service()
        console.print("\n[green]✓ AWS is now configured![/green]")
        return True
    elif has_creds and region:
        console.print("\n[green]✓ AWS is fully configured![/green]")
        return True

    return False


async def configure_github(session) -> bool:
    """Interactive GitHub configuration - prompts for token.

    Returns:
        True if configuration was successful
    """
    console.print(
        Panel.fit(
            "[bold cyan]GitHub Configuration[/bold cyan]",
            title="🔧 Configure GitHub",
        )
    )

    token = os.getenv("GITHUB_TOKEN")
    if token:
        # Show masked token
        masked = token[:4] + "..." + token[-4:] if len(token) > 8 else "***"
        console.print(f"[green]✓[/green] GITHUB_TOKEN is set ({masked})")
        response = await session.prompt_async("Update token? [y/N]: ")
        if response.lower() not in ("y", "yes"):
            console.print("\n[green]✓ GitHub is configured![/green]")
            return True  # Already configured

    if not token:
        console.print("[yellow]GITHUB_TOKEN not set[/yellow]")
        console.print("\n[dim]To get a token:[/dim]")
        console.print("  1. Go to [cyan]https://github.com/settings/tokens[/cyan]")
        console.print("  2. Create a token with 'repo' and 'read:org' scopes")

    console.print()
    new_token = await session.prompt_async("Paste your GitHub token (ghp_...): ")
    if new_token.strip():
        if new_token.strip().startswith("ghp_") or new_token.strip().startswith(
            "github_"
        ):
            update_env_var("GITHUB_TOKEN", new_token.strip())
            console.print("[green]✓ GITHUB_TOKEN saved to .env[/green]")
            await restart_agent_service()
            console.print("\n[green]✓ GitHub is now configured![/green]")
            return True
        else:
            console.print(
                "[yellow]Token doesn't look like a GitHub token (should start with ghp_ or github_)[/yellow]"
            )
            confirm = await session.prompt_async("Save anyway? [y/N]: ")
            if confirm.lower() in ("y", "yes"):
                update_env_var("GITHUB_TOKEN", new_token.strip())
                console.print("[green]✓ GITHUB_TOKEN saved to .env[/green]")
                await restart_agent_service()
                return True
    else:
        console.print("[dim]Skipped.[/dim]")

    return False


async def configure_slack(session) -> bool:
    """Interactive Slack configuration - prompts for token.

    Returns:
        True if configuration was successful
    """
    console.print(
        Panel.fit(
            "[bold cyan]Slack Configuration[/bold cyan]",
            title="🔧 Configure Slack",
        )
    )

    token = os.getenv("SLACK_BOT_TOKEN")
    if token:
        console.print("[green]✓[/green] SLACK_BOT_TOKEN is set")
        response = await session.prompt_async("Update token? [y/N]: ")
        if response.lower() not in ("y", "yes"):
            console.print("\n[green]✓ Slack is configured![/green]")
            return True  # Already configured

    if not token:
        console.print("[dim]SLACK_BOT_TOKEN not set (optional integration)[/dim]")
        console.print("\n[dim]To get a token:[/dim]")
        console.print("  1. Create app at [cyan]https://api.slack.com/apps[/cyan]")
        console.print("  2. Add scopes: channels:history, channels:read, chat:write")
        console.print("  3. Install to workspace and copy Bot Token")

    console.print()
    new_token = await session.prompt_async("Paste your Slack Bot Token (xoxb-...): ")
    if new_token.strip():
        if new_token.strip().startswith("xoxb-"):
            update_env_var("SLACK_BOT_TOKEN", new_token.strip())
            console.print("[green]✓ SLACK_BOT_TOKEN saved to .env[/green]")
            await restart_agent_service()
            console.print("\n[green]✓ Slack is now configured![/green]")
            return True
        else:
            console.print(
                "[yellow]Token doesn't look like a Slack bot token (should start with xoxb-)[/yellow]"
            )
            confirm = await session.prompt_async("Save anyway? [y/N]: ")
            if confirm.lower() in ("y", "yes"):
                update_env_var("SLACK_BOT_TOKEN", new_token.strip())
                console.print("[green]✓ SLACK_BOT_TOKEN saved to .env[/green]")
                await restart_agent_service()
                return True
    else:
        console.print("[dim]Skipped.[/dim]")

    return False


if __name__ == "__main__":
    main()
