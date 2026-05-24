---
name: aria-status
description: Config-driven one-screen status of a server stack — systemd timers, healthz endpoints, disk usage, GPU memory/util (if nvidia-smi present), and optional custom shell-command probes. All probes run in parallel with short timeouts; graceful degradation if any single check fails. Read-only by design. Text output by default; --json for machine-readable, --brief for one-screen. Use at session start, before a deploy, or when the user says "status", "how are things", "any issues".
---

# aria-status

Generic server status. Config-driven via `aria_status_config.yaml`.

## Usage

```sh
python3 aria_status.py                           # text report
python3 aria_status.py --brief                   # one-screen summary
python3 aria_status.py --json                    # machine-readable
python3 aria_status.py --config my-config.yaml   # custom config
```

## Config

See `aria_status_config.yaml` for the full shape. Top-level keys: `timer_patterns`, `healthz`, `disk_mounts`, `commands`.

## License

Apache 2.0
