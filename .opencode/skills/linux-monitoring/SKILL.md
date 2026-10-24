---
name: linux-monitoring
description: >
  Build and review Linux system health dashboards and metric collectors in Python
  using psutil and documented /proc, /sys and cgroup interfaces, structured with
  clean architecture. Use this skill whenever the user mentions system monitoring,
  health dashboard, CPU/memory/disk/network/process/temperature metrics, psutil,
  /proc or /sys parsing, resource usage, uptime, load average, alerts or
  thresholds, or exporting metrics (JSON, Prometheus, WebSocket), even if they do
  not say "monitoring" explicitly. Also use it when handling unsupported
  hardware, permission errors, containers, or when deciding whether a
  privileged operation is acceptable.
---

# Linux Monitoring Skill

Expert guidance for a **Linux system health dashboard**: accurate metric
collection, honest handling of missing data, least privilege, bounded resource
usage, and a clean-architecture codebase that is easy to test.

## 1. Non-negotiable rules

Each rule has a reason. Follow the reason, not just the letter.

| # | Rule | Why |
|---|------|-----|
| 1 | **Never fabricate a metric.** Unavailable means `None` / `Unavailable(reason)`, never `0`, never a guess. | A fake `0 °C` or `0 %` looks healthy and hides real failures. |
| 2 | **Run unprivileged by default.** Privileged paths are opt-in, isolated, documented. | A monitor with root is an attack surface and a blast radius. |
| 3 | **Use psutil and documented interfaces** (`/proc`, `/sys`, cgroup files). No `shell=True`, no scraping `top`/`df`/`free` output. | Shell output formats vary by distro and locale; they break silently. |
| 4 | **Every loop, buffer, queue and cache is bounded.** | A monitor must not become the thing that exhausts the host. |
| 5 | **Isolate failures per collector.** One failing collector never takes down the dashboard. | Partial data is far better than a blank screen. |
| 6 | **Tests never fake system values to look green.** Use injected fakes at the port boundary and label them as such. | Fixtures at the boundary are fine; fabricated production data is not. |

## 2. Workflow

1. **Define requirements**: metrics, refresh rate, retention window, target distros, container or bare metal, delivery (web, TUI, API).
2. **Design ports** (interfaces) in the domain/application layer before touching psutil.
3. **Implement adapters**: psutil collectors, then `/proc` or `/sys` fallbacks where psutil is insufficient.
4. **Add capability detection and error mapping** (unsupported, permission denied, transient failure).
5. **Add bounded sampling and history** (ring buffers, minimum interval).
6. **Add presentation layer** (API/UI/exporter) that depends only on use cases.
7. **Test** (unit, contract, integration, permission, overhead). See section 9.
8. **Document limitations** per metric (section 11).

## 3. Clean architecture layout

Dependencies point inward only: `presentation -> application -> domain`; `infrastructure` implements domain ports.

```
src/monitor/
├── domain/                  # Pure Python. No psutil, no I/O, no framework.
│   ├── entities.py          # CpuSnapshot, MemorySnapshot, DiskUsage, NetCounters, ProcessInfo, Alert
│   ├── value_objects.py     # Percent, Bytes, Rate, Timestamp (validated, immutable)
│   ├── result.py            # MetricResult = Ok[T] | Unavailable(reason, kind)
│   ├── errors.py            # UnsupportedMetric, PermissionDenied, TransientFailure
│   ├── thresholds.py        # Alert rules, pure functions
│   └── ports.py             # Protocols: CpuReader, MemoryReader, DiskReader, NetReader,
│                            #   ProcessReader, SensorReader, Clock, HistoryStore
├── application/             # Use cases / orchestration. Depends on domain only.
│   ├── collect_snapshot.py  # Runs collectors, isolates failures, builds SystemSnapshot
│   ├── sampler.py           # Bounded interval scheduler, rate calculation from deltas
│   ├── evaluate_alerts.py
│   └── dto.py               # Output models for presentation
├── infrastructure/          # Adapters. The only layer that imports psutil / reads /proc.
│   ├── psutil_cpu.py  psutil_memory.py  psutil_disk.py  psutil_network.py
│   ├── psutil_process.py  psutil_sensors.py
│   ├── procfs.py            # Documented /proc and /sys readers (fallbacks, pressure, cgroups)
│   ├── capabilities.py      # Detect what this host/user can actually read
│   ├── ring_buffer_store.py # In-memory bounded history
│   └── system_clock.py
├── presentation/            # Delivery. Depends on application DTOs only.
│   ├── api/ (FastAPI)  or  tui/ (Textual/Rich)
│   ├── exporters/           # JSON, Prometheus text format
│   └── serializers.py
├── config/                  # Settings model, defaults, validation
│   └── settings.py
├── composition.py           # The ONLY place that wires adapters into use cases
└── __main__.py
tests/
├── unit/  contract/  integration/  permissions/  performance/
```

