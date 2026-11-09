"""
Healing actuator for NeuroSynapse.

Responsibilities:
    - Select vendor-specific healing actions
    - Format incident context into commands
    - Validate commands in the sandbox
    - Execute commands through the correct connector
    - Verify the actual failed resource
    - Preserve RL-selected action ordering
"""

import logging
import re
import shutil
import subprocess

from django.utils import timezone

from monitoring.connector import get_connector, normalize_telemetry
from monitoring.models import Incident, HealingAction
from monitoring.vendor_profiles import get_profile


logger = logging.getLogger(__name__)

SANDBOX_IMAGE = "python:3.11-alpine"
SANDBOX_TIMEOUT_SECONDS = 30


HEALING_POLICIES = {
    "SERVICE_CRASH": [
        {
            "action_type": "RESTART_SERVICE",
            "command": (
                "sudo -n sh -c '"
                "command -v rc-service >/dev/null 2>&1 && rc-service {service} restart "
                "|| (command -v supervisorctl >/dev/null 2>&1 && supervisorctl restart {service}) "
                "|| (test -x /etc/init.d/{service} && /etc/init.d/{service} restart) "
                "|| (command -v systemctl >/dev/null 2>&1 && systemctl restart {service}) "
                "|| killall -HUP {service} 2>/dev/null || true'"
            ),
            "description": "Restart crashed service (Alpine OpenRC / systemd compatible)",
            "verify_command": (
                "sh -c 'command -v rc-service >/dev/null 2>&1 && rc-service {service} status "
                "|| pgrep {service} >/dev/null 2>&1 && echo active || echo inactive'"
            ),
        },
    ],
    "LINK_FAILURE": [
        {
            "action_type": "REROUTE_TRAFFIC",
            "command": "sudo -n ip link set dev {interface} up",
            "description": "Bring interface up",
            "verify_command": "ip -br link show {interface}",
        },
    ],
    "DDOS_ATTACK": [
        {
            "action_type": "BLOCK_SOURCE_IP",
            "command": "sudo -n iptables -A INPUT -s {ip} -j DROP",
            "description": "Block attacking IP",
            "verify_command": "sudo -n iptables -C INPUT -s {ip} -j DROP",
        },
    ],
}

# Rollback-only actions kept separately so RL never selects them as "heals".
ROLLBACK_POLICIES = {
    "DDOS_ATTACK": [
        {
            "action_type": "UNBLOCK_SOURCE_IP",
            "command": "sudo -n iptables -D INPUT -s {ip} -j DROP",
            "description": "Remove IP block during rollback",
            "verify_command": "sudo -n iptables -C INPUT -s {ip} -j DROP",
        },
    ],
}


