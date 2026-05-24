# aria-status

> One-screen status of any server stack. Config-driven; no vendor SDKs.

```sh
python3 aria_status.py
# HEALTH: 2/2 endpoints green
# TIMERS: 4 matching units present
# DISK /: 69.0% used · 517.2 GB free
# GPU NVIDIA L4: 28.4% mem · 12% util
```

## What it checks

- **Systemd timers** matching regex patterns
- **HTTP healthz endpoints** (parallel probe, 3s timeout each)
- **Disk usage** per mount point
- **GPU** via `nvidia-smi` (silent skip if absent)
- **Optional commands** — any shell command, optionally parsed as JSON

## Config

Edit `aria_status_config.yaml`:

```yaml
timer_patterns:
  - "\\bmyapp"
healthz:
  api:    "http://127.0.0.1:8080/health"
disk_mounts:
  - "/"
commands:
  - name: "queue depth"
    cmd: ["curl", "-s", "http://127.0.0.1:8080/queue.json"]
    parse_json: true
```

## CLI

| Flag | Effect |
|---|---|
| (none) | Text report |
| `--brief` | One-screen summary (skips per-endpoint detail) |
| `--json` | Machine-readable JSON |
| `--config PATH` | Alternate config file |

## Design

- **Read-only.** No `--apply`, no creds required, no side effects.
- **Parallel probes.** Total runtime bounded by slowest single check.
- **Graceful degradation.** Any single probe failure never blocks the others.
- **YAML-canonical** per [BUILDER_GUIDE.md](../BUILDER_GUIDE.md).

## Requirements

- Python 3.10+
- PyYAML

## License

Apache 2.0