**Design rules**

- Domain and application code must be importable and testable without psutil installed.
- Inject dependencies through constructors; no module-level singletons or hidden globals.
- Collectors return `MetricResult`, never raise to the caller for expected conditions (unsupported, permission).
- Keep entities immutable (`dataclass(frozen=True, slots=True)`); validate in value objects.
- Use `Protocol` for ports; one **contract test suite** runs against every adapter implementation.

## 4. Metric collection

### 4.1 CPU

- `psutil.cpu_percent(interval=None, percpu=True)`: **the first call returns a meaningless `0.0`**. Prime it once at startup and discard, then call non-blocking on each sample. Never use a blocking `interval=1` inside a request handler.
- `psutil.cpu_times_percent`, `psutil.cpu_count(logical=True/False)`, `psutil.cpu_freq()` (may return `None` or raise on some VMs/ARM).
- `os.getloadavg()`: load average is not a percentage; show it alongside core count.
- `psutil.cpu_stats()` for context switches and interrupts (optional).
- Pressure Stall Information: `/proc/pressure/cpu` (kernel 4.20+, may be disabled): optional, capability-gated.

### 4.2 Memory

- `psutil.virtual_memory()`: use **`available`**, not `free`, for "memory in use". Linux caches aggressively; `free` is misleadingly small.
- `psutil.swap_memory()`: handle hosts with swap disabled (`total == 0`) without dividing by zero.
- Per-process memory: prefer **PSS/USS** (`memory_full_info()`) only when permitted; RSS is the unprivileged default and double-counts shared pages. Label which one is shown.
- PSI: `/proc/pressure/memory`, optional.

### 4.3 Disk

- `psutil.disk_partitions(all=False)`; **filter pseudo filesystems** (`tmpfs`, `proc`, `sysfs`, `overlay` unless wanted, `squashfs` snap mounts) to avoid noise.
- `psutil.disk_usage(mountpoint)` per mount; catch `PermissionError` and `OSError` per mount (stale NFS can hang: use a timeout wrapper or worker thread).
- `psutil.disk_io_counters(perdisk=True)`: counters are cumulative; **compute rates from deltas** and handle counter resets (negative delta -> discard sample).
- Report inode usage (`os.statvfs`) in addition to bytes; inode exhaustion is a classic outage.
- SMART data requires root and `smartctl`: treat as **privileged optional** (section 7).

### 4.4 Network

- `psutil.net_io_counters(pernic=True)`: cumulative; compute bytes/s from deltas, handle wraparound and interface reset.
- `psutil.net_if_stats()` (up/down, speed; speed can be `0` meaning unknown -> `None`).
- `psutil.net_if_addrs()` for addresses.
- `psutil.net_connections()` **needs root to see other users' PIDs** on Linux. Without root, return the visible subset and mark the result `partial=True`.
- Exclude loopback by default; make it configurable.

### 4.5 Processes

