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

from .admin_config import AdminConfig, default_config_path
from .editor import open_editor
from .ssh import scp_upload, ssh_run
from .validator import ConfigValidationError, validate_service_config


_LEGACY_REMOTE_CONFIG_PATH = "/opt/polymarket-watcher/config.yaml"
_DEFAULT_REMOTE_CONFIG_PATH = "/etc/polymarket-watcher/config.yaml"


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

    Delegates to :func:`~.validator.validate_service_config` and re-raises any
    :class:`~.validator.ConfigValidationError` as a ``click.ClickException`` so
    that click formats and displays the message correctly.
    """
    try:
        validate_service_config(yaml_text)
    except ConfigValidationError as exc:
        raise click.ClickException(str(exc)) from exc


def _candidate_remote_config_paths(remote_config: str) -> list[str]:
    """Return ordered candidate paths for downloading service config.

    Keeps current behavior for non-legacy paths while allowing a one-time
    fallback for historical installs that used /opt/.../config.yaml.
    """
    if remote_config == _LEGACY_REMOTE_CONFIG_PATH:
        return [_LEGACY_REMOTE_CONFIG_PATH, _DEFAULT_REMOTE_CONFIG_PATH]
    return [remote_config]


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
    remote_config_group = click.prompt(
        "Remote config file group (service-read)",
        default=existing.remote_config_group,
    )

    cfg = AdminConfig(
        host=host,
        user=user,
        unit=unit,
        remote_config=remote_config,
        remote_config_group=remote_config_group,
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
    1. Download remote config using sudo cat over SSH.
    2. Open your local editor (respects $EDITOR; falls back to VS Code / notepad / nano).
    3. Validate the edited file (YAML parse + schema check).
    4. Upload to /tmp and install atomically with sudo (owner=root, mode=0640).
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
        chosen_remote_config: str | None = None
        download_error: Exception | None = None
        for candidate in _candidate_remote_config_paths(cfg.remote_config):
            click.echo(f"Downloading {candidate} from {cfg.user}@{cfg.host} …")
            try:
                result = ssh_run(
                    cfg,
                    ["sudo", "cat", candidate],
                    capture=True,
                )
            except Exception as exc:
                download_error = exc
                continue

            chosen_remote_config = candidate
            tmp_path.write_text(result.stdout, encoding="utf-8")
            break

        if chosen_remote_config is None:
            raise click.ClickException(f"Download failed: {download_error}")

        if chosen_remote_config != cfg.remote_config:
            old_remote_config = cfg.remote_config
            cfg.remote_config = chosen_remote_config
            config_file = ctx.obj.get("config_file")
            save_path = Path(config_file) if config_file else default_config_path()
            cfg.save(save_path)
            click.echo(
                "Detected legacy remote config path "
                f"'{old_remote_config}'. Updated to '{chosen_remote_config}' "
                f"in {save_path}."
            )

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
        remote_tmp = f"/tmp/pmw-config-{tmp_path.name}"
        click.echo(f"Uploading to {cfg.user}@{cfg.host}:{cfg.remote_config} …")
        try:
            scp_upload(cfg, tmp_path, remote_tmp)
            ssh_run(
                cfg,
                [
                    "sudo",
                    "install",
                    "-o",
                    "root",
                    "-g",
                    cfg.remote_config_group,
                    "-m",
                    "0640",
                    remote_tmp,
                    cfg.remote_config,
                ],
            )
            ssh_run(cfg, ["rm", "-f", remote_tmp], check=False)
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
