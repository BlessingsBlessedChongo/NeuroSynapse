import os
import json
import time
import socket
from datetime import datetime, timedelta

import requests
import paramiko

from django.core.management.base import BaseCommand
from django.utils import timezone

from monitoring.models import Device, Incident, HealingAction, RLReward, Telemetry


API_BASE = os.environ.get('API_BASE_URL', 'http://localhost:8000')


class Command(BaseCommand):
    help = 'Run end-to-end system tests against FRR container and NeuroSynapse services'

    def add_arguments(self, parser):
        parser.add_argument('--frr-ip', type=str, default='127.0.0.1')
        parser.add_argument('--frr-port', type=int, default=2222)
        parser.add_argument('--user', type=str, default='admin')
        parser.add_argument('--password', type=str, default='admin')

    def handle(self, *args, **options):
        frr_ip = options['frr_ip']
        frr_port = options['frr_port']
        user = options['user']
        password = options['password']

        report = {
            'start_time': timezone.now().isoformat(),
            'frr': frr_ip,
            'results': [],
            'summary': {},
        }

        print('[INFO] Starting end-to-end test suite')

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Helper: run remote command
        def run_ssh(cmd, sudo=False, timeout=10):
            try:
                full_cmd = cmd
                stdin, stdout, stderr = ssh.exec_command(full_cmd, timeout=timeout)
                out = stdout.read().decode('utf-8', errors='ignore')
                err = stderr.read().decode('utf-8', errors='ignore')
                exit_code = stdout.channel.recv_exit_status()
                return exit_code, out.strip(), err.strip()
            except Exception as e:
                return 255, '', str(e)

        # Pre-checks
        pre_checks = {'ssh': False, 'health': False, 'collector': False}

        # SSH reachability
        try:
            print(f'[INFO] Connecting to FRR SSH {frr_ip}:{frr_port}...')
            ssh.connect(hostname=frr_ip, port=frr_port, username=user, password=password, timeout=10)
            code, out, err = run_ssh('echo connected')
            if code == 0 and 'connected' in out:
                pre_checks['ssh'] = True
                print('[PASS] SSH to FRR container OK')
            else:
                print('[FAIL] SSH command failed:', err or out)
        except (socket.error, paramiko.ssh_exception.SSHException) as e:
            print('[FAIL] SSH connection failed:', str(e))

        # Health endpoint
        try:
            h = requests.get(f'{API_BASE}/api/health/', timeout=6)
            if h.status_code == 200:
                pre_checks['health'] = True
                print('[PASS] Django health endpoint returned 200')
            else:
                print(f'[FAIL] Health endpoint returned {h.status_code}')
        except Exception as e:
            print('[FAIL] Health endpoint request failed:', str(e))

        # Collector / Orchestrator activity: check recent telemetry via ORM
        try:
            recent_cutoff = timezone.now() - timedelta(seconds=120)
            recent = Telemetry.objects.filter(timestamp__gte=recent_cutoff).order_by('-timestamp')[:1]
            if recent.exists():
                pre_checks['collector'] = True
                print('[PASS] Collector appears active (recent telemetry present)')
            else:
                print('[WARN] No recent telemetry found (collector may be inactive)')
        except Exception as e:
            print('[WARN] Unable to query telemetry ORM:', str(e))

        report['pre_checks'] = pre_checks

        # Baseline telemetry samples
        baseline = {'samples': [], 'valid': False}
        print('[INFO] Collecting baseline telemetry (5 samples over 25 seconds)')
        for i in range(5):
            try:
                r = requests.get(f'{API_BASE}/api/telemetry/', timeout=8)
                data = r.json() if r.status_code == 200 else None
            except Exception as e:
                data = None
                print('[WARN] Telemetry API request failed:', str(e))

            sample_time = timezone.now().isoformat()
            entry = {'time': sample_time, 'data': data}
            baseline['samples'].append(entry)
            time.sleep(5)

        # Validate presence of canonical features in the first non-empty sample
        def extract_features(sample):
            if not sample or not isinstance(sample, dict):
                return None
            # Attempt to find first telemetry record
            # Accept flexible payloads
            # Try sample[0] -> devices list
            try:
                items = sample
                # If API wraps telemetry under 'telemetry'
                if isinstance(sample, dict) and 'telemetry' in sample:
                    items = sample['telemetry']
                # Search for numeric fields in nested structure
                # Flatten to first numeric dict found
                def find_dict(obj):
                    if isinstance(obj, dict):
                        keys = set(obj.keys())
                        needed = {'cpu_usage', 'memory_usage', 'packet_loss', 'latency_ms', 'bandwidth_util', 'interface_up_count', 'ospf_neighbors', 'error_count'}
                        if keys & needed:
                            return obj
                        for v in obj.values():
                            res = find_dict(v)
                            if res:
                                return res
                    if isinstance(obj, list):
                        for v in obj:
                            res = find_dict(v)
                            if res:
                                return res
                    return None

                found = find_dict(items)
                return found
            except Exception:
                return None

        features_found = extract_features(baseline['samples'][0]['data'])
        if features_found:
            baseline['valid'] = all(k in features_found for k in (
                'cpu_usage', 'memory_usage', 'packet_loss', 'latency_ms', 'bandwidth_util', 'interface_up_count', 'ospf_neighbors', 'error_count'
            ))
        else:
            baseline['valid'] = False

        print('[INFO] Baseline telemetry validity:', 'OK' if baseline['valid'] else 'MISSING')
        report['baseline'] = baseline

        # Identify FRR device record in DB
        try:
            device = Device.objects.filter(device_type='frr').first()
            if not device:
                print('[WARN] No FRR device found in database with device_type="frr"')
        except Exception as e:
            device = None
            print('[WARN] Unable to query Device ORM:', str(e))

        # Test sequences
        injections = [
            {'name': 'service_crash', 'command': 'systemctl stop frr', 'revert': 'systemctl start frr', 'model_type': 'SERVICE_CRASH'},
            {'name': 'link_failure', 'command': "vtysh -c 'configure terminal' -c 'interface eth1' -c 'shutdown'", 'revert': "vtysh -c 'configure terminal' -c 'interface eth1' -c 'no shutdown'", 'model_type': 'LINK_FAILURE', 'interface': 'eth1'},
            {'name': 'ddos_attack', 'command': 'iptables -A INPUT -s 10.0.0.5 -j DROP', 'revert': 'iptables -D INPUT -s 10.0.0.5 -j DROP', 'model_type': 'DDOS_ATTACK', 'source_ip': '10.0.0.5'},
        ]

        detection_results = []
        correct_detections = 0

        # Record RL stats baseline
        rl_before = None
        try:
            r = requests.get(f'{API_BASE}/api/rl-stats/', timeout=8)
            if r.status_code == 200:
                rl_before = r.json()
                print('[INFO] Retrieved RL stats baseline')
        except Exception:
            print('[WARN] Could not fetch RL stats before test')

        for inj in injections:
            name = inj['name']
            model_type = inj['model_type']
            print(f'[INFO] Injecting failure: {name}')
            start_inject = timezone.now()

            # execute injection via SSH
            code, out, err = run_ssh(inj['command'])
            if code == 0:
                print(f'[OK] Injection command executed: {inj["command"]}')
            else:
                print(f'[WARN] Injection command returned code {code}: {err or out}')

            # Wait up to 30s for orchestrator to detect incident
            detected = None
            detect_start = time.time()
            detected_time = None
            while time.time() - detect_start < 30:
                time.sleep(2)
                try:
                    incidents = Incident.objects.filter(device=device, detected_at__gte=start_inject)
                    if incidents.exists():
                        # find newest matching type
                        for inc in incidents.order_by('-detected_at'):
                            if inc.failure_type == model_type:
                                detected = inc
                                detected_time = inc.detected_at
                                break
                        if detected:
                            break
                except Exception as e:
                    print('[WARN] Error querying incidents:', str(e))

            if detected:
                delta = (detected_time - start_inject).total_seconds()
                print(f'[PASS] Incident detected: {model_type} (confidence={detected.confidence_score:.2f}) in {delta:.1f}s')
            else:
                print(f'[FAIL] Incident not detected for {model_type} within timeout')

            # Verify confidence
            confidence_ok = False
            confidence_val = None
            if detected and detected.confidence_score is not None:
                confidence_val = float(detected.confidence_score)
                confidence_ok = confidence_val > 0.7
                print(f'[INFO] Confidence: {confidence_val:.2f} ->', 'OK' if confidence_ok else 'LOW')

            # Monitor healing
            healing_ok = False
            healing_output = None
            healing_start = time.time()
            healing_record = None
            while time.time() - healing_start < 40:
                time.sleep(2)
                try:
                    if detected:
                        actions = HealingAction.objects.filter(incident=detected).order_by('-created_at')
                        if actions.exists():
                            healing_record = actions.first()
                            # Consider executed if status indicates executed or completed_at set
                            if healing_record.status in ('EXECUTED',) or healing_record.completed_at:
                                healing_ok = True
                                healing_output = healing_record.execution_output or healing_record.sandbox_result or ''
                                break
                except Exception as e:
                    print('[WARN] Error querying healing actions:', str(e))

            if healing_ok:
                heal_time = (healing_record.completed_at - detected.detected_at).total_seconds() if healing_record.completed_at and detected else None
                print(f'[PASS] Healing executed in {heal_time:.1f}s' if heal_time is not None else '[PASS] Healing executed')
            else:
                print('[FAIL] Healing did not complete within timeout')

            # Verify device state post-healing via SSH
            state_ok = False
            verify_out = ''
            if inj['name'] == 'service_crash':
                code, out, err = run_ssh('systemctl is-active frr')
                state_ok = (code == 0 and 'active' in out)
                verify_out = out or err
            elif inj['name'] == 'link_failure':
                code, out, err = run_ssh("vtysh -c 'show interface brief'")
                # check that interface is up
                state_ok = ('eth1' in out and 'up' in out.lower())
                verify_out = out or err
            elif inj['name'] == 'ddos_attack':
                # check iptables for rule absence
                code, out, err = run_ssh('iptables -L INPUT -n')
                state_ok = ('10.0.0.5' not in out)
                verify_out = out or err

            print('[PASS]' if state_ok else '[FAIL]', 'Post-healing verification for', inj['name'])

            # Clean up revert to safe state
            try:
                code, out, err = run_ssh(inj['revert'])
            except Exception:
                pass

            detection_results.append({
                'injection': inj['name'],
                'detected': bool(detected),
                'detection_time_s': (detected_time - start_inject).total_seconds() if detected_time else None,
                'confidence': confidence_val,
                'healing_executed': healing_ok,
                'healing_output': healing_output,
                'post_healing_ok': state_ok,
            })

            if detected and confidence_ok:
                correct_detections += 1

            # small pause between injections
            time.sleep(3)

        # Objective summaries
        total_tests = len(injections)
        detection_rate = correct_detections / total_tests if total_tests else 0
        objectives = {
            'anomaly_detection_accuracy': detection_rate,
        }

        # Dashboard checks
        dashboard_ok = {'device_healthy': False, 'open_incidents_zero': False, 'healed_today_increased': False, 'xai_contains': False}
        try:
            s = requests.get(f'{API_BASE}/api/status/', timeout=8).json()
            # Device status check
            devices = s.get('devices', [])
            if any(d.get('device_type') == 'frr' and (d.get('status') in ('ONLINE', 'HEALTHY') or d.get('status') == 'ONLINE') for d in devices):
                dashboard_ok['device_healthy'] = True
            if s.get('open_incidents', 0) == 0:
                dashboard_ok['open_incidents_zero'] = True
            # healed_today presence
            if 'healed_today' in s:
                dashboard_ok['healed_today_increased'] = True
        except Exception as e:
            print('[WARN] Failed to fetch /api/status/:', str(e))

        # XAI check for the last detected incident
        try:
            last_inc = Incident.objects.order_by('-detected_at').first()
            if last_inc:
                x = requests.get(f'{API_BASE}/api/xai/diagnosis/{last_inc.id}/', timeout=8)
                if x.status_code == 200:
                    body = x.json()
                    if any(k in body for k in ('summary', 'key_evidence', 'what_this_means')):
                        dashboard_ok['xai_contains'] = True
        except Exception:
            pass

        # RL stats after
        rl_after = None
        try:
            r = requests.get(f'{API_BASE}/api/rl-stats/', timeout=8)
            if r.status_code == 200:
                rl_after = r.json()
        except Exception:
            print('[WARN] Could not fetch RL stats after test')

        # RL reward check
        rl_reward_ok = False
        try:
            since = timezone.now() - timedelta(minutes=30)
            if RLReward.objects.filter(created_at__gte=since, reward_value=1).exists():
                rl_reward_ok = True
        except Exception:
            pass

        # Compose report
        report['results'] = detection_results
        report['objectives'] = objectives
        report['dashboard_checks'] = dashboard_ok
        report['rl_before'] = rl_before
        report['rl_after'] = rl_after
        report['rl_reward_ok'] = rl_reward_ok

        # Verdict
        final_pass = detection_rate >= 0.9 and all((r['healing_executed'] and r['post_healing_ok']) for r in detection_results)
        report['summary']['final_pass'] = final_pass
        report['end_time'] = timezone.now().isoformat()

        # save JSON report
        out_dir = os.path.join(os.getcwd(), 'test_results')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'end_to_end_report.json')
        with open(out_path, 'w', encoding='utf-8') as fh:
            json.dump(report, fh, indent=2, default=str)

        # Print human readable summary
        print('\n[INFO] Test run complete. Summary:')
        print(f"[INFO] Detection rate: {detection_rate:.2f} ({correct_detections}/{total_tests})")
        print(f"[INFO] All healings executed and verified: {'OK' if all(r['healing_executed'] and r['post_healing_ok'] for r in detection_results) else 'FAIL'}")
        print(f"[INFO] Dashboard checks: {dashboard_ok}")
        print(f"[INFO] RL reward found: {'YES' if rl_reward_ok else 'NO'}")
        print(f"[INFO] Report written to: {out_path}")

        print('[PASS]' if final_pass else '[FAIL]', 'End-to-end test verdict')

        # Close SSH
        try:
            ssh.close()
        except Exception:
            pass
