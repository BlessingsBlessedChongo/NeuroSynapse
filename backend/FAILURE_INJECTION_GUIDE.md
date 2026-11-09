# NeuroSynapse — Failure Injection Command Reference

All commands run from the `backend/` directory with the venv active:

```bash
cd backend
python manage.py inject_failure --device-type <type> --type <failure> [options]
```

Every command below was run for real against this codebase. Simulated and
PythonRouter commands were confirmed end-to-end (device correctly targeted,
failure context correctly recorded). FRR commands were confirmed to reach
the real SSH connection attempt correctly — they only fail in this
environment because no FRR container is reachable from here. Run them on a
machine with `docker compose up -d` and the container healthy.

---

## 1. Simulated Device (in-memory, database-backed)

No real network access — safe to run anywhere, anytime, heals in seconds.

```bash
# Service crash — a named process pegs CPU/memory
python manage.py inject_failure --device-type simulated --type service_crash --service-name nginx

# Link failure — an interface goes down
python manage.py inject_failure --device-type simulated --type link_failure --interface ether1

# DDoS attack — flood from a source IP
python manage.py inject_failure --device-type simulated --type ddos --source-ip 10.0.0.99
```

Optional context flags for any of the three: `--destination-ip`,
`--destination-port`, `--process-id`, `--traffic-volume`. Omit them and the
simulator fills in a realistic default (confirmed: `service_crash` above
picked `process_id: 4827` automatically, `ddos` picked a destination IP/port
and 75,000 pps automatically).

Target device: whichever `Device` row has `device_type=simulated`
(`SimRouter` by default). Use `--device-id <id>` if you have more than one
and need a specific one.

---

## 2. PythonRouter (realistic router simulator, database-backed)

Also safe to run anywhere — no real network access, heals in seconds.

```bash
python manage.py inject_failure --device-type python_router --type service_crash --service-name ospfd
python manage.py inject_failure --device-type python_router --type link_failure --interface eth0
python manage.py inject_failure --device-type python_router --type ddos --source-ip 10.0.0.99 --destination-port 443
```

`--device-type python_router` automatically prefers the canonical
`PyRouter-01` (127.0.0.2) row when more than one `python_router` device
exists in the database — confirmed. Use `--device-id` to be explicit if you
add more router instances.

Note: `eth0` is fine here — unlike FRR, PythonRouter's interfaces are pure
simulator state with no real SSH session to sever.

---

## 3. FRR (real Docker container, via SSH)

Requires the container to be up and reachable:

```bash
docker compose up -d
ssh admin@localhost -p 2222 "echo OK"   # sanity check first
```

```bash
# Service crash — stop the frr daemon
python manage.py inject_failure --device-type frr --type service_crash --service-name frr

# Link failure — MUST use eth1, not eth0 (see warning below)
python manage.py inject_failure --device-type frr --type link_failure --interface eth1

# DDoS attack — add an iptables DROP rule as if blocking is needed
python manage.py inject_failure --device-type frr --type ddos --source-ip 10.0.0.99
```

### ⚠️ Never use `--interface eth0` for FRR link_failure

`eth0` carries the SSH session NeuroSynapse itself needs to heal the
container. Confirmed live: the command refuses to run and explains why:

```
CommandError: Refusing to inject link_failure on 'eth0': it's the SSH
management interface in the single-NIC reference topology, so bringing
it down would sever the connection NeuroSynapse needs to heal it back...
```

This is a real safety guard, not a bug — it's on by default and only
applies to `device_type=frr`. If your compose file has a second NIC
(it does — see `docker-compose.yml`), always target `eth1` for FRR
link failures, confirmed working above.

`--force-mgmt-interface` exists to bypass the guard on purpose, but doing so
will genuinely make the container unreachable until you fix it manually
(`docker exec <container> ip link set eth0 up`) — not recommended.

### ⚠️ Only LINK_FAILURE is documented as reliable on real FRR

This is a real, existing limitation, not something introduced by recent
changes — it's documented directly in `inject_failure.py`'s own docstring:
stopping the `frr` daemon or adding an iptables rule on a bare Alpine
container does not reliably reproduce the CPU/bandwidth/packet-loss
telemetry signature the ML model was trained on the way the in-memory
simulators do. Budget for this if you're demoing all 9 combinations —
SERVICE_CRASH/DDOS_ATTACK against real FRR may show FAIL while
LINK_FAILURE (and everything on simulated/python_router) shows HEALED.

---

## Common flags (all device types)

| Flag | Purpose |
|---|---|
| `--device-id <id>` | Target one specific `Device` row by primary key |
| `--ip <address>` | Target by IP address instead of type/id |
| `--device-type <type>` | Target the canonical device of that type |
| `--all` | Inject into every matching device (combine with `--device-type` to scope it) |
| `--continue-on-error` | With `--all`: don't abort the batch on the first failure |
| `--interface <name>` | Interface for `link_failure` (default: `eth0` — override for FRR, see above) |
| `--service-name <name>` | Service for `service_crash` (default: `frr`) |
| `--source-ip`, `--source-port`, `--destination-ip`, `--destination-port`, `--process-id`, `--traffic-volume` | Optional context; simulators fill in realistic defaults if omitted |

## Verifying the failure actually healed

After any injection, run one orchestrator cycle and check the incident:

```bash
python manage.py shell -c "
from monitoring.models import Device, Incident
from ai_engine.orchestrator import orchestrator
device = Device.objects.get(device_type='simulated')  # or python_router / frr
orchestrator.run_cycle(device=device, monitor=True)
incident = Incident.objects.filter(device=device).order_by('-detected_at').first()
print(incident.status)
"
```

**Always pass `device=` explicitly.** `run_cycle(monitor=True)` with no
device argument silently monitors whichever `Device` row happens to be
first `ONLINE` in the database — not necessarily the one you just injected
a failure into. `test_live_healing.py` handles this correctly; write your
own one-off test scripts the same way.

Or use the master test script, which does all of the above correctly for
simulated and python_router, and probes FRR reachability before attempting
it (skipping cleanly instead of false-failing if the container isn't up):

```bash
python test_live_healing.py
```
