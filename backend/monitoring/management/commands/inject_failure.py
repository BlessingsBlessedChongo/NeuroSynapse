"""
Django management command to inject failures into target network devices.

Supports:
    - Simulated devices (in-memory)
    - FRR / Linux devices (via SSH)
    - Cisco IOS devices (via SSH)
    - MikroTik RouterOS devices (via SSH)
    - Juniper JunOS devices (via SSH)
    - Huawei VRP devices (via SSH)

IMPORTANT – REAL FRR/LINUX NOTES
--------------------------------
Only **LINK_FAILURE** is fully reliable for an end-to-end MAPE-K demo on
a real Linux/FRR host. The command `ip link set dev <iface> down`
directly alters interface state, which the telemetry parser detects via
`ip -br link`.

**DDoS_ATTACK** and **SERVICE_CRASH** injection on a raw Linux host do
*not* reliably produce the high CPU / high bandwidth / high packet loss
signature that the ML model was trained on. For those failure types,
use the simulated device or add stress tooling (e.g., `stress-ng`,
`hping3`) on the target VM.

DANGER — DO NOT TARGET THE MANAGEMENT INTERFACE
------------------------------------------------
The reference `frr-router` Docker container has a single NIC (`eth0`).
That same interface carries both the SSH connection NeuroSynapse
manages the device over *and* whatever "data plane" the link_failure
demo is simulating. Bringing `eth0` down severs the SSH session mid
command (Netmiko will report a "Pattern not detected" timeout even
though the interface really did go down), and worse: the MAPE-K
healing loop can never bring it back up, because there is no longer any
network path into the container to open the SSH connection that would
run `ip link set dev eth0 up`. The failure becomes permanent until you
fix it out-of-band (`docker exec neuro-frr ip link set eth0 up`).

Because of this, injecting `link_failure` against the interface that
matches `MANAGEMENT_INTERFACE` below is blocked by default. If your
compose file gives the container a second NIC (recommended -- see the
project's failure-injection guide for a docker-compose.yml patch),
point `--interface` at that one instead. `--force-mgmt-interface` is
available for advanced use, but understand that using it means you may
need to recover the container manually afterward.
"""

from django.core.management.base import BaseCommand, CommandError
from monitoring.models import Device
from monitoring.connector import get_connector

# The interface known to carry the SSH management session in the
# single-NIC reference topology (see docstring above). Only enforced
# for device_type == 'frr', since real hardware (Cisco/Juniper/etc.)
# typically has a genuinely separate out-of-band management port and
# shutting a data interface doesn't touch the management plane.
MANAGEMENT_INTERFACE = 'eth0'


