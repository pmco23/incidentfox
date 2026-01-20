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

    while True:
        try:
            # Get input
            prompt = await session.prompt_async("incidentfox> ")
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

            if cmd.startswith("use "):
                agent_name = prompt[4:].strip()
                console.print(f"[green]Switched to {agent_name}[/green]")
                continue

            # Run investigation
            console.print()

            with console.status(
                "[bold green]Investigating...[/bold green]", spinner="dots"
            ):
                result = await client.run_agent(agent_name, prompt)

            if result.get("success"):
                display_result(result)
            else:
                display_error(result)

            console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'quit' to exit[/dim]")
        except EOFError:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


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


if __name__ == "__main__":
    main()
