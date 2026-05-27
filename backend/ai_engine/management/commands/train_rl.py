"""
Train the RL agent through simulated episodes.
Usage: python manage.py train_rl --episodes 50
"""

import time
import random
from django.core.management.base import BaseCommand
from ai_engine.rl_agent import rl_agent
from healing.actuator import HEALING_POLICIES


class Command(BaseCommand):
    help = 'Train the RL agent with simulated healing episodes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--episodes',
            type=int,
            default=50,
            help='Number of training episodes'
        )

    def handle(self, *args, **options):
        episodes = options['episodes']
        failure_types = list(HEALING_POLICIES.keys())
        
        self.stdout.write(self.style.SUCCESS(f'Training RL agent with {episodes} episodes...'))
        self.stdout.write(f'Failure types: {failure_types}')
        self.stdout.write(f'Initial epsilon: {rl_agent.epsilon}')
        self.stdout.write('')
        
        success_count = 0
        fail_count = 0
        
        for episode in range(1, episodes + 1):
            # Pick a random failure type
            failure_type = random.choice(failure_types)
            num_actions = len(HEALING_POLICIES[failure_type])
            
            # Agent selects an action
            action_index = rl_agent.select_action(failure_type, num_actions)
            
            # Simulate healing outcome
            # In simulation, we define which actions work best
            if failure_type == 'SERVICE_CRASH':
                # restart_service is best (index 0 works 90% of time)
                if action_index == 0:
                    success = random.random() < 0.90
                elif action_index == 1:
                    success = random.random() < 0.70
                else:
                    success = random.random() < 0.50
                    
            elif failure_type == 'LINK_FAILURE':
                # reroute_traffic is best (index 0 works 85% of time)
                if action_index == 0:
                    success = random.random() < 0.85
                else:
                    success = random.random() < 0.60
                    
            elif failure_type == 'DDOS_ATTACK':
                # block_source_ip is best (index 0 works 80% of time)
                if action_index == 0:
                    success = random.random() < 0.80
                else:
                    success = random.random() < 0.65
            else:
                success = random.random() < 0.70
            
            # Update agent
            reward = 1 if success else -1
            rl_agent.update(failure_type, action_index, reward)
            
            if success:
                success_count += 1
                icon = '✅'
            else:
                fail_count += 1
                icon = '❌'
            
            # Progress indicator
            if episode % 10 == 0 or episode == 1:
                perf = rl_agent.get_performance()
                self.stdout.write(
                    f'{icon} Episode {episode}/{episodes} | '
                    f'Success rate: {success_count/(success_count+fail_count):.1%} | '
                    f'Recent perf: {perf:.1%} | '
                    f'Epsilon: {rl_agent.epsilon:.3f}'
                )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Training complete!'))
        self.stdout.write(f'Total episodes: {episodes}')
        self.stdout.write(f'Success rate: {success_count/(success_count+fail_count):.1%}')
        self.stdout.write(f'Recent performance: {rl_agent.get_performance():.1%}')
        self.stdout.write(f'Final epsilon: {rl_agent.epsilon:.3f}')
        
        # Show learned Q-table
        self.stdout.write('\nLearned Q-Table:')
        stats = rl_agent.get_stats()
        for ft, info in stats['best_actions'].items():
            self.stdout.write(f'  {ft}: action {info["action_index"]} (Q={info["q_value"]})')
        
        self.stdout.write(f'\nQ-table entries: {stats["q_table_size"]}')