- Iterate with `psutil.process_iter(attrs=[...])`: request only needed attributes.
- Expect and handle `NoSuchProcess`, `AccessDenied`, `ZombieProcess` per process; skip silently, count them in a `skipped` field.
- `cpu_percent` per process has the same priming rule as 4.1; keep Process objects between samples.
- **Bound the output**: top N (default 10-25) by CPU or memory, never the full list over the wire.
- **Redact command lines** by default (they often contain tokens and passwords). Expose a setting to enable them.

### 4.6 Sensors and optional hardware

- `psutil.sensors_temperatures()`, `sensors_fans()`, `sensors_battery()` exist only on some platforms; use `hasattr` checks and catch exceptions. Many servers, VMs and containers have none.
- Return `Unavailable(kind=UNSUPPORTED, reason="no thermal sensors exposed")`, never a placeholder number.
- GPU, NVMe vendor data, IPMI: out of default scope; add only behind an explicit adapter with an approval note (section 7).

### 4.7 System info

- Uptime/boot time (`psutil.boot_time()`), kernel (`platform.release()`), distro (`/etc/os-release` parse), hostname, logged-in users (optional).
- Open file descriptor and `ulimit` usage per process or system (`/proc/sys/fs/file-nr`): a useful health signal.

## 5. Containers and virtualization

A health dashboard that ignores containers reports wrong numbers inside Docker/Kubernetes.

- Detect cgroup version (`/sys/fs/cgroup/cgroup.controllers` exists -> v2).
- Inside a container, psutil's `virtual_memory()` and `cpu_count()` often report **host** values. For limits, read cgroup files: `memory.max` / `memory.current` (v2), `memory.limit_in_bytes` (v1), `cpu.max`, `cpu.stat`. Value `max` means unlimited.
- Expose a `scope` field (`host` or `cgroup`) so the UI never mixes them.
- Support `HOST_PROC` / `HOST_SYS` style overrides (psutil honors `psutil.PROCFS_PATH`) when the host filesystem is mounted read-only into the container.
- Document that PID, network and mount namespaces limit what is visible.

## 6. Error handling model

Use a typed result, not exceptions as control flow and not magic fallback numbers.

```python
# domain/result.py
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar("T")

class UnavailableKind(Enum):
    UNSUPPORTED = "unsupported"        # hardware/kernel does not provide it
    PERMISSION_DENIED = "permission"   # needs more privilege
    TRANSIENT = "transient"            # may succeed on next sample
    DISABLED = "disabled"              # turned off by configuration

@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T
    partial: bool = False              # True when only a visible subset was readable

@dataclass(frozen=True, slots=True)
class Unavailable:
    kind: UnavailableKind
    reason: str                        # short, safe, user-displayable

MetricResult = Ok[T] | Unavailable
```

- **Adapter** catches `psutil.AccessDenied`, `PermissionError`, `AttributeError` (missing API), `NotImplementedError`, `OSError`, and maps each to the right `UnavailableKind`.
- **Application** aggregates results; one `Unavailable` never fails the snapshot.
- **Presentation** renders `Unavailable` explicitly ("Not supported on this host"), never as `0` or blank.
- **Transient** failures: retry on the next scheduled sample with capped backoff; do not retry in a tight loop.
- Log the technical detail at DEBUG/WARNING (with rate limiting); show the user only the safe `reason`. Never expose paths, usernames or stack traces over the API.

## 7. Privileged operations and approval gates

Keep privileged code out of default paths. A privileged feature must be:

1. **Opt-in** via explicit configuration (default off).
2. **Isolated** in its own adapter module and, preferably, a separate helper process with a minimal allowlisted command set; never run the whole app as root.
3. **Documented** (what it reads, why root is needed).
4. **Logged** when enabled and when used.

**Ask the user for approval before** any of the following:

