"""
NeuroSynapse Orchestrator.
Connects telemetry collection, AI inference, and healing execution
into the complete MAPE-K loop.
"""

import time
import threading
from datetime import datetime
from monitoring.models import Device, Telemetry, Incident, HealingAction
from ai_engine.inference import engine
from healing.actuator import actuator


class NeuroSynapseOrchestrator:
    """Main orchestrator implementing the MAPE-K loop."""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.incident_check_interval = 5  # seconds
    
    def start(self):
        """Start the MAPE-K loop."""
        if self.running:
            print("[ORCHESTRATOR] Already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print("[ORCHESTRATOR] Started MAPE-K loop")
    
    def stop(self):
        """Stop the MAPE-K loop."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        actuator.disconnect_all()
        print("[ORCHESTRATOR] Stopped")
    
    def _loop(self):
        """Main MAPE-K loop."""
        while self.running:
            try:
                # Get latest telemetry from all devices
                devices = Device.objects.filter(status__in=['ONLINE', 'DEGRADED'])
                
                for device in devices:
                    latest_telemetry = Telemetry.objects.filter(
                        device=device
                    ).order_by('-timestamp').first()
                    
                    if latest_telemetry is None:
                        continue
                    
                    # ----- ANALYZE -----
                    diagnosis = engine.diagnose(latest_telemetry)
                    
                    if diagnosis['is_anomaly']:
                        print(f"\n[ORCHESTRATOR] ⚠️ Anomaly detected on {device.name}")
                        print(f"  Failure: {diagnosis['failure_type']}")
                        print(f"  Confidence: {diagnosis['classification_confidence']:.2%}")
                        
                        # Check if there's already an open incident
                        existing_incident = Incident.objects.filter(
                            device=device,
                            status__in=['DETECTED', 'DIAGNOSING', 'READY_FOR_ACTION', 'HEALING']
                        ).first()
                        
                        if existing_incident:
                            print(f"  Existing incident #{existing_incident.id} still open")
                            continue
                        
                        # ----- CREATE INCIDENT -----
                        incident = Incident.objects.create(
                            device=device,
                            telemetry_snapshot=latest_telemetry,
                            failure_type=diagnosis['failure_type'],
                            confidence_score=diagnosis['classification_confidence'],
                            status='DETECTED',
                            description=f"Auto-detected {diagnosis['failure_type']}",
                        )
                        print(f"  Created incident #{incident.id}")
                        
                        # ----- PLAN & EXECUTE (if high confidence) -----
                        if diagnosis['classification_confidence'] >= 0.70:
                            incident.status = 'READY_FOR_ACTION'
                            incident.save()
                            
                            print(f"  High confidence, auto-healing...")
                            
                            # Use RL agent to select best action
                            from ai_engine.rl_agent import rl_agent
                            healing = actuator.execute_healing(incident, rl_agent=rl_agent)
                            
                            if healing and healing.status == 'EXECUTED':
                                # ----- VERIFY -----
                                time.sleep(2)  # Wait for healing to take effect
                                is_healthy, details = actuator.verify_healing(incident)
                                
                                if is_healthy:
                                    print(f"  ✅ Healing successful")
                                    # Record positive reward
                                    rl_agent.record_reward(healing, success=True)
                                else:
                                    print(f"  ❌ Healing failed, rolling back")
                                    # Record negative reward
                                    rl_agent.record_reward(healing, success=False)
                                    actuator.rollback(incident)
                        else:
                            # Low confidence - flag for manual review
                            incident.status = 'MANUAL_REVIEW'
                            incident.save()
                            print(f"  Low confidence ({diagnosis['classification_confidence']:.0%}), manual review needed")
                    
                    else:
                        # Check if any incident needs to be closed
                        open_incidents = Incident.objects.filter(
                            device=device,
                            status='HEALING'
                        )
                        for inc in open_incidents:
                            is_healthy, _ = actuator.verify_healing(inc)
                            if is_healthy:
                                print(f"[ORCHESTRATOR] ✅ Incident #{inc.id} resolved")
                
            except Exception as e:
                print(f"[ORCHESTRATOR] Error: {e}")
                import traceback
                traceback.print_exc()
            
            time.sleep(self.incident_check_interval)
    
    def process_manual_approval(self, incident_id, approved):
        """Process a manual approval/rejection of a healing action."""
        try:
            incident = Incident.objects.get(id=incident_id, status='MANUAL_REVIEW')
            
            if approved:
                incident.status = 'READY_FOR_ACTION'
                incident.save()
                
                # Use RL agent to select best action for manual approval too
                from ai_engine.rl_agent import rl_agent
                healing = actuator.execute_healing(incident, rl_agent=rl_agent)
                
                if healing and healing.status == 'EXECUTED':
                    time.sleep(2)
                    is_healthy, details = actuator.verify_healing(incident)
                    
                    if is_healthy:
                        print(f"  ✅ Manual healing successful")
                        rl_agent.record_reward(healing, success=True)
                    else:
                        print(f"  ❌ Manual healing failed, rolling back")
                        rl_agent.record_reward(healing, success=False)
                        actuator.rollback(incident)
                
                return healing
            else:
                incident.status = 'DETECTED'  # Reset for re-diagnosis
                incident.save()
                return None
        except Incident.DoesNotExist:
            print(f"[ORCHESTRATOR] Incident #{incident_id} not found or not in review")
            return None


# Global instance
orchestrator = NeuroSynapseOrchestrator()