import asyncio
import json
import sys

import click

from agent import AgentError, run_agent_loop
from models import AgentRequest, PocketChangeResponse


def _print_pretty(result: PocketChangeResponse) -> None:
    action_color = {
        "stake": "green",
        "wait": "yellow",
        "none": "red",
        "insufficient_information": "magenta",
    }
    risk_color = {"low": "green", "medium": "yellow", "high": "red"}

    click.echo()
    click.secho("PocketChange Analysis", bold=True)
    click.echo("=" * 50)
    click.echo(f"Wallets analyzed:    {len(result.wallets_analyzed)}")
    click.echo(f"Pocket change found: {len(result.pocket_change_wallets)} wallet(s)")
    if result.pocket_change_wallets:
        for addr in result.pocket_change_wallets:
            click.echo(f"  • {addr}")
    click.echo(f"Estimated value:     ${result.estimated_value_usd:.2f} USD")
    click.echo(
        "Recommended action:  "
        + click.style(result.recommended_action.upper(), fg=action_color.get(result.recommended_action, "white"), bold=True)
    )
    click.echo(
        "Risk level:          "
        + click.style(result.risk_level.upper(), fg=risk_color.get(result.risk_level, "white"))
    )
    click.echo()
    click.secho("Reasoning:", bold=True)
    click.echo(f"  {result.decision_reasoning}")

    if result.execution_steps:
        click.echo()
        click.secho("Execution steps:", bold=True)
        for step in result.execution_steps:
            click.echo(f"  {step.step}. {step.action}")
            if step.contract:
                click.echo(f"     Contract:  {step.contract}")
            if step.value_eth:
                click.echo(f"     Value:     {step.value_eth} ETH")
            if step.notes:
                click.echo(f"     Notes:     {step.notes}")

    if result.fee_amount_eth:
        click.echo()
        click.echo(f"Coordination fee:    0.025% = {result.fee_amount_eth} ETH → {result.fee_recipient}")

    if result.notes_for_agents:
        click.echo()
        click.secho("Notes for agents:", bold=True)
        click.echo(f"  {result.notes_for_agents}")

    click.echo()


@click.group()
def cli():
    """PocketChange — Autonomous Ethereum yield coordination agent."""


@cli.command()
@click.argument("addresses", nargs=-1, required=True)
@click.option("--threshold", default=100.0, show_default=True, help="Max USD value to qualify as pocket change.")
@click.option("--context", "agent_context", default=None, help="Free-text constraints from the calling agent.")
@click.option("--agent", "requesting_agent", default=None, help="Identifier of the requesting agent.")
@click.option(
    "--output",
    type=click.Choice(["json", "pretty"]),
    default="pretty",
    show_default=True,
    help="Output format.",
)
def analyze(addresses, threshold, agent_context, requesting_agent, output):
    """Analyze one or more Ethereum wallet ADDRESSES for idle ETH pocket change."""
    try:
        request = AgentRequest(
            wallet_addresses=list(addresses),
            agent_context=agent_context,
            requesting_agent=requesting_agent,
            max_eth_threshold_usd=threshold,
        )
    except Exception as e:
        click.secho(f"Invalid input: {e}", fg="red", err=True)
        sys.exit(1)

    try:
        result = asyncio.run(run_agent_loop(request))
    except AgentError as e:
        click.secho(f"Agent error: {e}", fg="red", err=True)
        sys.exit(1)

    if output == "json":
        click.echo(result.model_dump_json(indent=2))
    else:
        _print_pretty(result)


if __name__ == "__main__":
    cli()
