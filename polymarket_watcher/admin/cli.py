"""Admin CLI — entry point for ``python -m polymarket_watcher.admin``.

Subcommands
-----------
init            Interactively initialise the admin config file.
config-path     Print the path to the admin config file.
status          Show ``systemctl status`` for the remote service.
logs            Stream live logs in a Textual TUI (press q to quit).
restart         Prompt then restart the remote systemd unit.
config edit     Download remote config, open local editor, upload back.
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
from pathlib import Path

import click
import yaml

from .admin_config import AdminConfig, default_config_path
from .editor import open_editor
from .ssh import scp_download, scp_upload, ssh_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_cfg(config_file: str | None) -> AdminConfig:
    """Load AdminConfig from *config_file* or the default user path."""
    if config_file:
        return AdminConfig.load(Path(config_file))
    return AdminConfig.load()


def _validate_service_config(yaml_text: str) -> None:
    """Parse *yaml_text* and instantiate Config dataclasses to validate it.

    Raises ``click.ClickException`` on any error.
    """
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        raise click.ClickException(f"YAML parse error: {exc}") from exc

    # Re-use the existing service Config dataclasses for schema validation
    try:
        from polymarket_watcher.config import (
            ActionsConfig,
            Config,
            MarketConfig,
            PriceSupportConfig,
            ServiceConfig,
            WatcherConfig,
        )

        market_data = data.get("market", {})
        watcher_data = data.get("watcher", {})
        service_data = data.get("service", {})
        actions_data = data.get("actions", {})
        ps_data = watcher_data.get("price_support", {})

        Config(
            market=MarketConfig(**market_data),
            watcher=WatcherConfig(price_support=PriceSupportConfig(**ps_data)),
            service=ServiceConfig(**service_data),
            actions=ActionsConfig(
                log_enabled=actions_data.get("log", {}).get("enabled", True)
            ),
        )
    except Exception as exc:
        raise click.ClickException(f"Config validation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.option(
    "--config-file",
    envvar="PMW_ADMIN_CONFIG",
    default=None,
    help="Path to the admin config file (default: per-user location).",
)
@click.pass_context
def cli(ctx: click.Context, config_file: str | None) -> None:
    """Administer the polymarket-watcher service over SSH.

    Run 'python -m polymarket_watcher.admin init' on first use to set up the
    connection to your remote host.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config_file


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Interactively create or update the admin config file."""
    config_file = ctx.obj.get("config_file")
    path = Path(config_file) if config_file else default_config_path()

    click.echo(f"Admin config file: {path}")

    existing = AdminConfig.load(path)

    host = click.prompt("Remote host (IP or hostname)", default=existing.host or "")
    user = click.prompt("SSH user", default=existing.user)
    unit = click.prompt("systemd unit name", default=existing.unit)
    remote_config = click.prompt(
        "Remote config file path", default=existing.remote_config
    )

    cfg = AdminConfig(
        host=host,
        user=user,
        unit=unit,
        remote_config=remote_config,
        ssh_options=existing.ssh_options,
    )
    saved = cfg.save(path)
    click.echo(f"\nConfig saved to: {saved}")


# ---------------------------------------------------------------------------
# config-path
# ---------------------------------------------------------------------------

@cli.command("config-path")
@click.pass_context
def config_path(ctx: click.Context) -> None:
    """Print the path to the admin config file."""
    config_file = ctx.obj.get("config_file")
    path = Path(config_file) if config_file else default_config_path()
    click.echo(str(path))


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show systemctl status for the remote service."""
    cfg = _load_cfg(ctx.obj.get("config_file"))
    try:
        cfg.require_host()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Connecting to {cfg.user}@{cfg.host} …\n")
    result = ssh_run(
        cfg,
        ["systemctl", "status", cfg.unit, "--no-pager"],
        check=False,
    )
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
def logs(ctx: click.Context) -> None:
    """Stream live journalctl output to the terminal (Ctrl+C to stop)."""
    cfg = _load_cfg(ctx.obj.get("config_file"))
    try:
        cfg.require_host()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    from .tui import run_logs_tui

    run_logs_tui(cfg)


# ---------------------------------------------------------------------------
# restart
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
def restart(ctx: click.Context) -> None:
    """Prompt then restart the remote systemd unit."""
    cfg = _load_cfg(ctx.obj.get("config_file"))
    try:
        cfg.require_host()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    click.confirm(
        f"Restart '{cfg.unit}' on {cfg.user}@{cfg.host}?",
        abort=True,
    )
    click.echo("Restarting …")
    ssh_run(cfg, ["sudo", "systemctl", "restart", cfg.unit])
    click.echo("Done.")


# ---------------------------------------------------------------------------
# config (sub-group)
# ---------------------------------------------------------------------------

@cli.group("config")
@click.pass_context
def config_group(ctx: click.Context) -> None:
    """Manage the remote service config file."""


@config_group.command("edit")
@click.pass_context
def config_edit(ctx: click.Context) -> None:
    """Download remote config, edit locally, validate and upload back.

    \b
    Workflow
    --------
    1. Download  /etc/polymarket-watcher/config.yaml  via scp.
    2. Open your local editor (respects $EDITOR; falls back to VS Code / notepad / nano).
    3. Validate the edited file (YAML parse + schema check).
    4. Upload back atomically (write to .tmp then move on remote).
    5. Prompt to restart the service.
    """
    cfg = _load_cfg(ctx.obj.get("config_file"))
    try:
        cfg.require_host()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    with tempfile.NamedTemporaryFile(
        suffix=".yaml", prefix="pmw-config-", delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # 1. Download
        click.echo(f"Downloading {cfg.remote_config} from {cfg.user}@{cfg.host} …")
        try:
            scp_download(cfg, cfg.remote_config, tmp_path)
        except Exception as exc:
            raise click.ClickException(f"Download failed: {exc}") from exc

        original_text = tmp_path.read_text(encoding="utf-8")

        # 2. Open editor
        click.echo(f"Opening editor for {tmp_path} …")
        open_editor(tmp_path)

        edited_text = tmp_path.read_text(encoding="utf-8")

        if edited_text == original_text:
            click.echo("No changes detected; skipping upload.")
            return

        # 3. Validate
        click.echo("Validating …")
        _validate_service_config(edited_text)
        click.echo("  ✓ YAML is valid.")

        # 4. Upload atomically
        remote_tmp = cfg.remote_config + ".tmp"
        click.echo(f"Uploading to {cfg.user}@{cfg.host}:{cfg.remote_config} …")
        try:
            scp_upload(cfg, tmp_path, remote_tmp)
            ssh_run(cfg, ["mv", remote_tmp, cfg.remote_config])
        except Exception as exc:
            # Attempt cleanup
            try:
                ssh_run(cfg, ["rm", "-f", remote_tmp], check=False)
            except Exception:
                pass
            raise click.ClickException(f"Upload failed: {exc}") from exc

        click.echo("  ✓ Config uploaded.")

        # 5. Prompt restart
        if click.confirm(f"Restart '{cfg.unit}' now?", default=False):
            ssh_run(cfg, ["sudo", "systemctl", "restart", cfg.unit])
            click.echo("Service restarted.")
        else:
            click.echo(
                textwrap.dedent(f"""
                Config saved.  To apply it, run:

                    python -m polymarket_watcher.admin restart
                """).strip()
            )
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