class Command(BaseCommand):
    help = 'Inject a simulated or actual failure into target network devices'

    def add_arguments(self, parser):
        parser.add_argument('--device-id', type=int, dest='device_id',
                            help='Target specific Device by Primary Key ID')
        parser.add_argument('--ip', type=str, dest='ip_address',
                            help='Target device by IP address')
        parser.add_argument('--device-type', type=str, dest='device_type',
                            help='Target device by type (e.g., frr, cisco_ios, simulated)')
        parser.add_argument('--all', action='store_true', dest='all_devices',
                            help='Inject the failure into every matching device instead of just one. '
                                 'Combine with --device-type to scope it (e.g. --all --device-type frr). '
                                 'Without --device-type, targets every device in the database.')
        parser.add_argument('--continue-on-error', action='store_true', dest='continue_on_error',
                            help='With --all: keep going if one device fails instead of aborting the batch.')
        parser.add_argument('--type', type=str, required=True,
                            choices=['service_crash', 'link_failure', 'ddos', 'ddos_attack'],
                            help='Type of failure to trigger')
        parser.add_argument('--source-ip', type=str, dest='source_ip')
        parser.add_argument('--source-port', type=int, dest='source_port')
        parser.add_argument('--destination-ip', type=str, dest='destination_ip')
        parser.add_argument('--destination-port', type=int, dest='destination_port')
        parser.add_argument('--interface', type=str, dest='interface_name', default='eth0')
        parser.add_argument('--service-name', type=str, dest='service_name', default='frr')
        parser.add_argument('--process-id', type=int, dest='process_id')
        parser.add_argument('--traffic-volume', type=float, dest='traffic_volume')
        parser.add_argument(
            '--force-mgmt-interface', action='store_true', dest='force_mgmt_interface',
            help=f"Allow injecting link_failure against '{MANAGEMENT_INTERFACE}' on frr devices "
                 f"even though it's the SSH management interface in the reference single-NIC "
                 f"topology. Doing this WILL sever the SSH session and the MAPE-K loop will NOT "
                 f"be able to heal it automatically -- you'll need to fix it via "
                 f"'docker exec <container> ip link set {MANAGEMENT_INTERFACE} up'."
        )

    def handle(self, *args, **options):
        if options.get('all_devices'):
            self._handle_all(options)
            return

        device = self._get_target_device(options)
        self._inject_into_device(device, options)

    def _handle_all(self, options):
        devices = self._get_target_devices(options)

        if not devices:
            raise CommandError(
                "No devices matched --all"
                + (f" --device-type {options['device_type']}" if options.get('device_type') else "")
                + ". Nothing to inject."
            )

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Injecting '{options['type']}' into {len(devices)} device(s)..."
        ))

        succeeded, failed = [], []

        for device in devices:
            self.stdout.write("")  # spacer between devices
            try:
                self._inject_into_device(device, options, raise_on_error=True)
                succeeded.append(device.name)
            except CommandError as e:
                failed.append((device.name, str(e)))
                self.stdout.write(self.style.ERROR(f"[FAILED] {device.name}: {e}"))
                if not options.get('continue_on_error'):
                    raise CommandError(
                        f"Aborting batch after failure on '{device.name}'. "
                        f"Re-run with --continue-on-error to skip failures instead."
                    )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Batch summary"))
        self.stdout.write(self.style.SUCCESS(f"  Succeeded ({len(succeeded)}): {', '.join(succeeded) or '-'}"))
        if failed:
            self.stdout.write(self.style.ERROR(f"  Failed ({len(failed)}):"))
            for name, err in failed:
                self.stdout.write(self.style.ERROR(f"    - {name}: {err}"))

    def _inject_into_device(self, device, options, raise_on_error=False):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Targeting Device: '{device.name}' [{device.ip_address}] (Type: {device.device_type})"
        ))

        self._guard_management_interface(device, options)

        connector = get_connector(device)

        kwargs = {
            'source_ip': options.get('source_ip'),
            'source_port': options.get('source_port'),
            'destination_ip': options.get('destination_ip'),
            'destination_port': options.get('destination_port'),
            'interface_name': options.get('interface_name'),
            'service_name': options.get('service_name'),
            'process_id': options.get('process_id'),
            'traffic_volume': options.get('traffic_volume'),
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        try:
            # In-process simulators (DB-backed SimulatedDevice and PythonRouter)
            # share the inject_failure() API — never SSH into them.
            if device.device_type in ('simulated', 'python_router'):
                result = connector.inject_failure(options['type'], **kwargs)
                output_display = result
                success = True
            else:
                result = self._inject_real_device_failure(
                    connector, device, options['type'], **kwargs
                )
                output_display = result.get('output', 'Command sent')
                success = result.get('success', True)

            self.stdout.write(self.style.WARNING(f"[INJECTED] {output_display}"))

            if success:
                self.stdout.write(self.style.SUCCESS(
                    f"[OK] Device '{device.name}' is now degraded for MAPE-K Analysis."
                ))
            else:
                # Don't lie about success: the command errored or the
                # connection dropped before Netmiko could confirm
                # completion. Report it plainly instead of the old
                # behavior of always printing "[OK]" regardless.
                if options['type'] == 'link_failure' and options.get('interface_name') == MANAGEMENT_INTERFACE:
                    hint = (
                        f"This brought down '{MANAGEMENT_INTERFACE}', the SSH management "
                        f"interface, so the connection likely dropped mid-command -- check "
                        f"'docker exec <container> ip -br link' to see the real interface "
                        f"state, and see the failure-injection guide for recovery steps."
                    )
                else:
                    hint = (
                        f"This is not a management-interface link_failure, so the connection "
                        f"drop points at something else -- confirm the device is reachable "
                        f"('docker ps', 'ssh {device.username}@{device.ip_address} -p "
                        f"{device.ssh_port}') before retrying."
                    )
                self.stdout.write(self.style.ERROR(
                    f"[WARNING] Command did not confirm success on '{device.name}'. {hint}"
                ))
        except Exception as e:
            message = f"Failed to inject failure into '{device.name}': {str(e)}"
            raise CommandError(message)
        finally:
            connector.disconnect()
            self.stdout.write("[INFO] SSH connection closed")

    def _guard_management_interface(self, device, options):
        """
        Refuse (by default) to run link_failure against the interface
        known to carry the SSH management session on frr devices in the
        single-NIC reference topology -- doing so severs the connection
        NeuroSynapse needs to heal it back, making the "failure" 
        permanent until someone fixes it out-of-band.
        """
        if device.device_type != 'frr':
            return
        if options.get('type') != 'link_failure':
            return
        if options.get('interface_name') != MANAGEMENT_INTERFACE:
            return
        if options.get('force_mgmt_interface'):
            self.stdout.write(self.style.WARNING(
                f"[DANGER] Proceeding against management interface "
                f"'{MANAGEMENT_INTERFACE}' with --force-mgmt-interface. "
                f"The MAPE-K loop will NOT be able to heal this automatically."
            ))
            return

        raise CommandError(
            f"Refusing to inject link_failure on '{MANAGEMENT_INTERFACE}': it's the SSH "
            f"management interface in the single-NIC reference topology, so bringing it "
            f"down would sever the connection NeuroSynapse needs to heal it back -- the "
            f"MAPE-K loop cannot recover from this on its own. Either target a different "
            f"interface (e.g. --interface eth1 if your compose file has a second network), "
            f"or pass --force-mgmt-interface if you understand you'll need to recover the "
            f"container manually afterward (docker exec <container> ip link set "
            f"{MANAGEMENT_INTERFACE} up)."
        )

    def _get_target_device(self, options):
        if options.get('device_id'):
            return Device.objects.get(id=options['device_id'])
        if options.get('ip_address'):
            return Device.objects.get(ip_address=options['ip_address'])
        if options.get('device_type'):
            device_type = options['device_type']
            # Prefer canonical in-process simulators when multiple rows exist.
            if device_type == 'python_router':
                device = (
                    Device.objects.filter(device_type='python_router', ip_address='127.0.0.2').first()
                    or Device.objects.filter(device_type='python_router').order_by('id').first()
                )
                if device:
                    return device
                device, _ = Device.objects.get_or_create(
                    ip_address='127.0.0.2',
                    defaults={
                        'name': 'PyRouter-01',
                        'device_type': 'python_router',
                        'status': 'ONLINE',
                        'username': 'admin',
                        'password': 'admin',
                    },
                )
                return device
            if device_type == 'simulated':
                device = (
                    Device.objects.filter(device_type='simulated', ip_address='127.0.0.1').first()
                    or Device.objects.filter(device_type='simulated').order_by('id').first()
                )
                if device:
                    return device
                device, _ = Device.objects.get_or_create(
                    ip_address='127.0.0.1',
                    defaults={
                        'name': 'SimRouter',
                        'device_type': 'simulated',
                        'status': 'ONLINE',
                    },
                )
                return device

            device = Device.objects.filter(device_type=device_type).order_by('id').first()
            if device:
                return device
            raise CommandError(
                f"No device with device_type='{device_type}' found. "
                f"Register one first, or use --device-type python_router / simulated."
            )

        device = Device.objects.filter(device_type='frr').first()
        if not device:
            device = Device.objects.filter(device_type='python_router').first()
        if not device:
            device = Device.objects.filter(device_type='simulated').first()

        if not device:
            device, _ = Device.objects.get_or_create(
                ip_address='127.0.0.1',
                defaults={
                    'name': 'SimRouter',
                    'device_type': 'simulated',
                    'status': 'ONLINE',
                },
            )
        return device

    def _get_target_devices(self, options):
        """Resolve the queryset of devices targeted by --all."""
        if options.get('device_id'):
            return list(Device.objects.filter(id=options['device_id']))
        if options.get('ip_address'):
            return list(Device.objects.filter(ip_address=options['ip_address']))
        if options.get('device_type'):
            return list(Device.objects.filter(device_type=options['device_type']))
        return list(Device.objects.all())

    def _inject_real_device_failure(self, connector, device, failure_type, **kwargs):
        device_type = device.device_type
        interface = kwargs.get('interface_name', 'eth0')
        service = kwargs.get('service_name', 'frr')
        source_ip = kwargs.get('source_ip', '10.0.0.5')

        if device_type == 'frr' or device_type == 'linux':
            return self._inject_frr_failure(
                connector, failure_type, interface, service, source_ip
            )

        if device_type == 'cisco_ios':
            return self._inject_cisco_failure(
                connector, failure_type, interface, service, source_ip
            )

        if device_type == 'mikrotik_routeros':
            return self._inject_mikrotik_failure(
                connector, failure_type, interface, service, source_ip
            )

        if device_type == 'juniper_junos':
            return self._inject_juniper_failure(
                connector, failure_type, interface, service, source_ip
            )

        if device_type == 'huawei_vrp':
            return self._inject_huawei_failure(
                connector, failure_type, interface, service, source_ip
            )

        raise ValueError(f"Unsupported device type: {device_type}")

    # ---------------------------------------------------------------------
    # FRR / Linux
    # ---------------------------------------------------------------------
    def _inject_frr_failure(self, connector, failure_type, interface, service, source_ip):
        # NeuroSynapse's FRR container (see init.sh) provisions the SSH
        # management user with passwordless sudo specifically so that
        # privileged networking commands work over a non-root SSH
        # session -- Docker's `privileged: true` / `cap_add` only grant
        # capabilities to processes running as root, not to the
        # unprivileged 'admin' login itself. Without `sudo -n` here,
        # `ip link ... down` and friends fail with
        # "RTNETLINK answers: Operation not permitted" even on a fully
        # privileged container.
        if failure_type == 'service_crash':
            # Stop daemons immediately, then run OpenRC in the background. A
            # foreground rc-service stop can delay the shell prompt long
            # enough for Netmiko to report "Pattern not detected" even though
            # the failure was injected successfully.
            cmd = (
                f"sudo -n sh -c '"
                f"killall -9 watchfrr 2>/dev/null; "
                f"killall -9 zebra ospfd staticd bgpd {service} 2>/dev/null; "
                f"if command -v rc-service >/dev/null 2>&1; then "
                f"(timeout 5 rc-service {service} stop >/dev/null 2>&1 || true) & "
                f"fi; echo INJECTION_SENT'"
            )
            return connector.execute_healing_command(cmd, verify=False)

        elif failure_type == 'link_failure':
            cmd = f"sudo -n ip link set dev {interface} down; ip -br link show {interface} || true"
            return connector.execute_healing_command(cmd, verify=False)

        elif failure_type in ['ddos', 'ddos_attack']:
            # Prefer iptables DROP (matches heal/verify). Fall back to tc /
            # blackhole when iptables is unavailable.
            cmd = (
                f"if command -v iptables >/dev/null 2>&1; then "
                f"sudo -n iptables -A INPUT -s {source_ip} -j DROP; "
                f"sudo -n iptables -C INPUT -s {source_ip} -j DROP && echo BLOCKED; "
                f"elif command -v tc >/dev/null 2>&1; then "
                f"sudo -n tc qdisc add dev {interface} root netem loss 30% delay 200ms; "
                f"else sudo -n ip route add blackhole {source_ip}; fi"
            )
            return connector.execute_healing_command(cmd, verify=False)

        raise ValueError(f"Unsupported failure type: {failure_type}")

    # ---------------------------------------------------------------------
    # Cisco IOS
    # ---------------------------------------------------------------------
    def _inject_cisco_failure(self, connector, failure_type, interface, service, source_ip):
        if failure_type == 'service_crash':
            cmd = [
                "configure terminal",
                f"interface {interface}",
                "shutdown",
                "end",
            ]
            return connector.execute_healing_command(cmd)

        elif failure_type == 'link_failure':
            cmd = [
                "configure terminal",
                f"interface {interface}",
                "shutdown",
                "end",
            ]
            return connector.execute_healing_command(cmd)

        elif failure_type in ['ddos', 'ddos_attack']:
            cmd = [
                "configure terminal",
                f"access-list 100 deny ip host {source_ip} any",
                "end",
            ]
            return connector.execute_healing_command(cmd)

        raise ValueError(f"Unsupported failure type: {failure_type}")

    # ---------------------------------------------------------------------
    # MikroTik RouterOS
    # ---------------------------------------------------------------------
    def _inject_mikrotik_failure(self, connector, failure_type, interface, service, source_ip):
        if failure_type == 'service_crash':
            cmd = "/system resource print"
            return connector.execute_healing_command(cmd)

        elif failure_type == 'link_failure':
            cmd = f'/interface disable [find name="{interface}"]'
            return connector.execute_healing_command(cmd)

        elif failure_type in ['ddos', 'ddos_attack']:
            cmd = f"/ip firewall filter add chain=input src-address={source_ip} action=drop"
            return connector.execute_healing_command(cmd)

        raise ValueError(f"Unsupported failure type: {failure_type}")

    # ---------------------------------------------------------------------
    # Juniper JunOS
    # ---------------------------------------------------------------------
    def _inject_juniper_failure(self, connector, failure_type, interface, service, source_ip):
        if failure_type == 'service_crash':
            cmd = [
                "configure",
                f"set interfaces {interface} disable",
                "commit",
            ]
            return connector.execute_healing_command(cmd)

        elif failure_type == 'link_failure':
            cmd = [
                "configure",
                f"set interfaces {interface} disable",
                "commit",
            ]
            return connector.execute_healing_command(cmd)

        elif failure_type in ['ddos', 'ddos_attack']:
            cmd = [
                "configure",
                f"set firewall family inet filter block-attack term 1 from source-address {source_ip} then discard",
                "commit",
            ]
            return connector.execute_healing_command(cmd)

        raise ValueError(f"Unsupported failure type: {failure_type}")

    # ---------------------------------------------------------------------
    # Huawei VRP
    # ---------------------------------------------------------------------
    def _inject_huawei_failure(self, connector, failure_type, interface, service, source_ip):
        if failure_type == 'service_crash':
            cmd = [
                "system-view",
                f"interface {interface}",
                "shutdown",
                "quit",
            ]
            return connector.execute_healing_command(cmd)

        elif failure_type == 'link_failure':
            cmd = [
                "system-view",
                f"interface {interface}",
                "shutdown",
                "quit",
            ]
            return connector.execute_healing_command(cmd)

        elif failure_type in ['ddos', 'ddos_attack']:
            cmd = [
                "system-view",
                "acl 3000",
                f"rule deny ip source {source_ip} 0",
                "quit",
            ]
            return connector.execute_healing_command(cmd)

        raise ValueError(f"Unsupported failure type: {failure_type}")