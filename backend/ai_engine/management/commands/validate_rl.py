"""
Validate Objective 5: RL agent improves healing success by >15%.
Usage: python manage.py validate_rl
"""

import random
from django.core.management.base import BaseCommand
from ai_engine.rl_agent import SimpleRLAgent
from healing.actuator import HEALING_POLICIES


class Command(BaseCommand):
    help = 'Validate RL performance improvement (Objective 5)'

    def handle(self, *args, **options):
        failure_types = list(HEALING_POLICIES.keys())
        trials = 30
        
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('OBJECTIVE 5 VALIDATION'))
        self.stdout.write(self.style.SUCCESS('Target: >15% improvement in healing success'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        # ==========================================
        # PHASE 1: Baseline (no learning)
        # ==========================================
        self.stdout.write('\n📊 PHASE 1: Baseline (Random actions)')
        
        baseline_agent = SimpleRLAgent(epsilon=1.0)  # Always random
        baseline_success = 0
        
        for i in range(trials):
            failure_type = random.choice(failure_types)
            num_actions = len(HEALING_POLICIES[failure_type])
            action_index = baseline_agent.select_action(failure_type, num_actions)
            
            # Simulate outcome based on action quality
            success = self._simulate_outcome(failure_type, action_index)
            if success:
                baseline_success += 1
        
        baseline_rate = baseline_success / trials
        self.stdout.write(f'Baseline success rate: {baseline_rate:.1%} ({baseline_success}/{trials})')
        
        # ==========================================
        # PHASE 2: Train the agent
        # ==========================================
        self.stdout.write('\n🔄 PHASE 2: Training...')
        
        trained_agent = SimpleRLAgent(epsilon=0.3)
        training_episodes = 60
        
        for episode in range(training_episodes):
            failure_type = random.choice(failure_types)
            num_actions = len(HEALING_POLICIES[failure_type])
            action_index = trained_agent.select_action(failure_type, num_actions)
            
            success = self._simulate_outcome(failure_type, action_index)
            reward = 1 if success else -1
            trained_agent.update(failure_type, action_index, reward)
        
        self.stdout.write(f'Training complete ({training_episodes} episodes)')
        self.stdout.write(f'Final epsilon: {trained_agent.epsilon:.3f}')
        
        # ==========================================
        # PHASE 3: Test after learning
        # ==========================================
        self.stdout.write('\n📊 PHASE 3: Post-learning (Epsilon-greedy)')
        
        trained_agent.epsilon = 0.05  # Mostly exploit
        post_success = 0
        
        for i in range(trials):
            failure_type = random.choice(failure_types)
            num_actions = len(HEALING_POLICIES[failure_type])
            action_index = trained_agent.select_action(failure_type, num_actions)
            
            success = self._simulate_outcome(failure_type, action_index)
            if success:
                post_success += 1
        
        post_rate = post_success / trials
        self.stdout.write(f'Post-learning success rate: {post_rate:.1%} ({post_success}/{trials})')
        
        # ==========================================
        # RESULTS
        # ==========================================
        improvement = (post_rate - baseline_rate) * 100
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write('RESULTS')
        self.stdout.write('='*60)
        self.stdout.write(f'Baseline success rate:     {baseline_rate:.1%}')
        self.stdout.write(f'Post-learning rate:        {post_rate:.1%}')
        self.stdout.write(f'Improvement:               {improvement:.1f} percentage points')
        self.stdout.write(f'Target:                    >15 percentage points')
        
        if improvement >= 15:
            self.stdout.write(self.style.SUCCESS(f'\n✅ OBJECTIVE 5 ACHIEVED: {improvement:.1f}% improvement'))
        else:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Below target: {improvement:.1f}% (need >15%)'))
            self.stdout.write(self.style.WARNING('Try increasing training episodes.'))
        
        # Show learned policy
        self.stdout.write('\n📋 Learned Best Actions:')
        stats = trained_agent.get_stats()
        for ft, info in stats['best_actions'].items():
            policies = HEALING_POLICIES.get(ft, [])
            action_desc = policies[info['action_index']]['description'] if info['action_index'] < len(policies) else 'Unknown'
            self.stdout.write(f'  {ft}: {action_desc} (Q={info["q_value"]})')
    
    def _simulate_outcome(self, failure_type, action_index):
        """Simulate healing outcome based on action quality."""
        if failure_type == 'SERVICE_CRASH':
            probs = [0.90, 0.70, 0.50]
        elif failure_type == 'LINK_FAILURE':
            probs = [0.85, 0.60]
        elif failure_type == 'DDOS_ATTACK':
            probs = [0.80, 0.65]
        else:
            probs = [0.70]
        
        if action_index < len(probs):
            return random.random() < probs[action_index]
        return random.random() < 0.50