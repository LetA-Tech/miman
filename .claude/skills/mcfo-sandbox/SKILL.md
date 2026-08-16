---
name: mcfo-sandbox
description: Use whenever a task on Lucas's Mac needs a container — a database to test against, a broker, a one-off image, an integration test that requires real infrastructure. Triggers on "spin up postgres", "start a container", "run the integration tests", "test against a real database", "docker run", "docker compose up", "bring up the stack", "I need redis/redpanda/mongo locally". Provides an empty, resource-capped, disposable sandbox via `mcfo-sbx` so agent workloads cannot exhaust the host. Do NOT use for containers on remote hosts (the LETA droplet manages its own), or for reasoning about production infrastructure.
---

# mcfo-sandbox

## Applies only where `mcfo-sbx` exists

```bash
command -v mcfo-sbx
```

Empty result means this is **not** the workstation this skill governs — a CI runner, the LETA
droplet, or a dispatched container. Stop and use that host's own conventions; nothing below
applies. The droplet in particular runs its own gVisor-isolated Docker and must not be driven
through this skill.

The governed workstation is a **16 GiB M4** that has crashed repeatedly from memory exhaustion.
Containers must never be started on it outside this sandbox.

## The rule

**Never run bare `docker run`, `docker compose up`, or `colima start`.** Use `mcfo-sbx`.
It applies resource caps that cannot be forgotten and it makes teardown verifiable.

**Teardown belongs to the turn that provisioned.** Not "later", not "at the end of
the session". If a test is the deliverable, the deliverable is not complete until
`mcfo-sbx down` has reported zero.

## Commands

```bash
mcfo-sbx up                      # start Colima (5 CPU / 6 GiB, persisted config)
mcfo-sbx run [caps] -- ARGS...   # docker run with caps; auto-starts Colima
mcfo-sbx status                  # what runs, what it costs, budget left
mcfo-sbx down                    # destroy everything, stop Colima, verify zero
mcfo-sbx nuke                    # also delete the VM disk (asks first)
```

Caps default to `--mem 1g --cpu 1.0 --pids 512` and may be raised per task.
Everything after `--` goes to `docker run` verbatim:

```bash
mcfo-sbx run -- -d --name sbx-pg -e POSTGRES_PASSWORD=test postgres:17-alpine
mcfo-sbx run --mem 2g -- --rm -v "$PWD:/w" -w /w golang:1.26 go test ./...
```

## Resource envelope

The Colima VM caps at **5 CPU / 6 GiB**. Inside it, **4 GiB** is available to
containers — 2 GiB is reserved for dockerd, buildkit and page cache. `run` sums
the memory limits of running containers and **refuses** anything that would breach
4 GiB, so the concurrency ceiling is enforced rather than remembered.

At the 1 GiB default that is **up to 4 concurrent containers**.

Idle state is **Colima stopped** — zero host CPU, zero host memory. Only the VM's
sparse disk file remains, and it is near-empty because `down` removes all images.

## Bash sandbox interaction

Claude Code's sandboxed Bash **cannot reach the Colima socket**:

```
permission denied while trying to connect to the docker API at
unix:///Users/lucas/.colima/default/docker.sock
```

That is expected. Any `mcfo-sbx` or `docker` call needs `dangerouslyDisableSandbox: true`.
The error means "sandboxed shell", never "Docker is broken".

## What `down` destroys

Every container, volume, custom network, image and the build cache **inside the VM** —
not only what this script started. The VM is dedicated to this sandbox, so that is
correct. It is also why nothing of value should ever be stored inside it.

`down` verifies rather than assumes, and exits non-zero naming anything that survived.
Report those numbers; never claim clean without them.

## Boundaries

- Nothing is preinstalled. No service catalogue, no compose stack, no observability.
  Pull only what the current task needs.
- Do not add resource limits to `mcfo-*` repo compose files as a way of managing the
  host. Those repos deploy to servers; host resource management lives here.
- `nuke` deletes the VM. Ask Lucas first — it is not part of routine teardown.
- Approval to start the sandbox is **per task, never standing**.

## The caps do not fix the crashes

Measured from nine `JetsamEvent` reports: every crash was
`vm-compressor-space-shortage` driven by **host-side `node` processes** (132 procs /
16.56 GiB at worst) plus the Android emulator. **No Docker process appeared in any
crash.** macOS has no cgroups, so Claude Code's own fan-out on the host remains
uncapped and this sandbox does not address it. Keep MCP server count and subagent
fan-out modest regardless of what the sandbox reports.