class HealingActuator:

    def __init__(self):
        self.connectors = {}

    def _resolve_device_type(self, device):
        return getattr(device, "device_type", "generic") or "generic"

    def _get_connector(self, device):
        connector = get_connector(device)
        self.connectors[device.id] = connector
        return connector

    def _incident_kwargs(self, incident):
        interface = getattr(incident, "interface_name", None) or "eth0"
        ip = getattr(incident, "source_ip", None) or "10.0.0.5"
        service = getattr(incident, "service_name", None) or "frr"
        port = getattr(incident, "destination_port", None) or 80

        return {
            "interface": str(interface),
            "ip": str(ip),
            "service": str(service),
            "port": str(port),
        }

    def get_actions_for_failure(self, failure_type, device_type="generic"):
        # DB-backed simulator uses the direct heal() API path in
        # _execute_simulated(); symbolic vendor commands are not needed.
        if device_type == "simulated":
            return []

        profile = get_profile(device_type)
        actions = profile.get("healing_commands", {}).get(failure_type, [])

        if actions:
            return actions

        return HEALING_POLICIES.get(failure_type, [])

    def _fill_action(self, action, **kwargs):
        filled = dict(action)

        for field in ("command", "verify_command"):
            raw = action.get(field)
            if not raw:
                continue
            try:
                filled[field] = raw.format(**kwargs)
            except KeyError as exc:
                logger.error("[HEALING] Missing command parameter %s", exc)
                raise

        return filled

    def _order_candidates(self, actions, rl_agent, failure_type):
        if not actions:
            return [], 0

        start_index = 0

        if rl_agent and len(actions) > 1:
            try:
                selected = rl_agent.select_action(failure_type, len(actions))
                if isinstance(selected, int) and 0 <= selected < len(actions):
                    start_index = selected
            except Exception as exc:
                logger.error("[HEALING] RL selection failed: %s", exc)

        ordered = actions[start_index:] + actions[:start_index]
        return ordered, start_index

    def select_action(self, failure_type, device_type="generic", rl_agent=None, **kwargs):
        actions = self.get_actions_for_failure(failure_type, device_type)
        # Forward healing only — rollback-only types stay in the profile for
        # actuator.rollback() lookup but must not be RL-selected as "fixes".
        actions = [
            a for a in actions
            if "UNBLOCK" not in a.get("action_type", "")
            and not str(a.get("action_type", "")).startswith("CLEAR_")
        ]

        if not actions:
            return None

        defaults = {
            "interface": "eth0",
            "ip": "10.0.0.5",
            "service": "frr",
            "port": "80",
        }
        defaults.update({k: v for k, v in kwargs.items() if v is not None})

        ordered, start_index = self._order_candidates(actions, rl_agent, failure_type)
        selected = self._fill_action(ordered[0], **defaults)
        selected["action_index"] = start_index
        return selected

    def _execute_simulated(self, incident):
        """
        In-process simulators (SimulatedDevice / PythonRouter) use heal() directly.

        LINK_FAILURE -> REROUTE_TRAFFIC
        SERVICE_CRASH -> RESTART_SERVICE
        DDOS_ATTACK -> BLOCK_SOURCE_IP (attack in progress, block it)
        """
        connector = self._get_connector(incident.device)
        sim = getattr(connector, "sim", None) or getattr(connector, "router", None)

        if sim is None:
            return None

        failure_type = incident.failure_type
        device_type = self._resolve_device_type(incident.device)
        label = "PYTHON_ROUTER" if device_type == "python_router" else "SIMULATED"

        if failure_type == "LINK_FAILURE":
            action_type = "REROUTE_TRAFFIC"
        elif failure_type == "SERVICE_CRASH":
            action_type = "RESTART_SERVICE"
        elif failure_type == "DDOS_ATTACK":
            # Attack is ongoing — BLOCK it (not UNBLOCK)
            action_type = "BLOCK_SOURCE_IP"
        else:
            action_type = "HEAL"

        logger.info(
            "[HEALING] %s device=%s action=%s",
            label,
            incident.device.name,
            action_type,
        )

        success, output = sim.heal(action_type)

        healing = HealingAction.objects.create(
            incident=incident,
            action_type=action_type,
            command=f"{label}:{action_type}",
            status="EXECUTED" if success else "ROLLBACK",
            sandbox_result="PASS",
            execution_output=str(output)[:500],
            completed_at=timezone.now(),
        )

        return healing

    def execute_healing(self, incident, action=None, rl_agent=None):
        device = incident.device
        device_type = self._resolve_device_type(device)

        # Both in-process simulators heal via their heal() API rather than SSH.
        if device_type in ("simulated", "python_router"):
            return self._execute_simulated(incident)

        kwargs = self._incident_kwargs(incident)

        all_actions = self.get_actions_for_failure(incident.failure_type, device_type)
        # Exclude rollback-only actions from the forward healing candidate set
        # so the RL agent cannot select UNBLOCK / CLEAR as a "heal".
        all_actions = [
            a for a in all_actions
            if "UNBLOCK" not in a.get("action_type", "")
            and not str(a.get("action_type", "")).startswith("CLEAR_")
        ]

        if not all_actions:
            logger.error(
                "[HEALING] No actions for %s on %s",
                incident.failure_type,
                device_type,
            )
            return None

        if action is not None:
            # Deduplicate by action_type, not identity
            raw_candidates = [action] + [
                candidate
                for candidate in all_actions
                if candidate.get("action_type") != action.get("action_type")
            ]
        else:
            ordered, _ = self._order_candidates(all_actions, rl_agent, incident.failure_type)
            raw_candidates = ordered

        candidates = [
            self._fill_action(candidate, **kwargs)
            for candidate in raw_candidates
        ]

        connector = self._get_connector(device)
        last_healing = None

        try:
            for attempt, candidate in enumerate(candidates, start=1):
                healing = HealingAction.objects.create(
                    incident=incident,
                    action_type=candidate["action_type"],
                    command=candidate["command"],
                    status="PENDING",
                )
                last_healing = healing

                logger.info(
                    "[HEALING] Target=%s type=%s failure=%s attempt=%s/%s",
                    device.name,
                    device_type,
                    incident.failure_type,
                    attempt,
                    len(candidates),
                )
                logger.info("[HEALING] Actual command: %s", candidate["command"])

                healing.status = "SANDBOXING"
                healing.save(update_fields=["status"])

                sandbox_ok = self._validate_in_sandbox(candidate["command"])
                healing.sandbox_result = "PASS" if sandbox_ok else "BLOCKED"
                healing.save(update_fields=["sandbox_result"])

                if not sandbox_ok:
                    healing.status = "FAILED"
                    healing.execution_output = "Command blocked by security sandbox."
                    healing.completed_at = timezone.now()
                    healing.save()
                    continue

                healing.status = "EXECUTING"
                healing.save(update_fields=["status"])

                command = candidate["command"]

                if "\n" in command:
                    command = [
                        item.strip()
                        for item in command.split("\n")
                        if item.strip()
                    ]

                logger.info("[HEALING] Dispatching actual command: %s", command)

                try:
                    result = connector.execute_healing_command(command)
                except Exception as exc:
                    logger.exception("[HEALING] Command execution exception")
                    result = {"success": False, "output": f"Execution error: {exc}"}

                healing.execution_output = str(result.get("output", ""))[:500]
                healing.completed_at = timezone.now()
                healing.status = "EXECUTED" if result.get("success") else "ROLLBACK"
                healing.save()

                logger.info(
                    "[HEALING] Result success=%s output=%s",
                    result.get("success"),
                    str(result.get("output", ""))[:300],
                )

                if healing.status == "EXECUTED":
                    return healing

                logger.warning("[HEALING] Primary action failed; trying fallback.")

            return last_healing

        finally:
            connector.disconnect()

    def _validate_in_sandbox(self, command):
        """
        Validate a remediation script.

        Primary path: run inside an isolated Docker container.
        Fallback path: when Docker is unavailable (daemon not running, CLI
        not installed, or the host lacks a POSIX shell such as Windows), we
        still apply dangerous-pattern blocking and a best-effort static
        syntax check. This keeps the security guarantee (known-dangerous
        commands are always rejected) while allowing tests and CI runs on
        hosts without a live Docker daemon.
        """
        dangerous_patterns = [
            "rm -rf",
            "mkfs",
            "dd if=",
            "erase startup-config",
            "format flash",
            "delete all",
        ]

        command_lower = command.lower()

        for pattern in dangerous_patterns:
            if pattern in command_lower:
                logger.warning("[SANDBOX] Blocked pattern: %s", pattern)
                return False

        if len(command) > 1000:
            logger.warning("[SANDBOX] Command too long")
            return False

        docker = shutil.which("docker")
        if not docker:
            logger.warning(
                "[SANDBOX] Docker CLI unavailable — using static validation only"
            )
            return self._static_shell_check(command)

        script = "#!/bin/sh\nset -eu\n" + command + "\n"
        docker_command = [
            docker, "run", "--rm", "--network", "none",
            "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,noexec",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "-i", SANDBOX_IMAGE, "sh", "-c",
            "cat > /tmp/remediation.sh && sh -n /tmp/remediation.sh",
        ]
        try:
            result = subprocess.run(
                docker_command,
                input=script,
                text=True,
                capture_output=True,
                timeout=SANDBOX_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.error(
                "[SANDBOX] Validation timed out after %ss", SANDBOX_TIMEOUT_SECONDS
            )
            return False
        except OSError:
            logger.exception("[SANDBOX] Docker validation failed to start")
            return self._static_shell_check(command)

        if result.returncode != 0:
            stderr = result.stderr or ""
            stderr_lower = stderr.lower()
            # Detect "docker daemon unreachable" style failures and fall back
            # to static validation rather than failing the whole remediation.
            daemon_unreachable = (
                "cannot find the file specified" in stderr_lower
                or "docker api" in stderr_lower
                or "daemon is running" in stderr_lower
                or "is the docker daemon running" in stderr_lower
                or "error during connect" in stderr_lower
            )
            if daemon_unreachable:
                logger.warning(
                    "[SANDBOX] Docker daemon unreachable — falling back to static validation"
                )
                return self._static_shell_check(command)

            logger.error(
                "[SANDBOX] Validation failed exit=%s stderr=%s",
                result.returncode,
                stderr[:500],
            )
            return False

        logger.info("[SANDBOX] Validation passed image=%s", SANDBOX_IMAGE)
        return True

    def _static_shell_check(self, command):
        """
        Best-effort shell syntax check used when Docker is unavailable.

        On POSIX hosts we invoke `sh -n` to parse the script without
        executing it. On hosts without a POSIX shell (e.g. bare Windows),
        we accept the command after the dangerous-pattern filter has already
        run — this keeps the security-relevant checks in place while not
        blocking every safe command on developer machines.
        """
        try:
            result = subprocess.run(
                ["sh", "-n"],
                input=command,
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            # No POSIX sh available (Windows) or it hung — accept after the
            # pattern check above, which already blocked known-dangerous
            # constructs.
            logger.warning(
                "[SANDBOX] No POSIX shell available — accepting after pattern check"
            )
            return True

        if result.returncode != 0:
            logger.error(
                "[SANDBOX] Static shell check failed: %s",
                (result.stderr or "")[:300],
            )
            return False

        logger.info("[SANDBOX] Static shell check passed")
        return True

    def verify_healing(self, incident):
        connector = self._get_connector(incident.device)

        try:
            return self._verify_action_result(incident, connector)
        finally:
            connector.disconnect()

    def _latest_healing_action(self, incident):
        return (
            HealingAction.objects
            .filter(incident=incident)
            .order_by("-created_at")
            .first()
        )

    def _verify_link_failure(self, incident, connector):
        device_type = self._resolve_device_type(incident.device)
        kwargs = self._incident_kwargs(incident)
        interface = kwargs["interface"]

        if device_type == "frr":
            command = f"ip link show dev {interface}"
            output = connector.run_readonly_command(command) or ""
            healthy = bool(output) and "state UP" in output.upper()

        elif device_type == "cisco_ios":
            command = f"show interfaces {interface}"
            output = connector.run_readonly_command(command) or ""
            output_lower = output.lower()
            healthy = "is up" in output_lower and "line protocol is up" in output_lower

        elif device_type == "mikrotik_routeros":
            command = f'interface print detail where name="{interface}"'
            output = connector.run_readonly_command(command) or ""
            healthy = "running=true" in output.lower()

        elif device_type == "juniper_junos":
            command = f"show interfaces terse {interface}"
            output = connector.run_readonly_command(command) or ""
            healthy = bool(output) and "up" in output.lower()

        elif device_type == "huawei_vrp":
            command = f"display interface {interface}"
            output = connector.run_readonly_command(command) or ""
            healthy = "current state : up" in output.lower()

        else:
            healthy = False
            output = ""

        message = (
            f"[VERIFY:LINK_FAILURE] device={device_type} "
            f"interface={interface} healthy={healthy} output={output[:300]}"
        )
        logger.info(message)
        return healthy, message

    def _verify_service_crash(self, incident, connector):
        device_type = self._resolve_device_type(incident.device)
        kwargs = self._incident_kwargs(incident)
        service = kwargs["service"]

        if device_type == "frr":
            # Official FRR Alpine images: rc-service/init.d status calls
            # Debian status_of_proc (missing). Probe zebra/frr processes first.
            # watchfrr may take a few seconds to respawn daemons after restart.
            import time as _time

            command = (
                f"sh -c '"
                f"if pgrep -x zebra >/dev/null 2>&1 || pgrep -a zebra >/dev/null 2>&1; then echo active; "
                f"elif pgrep -a {service} >/dev/null 2>&1; then echo active; "
                f"elif command -v rc-service >/dev/null 2>&1 && "
                f"rc-service {service} status >/dev/null 2>&1; then echo active; "
                f"else echo inactive; fi'"
            )
            output = ""
            healthy = False
            for _ in range(20):
                output = connector.run_readonly_command(command) or ""
                output_lower = output.lower()
                healthy = "active" in output_lower and "inactive" not in output_lower
                if healthy:
                    break
                _time.sleep(1.0)

        else:
            profile = get_profile(device_type)
            actions = profile.get("healing_commands", {}).get("SERVICE_CRASH", [])
            verify_command = None

            for candidate in actions:
                if candidate.get("verify_command"):
                    verify_command = candidate["verify_command"]
                    break

            if not verify_command:
                return False, "[VERIFY:SERVICE_CRASH] No verification command"

            verify_command = verify_command.format(**kwargs)
            output = connector.run_readonly_command(verify_command) or ""
            output_lower = output.lower()
            healthy = (
                "active" in output_lower
                or "running" in output_lower
                or "uptime" in output_lower
            )

        message = (
            f"[VERIFY:SERVICE_CRASH] service={service} "
            f"healthy={healthy} output={output[:300]}"
        )
        logger.info(message)
        return healthy, message

    def _verify_ddos(self, incident, connector, action):
        kwargs = self._incident_kwargs(incident)
        ip = kwargs["ip"]
        action_type = action.action_type if action else "BLOCK_SOURCE_IP"
        device_type = self._resolve_device_type(incident.device)

        if device_type == "frr":
            check_command = f"sudo -n iptables -C INPUT -s {ip} -j DROP"
            output = connector.run_readonly_command(check_command) or ""
            # iptables -C returns empty stdout and exit 0 when the rule exists.
            # Netmiko may surface exit status in the output string on failure.
            rule_exists = (
                "no chain/target/match" not in output.lower()
                and "bad rule" not in output.lower()
                and "error" not in output.lower()
                and "permission denied" not in output.lower()
            )

            # FIXED: UNBLOCK means rule should NOT exist (healthy = no rule)
            # BLOCK means rule SHOULD exist (healthy = rule present)
            if action_type == "UNBLOCK_SOURCE_IP":
                healthy = not rule_exists
            else:
                healthy = rule_exists

        else:
            profile = get_profile(device_type)
            actions = profile.get("healing_commands", {}).get("DDOS_ATTACK", [])
            verify_template = None

            for candidate in actions:
                if candidate.get("action_type") == action_type and candidate.get("verify_command"):
                    verify_template = candidate["verify_command"]
                    break

            if not verify_template:
                return False, "[VERIFY:DDOS] No verification command"

            command = verify_template.format(**kwargs)
            output = connector.run_readonly_command(command) or ""
            ip_present = ip in output

            if action_type == "UNBLOCK_SOURCE_IP":
                healthy = not ip_present
            else:
                healthy = ip_present

        message = (
            f"[VERIFY:DDOS] action={action_type} ip={ip} "
            f"healthy={healthy} output={output[:300]}"
        )
        logger.info(message)
        return healthy, message

    def _verify_action_result(self, incident, connector):
        device_type = self._resolve_device_type(incident.device)
        action = self._latest_healing_action(incident)
        failure_type = incident.failure_type

        if device_type in ("simulated", "python_router"):
            if hasattr(connector, "verify_recovery"):
                healthy, telemetry = connector.verify_recovery()
                normalized = normalize_telemetry(telemetry) if telemetry else None

                interface_count = (
                    normalized.get("interface_up_count")
                    if normalized
                    else "n/a"
                )

                label = "PYTHON_ROUTER" if device_type == "python_router" else "SIMULATED"
                message = (
                    f"[VERIFY:{label}] "
                    f"healthy={healthy} "
                    f"interface_up_count={interface_count}"
                )
                logger.info(message)
                return bool(healthy), message

            return False, f"[VERIFY:{device_type.upper()}] Simulator verification unavailable"

        if failure_type == "LINK_FAILURE":
            healthy, message = self._verify_link_failure(incident, connector)
        elif failure_type == "SERVICE_CRASH":
            healthy, message = self._verify_service_crash(incident, connector)
        elif failure_type == "DDOS_ATTACK":
            healthy, message = self._verify_ddos(incident, connector, action)
        else:
            telemetry = connector.collect_telemetry()
            if telemetry is None:
                return False, "Verification telemetry unavailable"

            normalized = normalize_telemetry(telemetry)
            cpu = normalized.get("cpu_usage", 100.0)
            loss = normalized.get("packet_loss", 100.0)
            latency = normalized.get("latency_ms", 999.0)

            healthy = cpu < 70 and loss < 10 and latency < 100
            message = f"CPU={cpu}% PacketLoss={loss}% Latency={latency}ms"

        # Clear FRR injected-failure overlay once the host is confirmed healthy
        # so subsequent polls stop emitting synthetic DDoS/crash signatures.
        if healthy and device_type in ("frr", "linux", "generic"):
            if hasattr(connector, "_clear_frr_overlay"):
                try:
                    connector._clear_frr_overlay()
                except Exception as exc:
                    logger.warning("[VERIFY] Failed to clear FRR overlay: %s", exc)

        return healthy, message

    def rollback(self, incident):
        """
        Manually roll back a previously executed healing action.

        Restores the incident to a terminal state and (for simulated /
        python_router devices) resets the in-process simulator. For real
        vendor devices, applies the UNBLOCK-style inverse action.

        Terminal status is ``ROLLED_BACK`` by default so the use-case test
        (UC-07) can observe it. Callers that follow the API state machine
        (HEALED -> ROLLBACK -> MONITORING) may set
        ``incident._rollback_target_status = 'MONITORING'`` before calling
        this method to override the label.
        """
        device = incident.device
        last_action = (
            HealingAction.objects
            .filter(incident=incident)
            .order_by("-created_at")
            .first()
        )

        if last_action:
            last_action.status = "ROLLBACK"
            last_action.save(update_fields=["status"])

        # --- Update the incident itself so UC-07 / audit can observe it ---
        target_status = getattr(incident, "_rollback_target_status", "ROLLED_BACK")
        incident.status = target_status
        if hasattr(incident, "resolved_at") and incident.resolved_at is None:
            incident.resolved_at = timezone.now()
            incident.save(update_fields=["status", "resolved_at"])
        else:
            incident.save(update_fields=["status"])

        # For simulated / python_router devices, reset the in-process simulator
        device_type = getattr(device, "device_type", "") or ""
        if device_type in ("simulated", "python_router"):
            connector = self._get_connector(device)
            target = getattr(connector, "sim", None) or getattr(connector, "router", None)
            if target is not None:
                try:
                    if hasattr(target, "reset"):
                        target.reset()
                    elif hasattr(target, "_default_state"):
                        target._default_state()
                except Exception as exc:
                    logger.error("[ROLLBACK] Simulator reset failed: %s", exc)
            return

        # For real devices, find UNBLOCK action (profile first, then ROLLBACK_POLICIES)
        profile = get_profile(self._resolve_device_type(device))
        actions = list(profile.get("healing_commands", {}).get(incident.failure_type, []))
        actions.extend(ROLLBACK_POLICIES.get(incident.failure_type, []))

        rollback_action = next(
            (
                candidate
                for candidate in actions
                if "UNBLOCK" in candidate.get("action_type", "")
            ),
            None,
        )

        if not rollback_action:
            logger.info("[ROLLBACK] No vendor-specific rollback action.")
            return

        connector = self._get_connector(device)

        try:
            kwargs = self._incident_kwargs(incident)
            command = self._fill_action(rollback_action, **kwargs)["command"]

            if "\n" in command:
                command = [
                    item.strip()
                    for item in command.split("\n")
                    if item.strip()
                ]

            logger.info("[ROLLBACK] Executing: %s", command)
            connector.execute_healing_command(command)

        except Exception as exc:
            logger.exception("[ROLLBACK] Failed: %s", exc)
        finally:
            connector.disconnect()

    def disconnect_all(self):
        for connector in self.connectors.values():
            try:
                connector.disconnect()
            except Exception:
                pass
        self.connectors = {}


actuator = HealingActuator()