- Adding a privileged call (`sudo`, setuid helper, capabilities such as `CAP_NET_ADMIN`/`CAP_SYS_PTRACE`, reading other users' `/proc/<pid>/fd`).
- Changing the default collection frequency or minimum interval.
- Adding hardware-specific dependencies (NVML, `smartctl`, IPMI, vendor SDKs).
- Implementing system-level security features (auth, TLS termination, firewall rules).
- Adding any write operation to the host (kill process, restart service). The default product is **read-only**.

## 8. Sampling, performance and bounded resources

- Enforce a **minimum sampling interval** (default 1 s, hard floor configurable but approved per section 7) so clients cannot trigger a collection storm.
- **One sampler, many consumers.** Collect once per interval into a shared latest-snapshot; API requests read the cache. Never collect per HTTP request.
- Keep history in a **fixed-size ring buffer** (e.g. `collections.deque(maxlen=N)`); define retention as `window_seconds / interval`.
- Rate metrics (disk, network) need two samples; the first reading yields `None` for the rate, not `0`.
- Use a monotonic clock (`time.monotonic()`) for deltas, wall clock only for display.
- Slow collectors (disk usage on many mounts, `net_connections`) run on a worker thread or at a lower frequency with their own timeout.
- Cap payload sizes (top-N processes, max mounts, max interfaces).
- Target and measure: monitor's own CPU < 1-2 % and RSS stable over 24 h on a reference host. Expose the monitor's own metrics (collection duration, error count) as first-class data.

## 9. Testing strategy

| Layer | What to test | How |
|-------|--------------|-----|
| Unit (domain) | Value objects, thresholds, rate math, counter-reset handling | Pure pytest, no mocks needed |
| Unit (application) | Failure isolation, aggregation, interval floor | Fake ports (in-memory implementations) |
| Contract | Every adapter honors its port: types, units, `Unavailable` mapping | One shared test class parametrized over real and fake adapters |
| Adapter | psutil mapping, `/proc` parsing | Monkeypatch psutil to raise `AccessDenied`, return `None`, lack `sensors_*`; parse **recorded real** `/proc` samples stored under `tests/fixtures/` |
| Permissions | Behavior as non-root and with denied paths | Run in CI as unprivileged user; assert `Unavailable(PERMISSION_DENIED)` and `partial=True` |
| Integration | Collector -> sampler -> API end to end on the real host | Assert shapes and ranges (`0 <= percent <= 100`), not exact values |
| Edge cases | No swap, no sensors, 1 CPU, hundreds of cores, hung mount, counter wrap, container cgroup limits, PSI disabled | Parametrized fixtures |
| Performance | Collection duration, memory growth, CPU overhead | `pytest-benchmark`, soak test with `tracemalloc` |
| Security | Command-line redaction, no stack traces in responses, bind address default | API tests |

Tooling: `pytest`, `pytest-cov` (target >= 85 % on domain and application), `pytest-asyncio` if async, `hypothesis` for rate/delta math, `ruff`, `mypy --strict`, `import-linter` to **enforce the dependency direction** in section 3.

Fixture rule: recorded real samples and explicit fakes at the port boundary are allowed. Hard-coded values inside production code are not.

## 10. Presentation and security

- **Bind to `127.0.0.1` by default.** Exposing on `0.0.0.0` requires explicit config plus authentication (token or reverse proxy). System metrics reveal useful reconnaissance data.
- Read-only API; validate every query parameter (limits, intervals, sort keys) against allowlists.
- CORS closed by default; set security headers; no verbose errors.
- Serialize `Unavailable` states in the schema (`{"status": "unavailable", "kind": "permission", "reason": "..."}`) so any client can render them correctly.
- Version the API schema (`/api/v1`) and keep units explicit (`bytes`, `percent`, `seconds`).
- Optional exporters: Prometheus text format with `# HELP`/`# TYPE`, base units, and **absent series instead of zero** for unavailable metrics.
- Dashboard UX: show units, last-updated time, staleness indicator when the sampler stalls, and a visible "partial data" badge.

## 11. Configuration, logging, deployment

- Typed settings (e.g. `pydantic-settings`) with validation and safe defaults; env vars override file.
- Structured logging (JSON option), log levels per module, rate-limited repeated errors, no secrets in logs.
- Graceful shutdown: stop sampler, flush exporters, no orphan threads.
- Packaging: `pyproject.toml`, pinned minimum psutil version (state it), supported Python versions, lockfile.
- Run as a **systemd service** with a dedicated unprivileged user and hardening (`NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp=yes`, `ReadOnlyPaths=`); provide the unit file in `deploy/`.
- Docker: non-root user, read-only root filesystem, document required mounts for host visibility.
- Supported platforms: Linux only. Test on at least one Debian-family and one RHEL-family distro, and kernel with and without PSI.

## 12. Common pitfalls

- Treating `free` memory as "unused" instead of `available`.
- Calling `cpu_percent()` for the first time and displaying `0.0`.
- Showing cumulative counters as if they were rates.
- Dividing by zero when swap, a mount, or link speed is `0`.
- Averaging percentages across cores or mounts incorrectly (weight by capacity).
- Listing every process or every pseudo-filesystem.
- Letting `disk_usage()` on a stale NFS mount hang the whole collector.
- Collecting inside the request handler.
- Using host values inside a container.
- Running everything as root "to avoid permission errors".
- Substituting `0` or random values when a sensor is missing.
- Parsing command output (`df`, `free`, `top`, `sensors`) instead of using APIs.
- Letting domain code import psutil, which destroys testability.

## 13. Definition of done

- [ ] All core metrics (CPU, memory, disk, network, processes, uptime/load) collected and cross-checked against a trusted tool (`top`, `free -b`, `df`, `ip -s`) within tolerance.
- [ ] Every collector returns `MetricResult`; no placeholder values anywhere in production code.
- [ ] Unsupported hardware, permission denial, missing swap, missing sensors, container limits all covered by tests.
- [ ] `import-linter` passes: domain and application do not import infrastructure or psutil.
- [ ] Runs fully as an unprivileged user; privileged features are off by default and documented.
- [ ] Sampler bounded: interval floor, ring buffer, top-N, timeouts, stable memory over a soak test.
- [ ] `mypy --strict`, `ruff`, and the test suite pass in CI on supported distros.
- [ ] Limitations documented per metric (what is unavailable without root, in containers, on VMs).
- [ ] API binds to localhost by default; error responses leak no internal detail.

## 14. Metric limitations template (copy into project docs)

| Metric | Source | Needs root? | Unsupported when | Container behavior | Notes |
|--------|--------|-------------|------------------|--------------------|-------|
| CPU % | `psutil.cpu_percent` | No | Never | Host-wide unless cgroup read | Prime first call |
| Memory available | `psutil.virtual_memory` | No | Never | Host values; use cgroup | Not `free` |
| Per-process PSS | `memory_full_info` | Often | Restricted `/proc` | Namespace-limited | Fallback RSS, labeled |
| Disk SMART | `smartctl` | Yes | No SMART device, VMs | Usually none | Privileged optional |
| Temperature | `sensors_temperatures` | No | VMs, many servers | Often none | `Unavailable`, never 0 |
| All connections | `net_connections` | For other users | Never | Own namespace only | `partial=True` |
| PSI | `/proc/pressure/*` | No | Kernel < 4.20 or disabled | Via cgroup files | Capability-gated |

## 15. Dependencies

**Core:** `psutil`

**Presentation (choose one):** `fastapi` + `uvicorn`, or `textual` / `rich`

**Config and validation:** `pydantic`, `pydantic-settings`

**Dev:** `pytest`, `pytest-cov`, `pytest-asyncio` (if async), `pytest-benchmark`, `hypothesis`, `ruff`, `mypy`, `import-linter`

Do not add wrapper libraries around psutil or generic "metrics" packages; they add dependency risk without capability. New hardware-specific dependencies require approval (section 7).