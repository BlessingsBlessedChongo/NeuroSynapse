"""
Reinforcement Learning Agent for NeuroSynapse.
Uses a Q-learning approach to learn optimal healing actions.
"""

import json
import random
import numpy as np
from monitoring.models import RLReward, RLPolicy


class SimpleRLAgent:
    """
    Q-learning agent that learns which healing actions work best
    for each failure type.
    
    State: failure_type (SERVICE_CRASH, LINK_FAILURE, DDOS_ATTACK)
    Action: index into the healing actions list for that failure type
    Reward: +1 for successful healing, -1 for failed healing
    """
    
    def __init__(self, learning_rate=0.1, discount_factor=0.9, epsilon=0.2):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.q_table = {}  # {(failure_type, action_index): q_value}
        self.action_counts = {}  # Track how many times each action is used
        self.performance_history = []
        self.episode_count = 0
        self._load_from_db()
    
    def _load_from_db(self):
        """Load the latest policy from the database."""
        try:
            latest_policy = RLPolicy.objects.order_by('-updated_at').first()
            if latest_policy and latest_policy.policy_data:
                # Load Q-table with string keys and convert back to tuples
                raw_q_table = latest_policy.policy_data.get('q_table', {})
                self.q_table = {}
                for k, v in raw_q_table.items():
                    # Convert string key back to tuple (e.g., "('SERVICE_CRASH', 0)" -> ('SERVICE_CRASH', 0))
                    if isinstance(k, str) and k.startswith('('):
                        try:
                            key_tuple = eval(k)
                            self.q_table[key_tuple] = v
                        except:
                            self.q_table[k] = v
                    else:
                        self.q_table[k] = v
                
                # Load action counts with string keys
                raw_action_counts = latest_policy.policy_data.get('action_counts', {})
                self.action_counts = {}
                for k, v in raw_action_counts.items():
                    if isinstance(k, str) and k.startswith('('):
                        try:
                            key_tuple = eval(k)
                            self.action_counts[key_tuple] = v
                        except:
                            self.action_counts[k] = v
                    else:
                        self.action_counts[k] = v
                
                self.learning_rate = latest_policy.policy_data.get('learning_rate', 0.1)
                self.epsilon = latest_policy.policy_data.get('epsilon', 0.2)
                self.episode_count = latest_policy.training_episodes
                self.performance_history = latest_policy.policy_data.get('performance_history', [])
                print(f"[RL AGENT] Loaded policy: {latest_policy.policy_name}")
                print(f"[RL AGENT] Episodes: {self.episode_count}, Epsilon: {self.epsilon}")
        except Exception as e:
            print(f"[RL AGENT] No existing policy found, starting fresh: {e}")
    
    def _save_to_db(self):
        """Save the current policy to the database."""
        # Convert tuple keys to strings for JSON serialization
        serializable_q_table = {str(k): v for k, v in self.q_table.items()}
        serializable_action_counts = {str(k): v for k, v in self.action_counts.items()}
        
        policy_data = {
            'q_table': serializable_q_table,
            'learning_rate': self.learning_rate,
            'discount_factor': self.discount_factor,
            'epsilon': self.epsilon,
            'performance_history': self.performance_history,
            'action_counts': serializable_action_counts,
        }
        
        # Calculate performance score
        recent_performance = self.performance_history[-20:] if self.performance_history else [0.5]
        performance_score = sum(recent_performance) / len(recent_performance)
        
        policy, created = RLPolicy.objects.update_or_create(
            policy_name='default_q_learning_policy',
            defaults={
                'policy_data': policy_data,
                'performance_score': performance_score,
                'training_episodes': self.episode_count,
            }
        )
        
        if created:
            print(f"[RL AGENT] Created new policy: {policy.policy_name}")
        return policy
    
    def get_q_value(self, failure_type, action_index):
        """Get Q-value for a state-action pair."""
        key = (failure_type, action_index)
        return self.q_table.get(key, 0.0)
    
    def set_q_value(self, failure_type, action_index, value):
        """Set Q-value for a state-action pair."""
        key = (failure_type, action_index)
        self.q_table[key] = value
    
    def select_action(self, failure_type, num_actions):
        """Select an action using epsilon-greedy policy.
        
        Args:
            failure_type: The type of failure (state)
            num_actions: Number of available actions
        
        Returns:
            Index of the selected action
        """
        if num_actions == 0:
            return 0
        
        # Exploration: try a random action
        if random.random() < self.epsilon:
            action = random.randint(0, num_actions - 1)
            print(f"[RL AGENT] Exploring: action {action}/{num_actions} (epsilon={self.epsilon})")
            return action
        
        # Exploitation: pick the best known action
        q_values = [self.get_q_value(failure_type, i) for i in range(num_actions)]
        max_q = max(q_values)
        
        # If multiple actions have the same max value, pick randomly among them
        best_actions = [i for i, q in enumerate(q_values) if q == max_q]
        action = random.choice(best_actions)
        print(f"[RL AGENT] Exploiting: action {action}/{num_actions} (Q={max_q:.3f})")
        return action
    
    def update(self, failure_type, action_index, reward, next_failure_type=None):
        """Update Q-value based on reward received.
        
        Args:
            failure_type: The failure type that was healed
            action_index: The action that was taken
            reward: +1 for success, -1 for failure
            next_failure_type: Not used in this simple implementation
        """
        # Get current Q-value
        current_q = self.get_q_value(failure_type, action_index)
        
        # Q-learning update formula: Q(s,a) = Q(s,a) + α * (reward - Q(s,a))
        new_q = current_q + self.learning_rate * (reward - current_q)
        self.set_q_value(failure_type, action_index, new_q)
        
        # Track action count
        key = (failure_type, action_index)
        self.action_counts[key] = self.action_counts.get(key, 0) + 1
        
        # Track performance
        self.episode_count += 1
        self.performance_history.append(1 if reward > 0 else 0)
        
        # Decay epsilon over time (less exploration as agent learns)
        self.epsilon = max(0.05, self.epsilon * 0.995)
        
        print(f"[RL AGENT] Update: {failure_type}, action {action_index}")
        print(f"  Reward: {reward:+d}, Q-value: {current_q:.3f} → {new_q:.3f}")
        print(f"  Episode: {self.episode_count}, Epsilon: {self.epsilon:.3f}")
        
        # Save to database periodically
        if self.episode_count % 5 == 0:
            self._save_to_db()
    
    def get_performance(self, window=20):
        """Get recent performance (success rate)."""
        recent = self.performance_history[-window:] if self.performance_history else []
        if not recent:
            return 0.0
        return sum(recent) / len(recent)
    
    def get_stats(self):
        """Get agent statistics for the dashboard."""
        return {
            'episode_count': self.episode_count,
            'epsilon': round(self.epsilon, 4),
            'learning_rate': self.learning_rate,
            'recent_performance': round(self.get_performance(), 3),
            'overall_performance': round(
                sum(self.performance_history) / len(self.performance_history), 3
            ) if self.performance_history else 0,
            'q_table_size': len(self.q_table),
            'best_actions': self._get_best_actions(),
        }
    
    def _get_best_actions(self):
        """Get the best action for each known failure type."""
        failure_types = set(k[0] for k in self.q_table.keys())
        best = {}
        for ft in failure_types:
            actions = [(i, self.get_q_value(ft, i)) 
                       for (f, i), q in self.q_table.items() if f == ft]
            if actions:
                best_action = max(actions, key=lambda x: x[1])
                best[ft] = {
                    'action_index': best_action[0],
                    'q_value': round(best_action[1], 3),
                }
        return best
    
    def record_reward(self, healing_action, success):
        """Record a reward in the database and update the agent.
        
        Args:
            healing_action: HealingAction object
            success: Boolean indicating if healing was successful
        """
        reward_value = 1 if success else -1
        
        # Save reward to database
        RLReward.objects.create(
            healing_action=healing_action,
            reward_value=reward_value,
            state_context={
                'failure_type': healing_action.incident.failure_type,
                'action_type': healing_action.action_type,
                'incident_id': healing_action.incident.id,
            }
        )
        
        # Update Q-table
        failure_type = healing_action.incident.failure_type
        
        # Find which action index was used
        from healing.actuator import HEALING_POLICIES
        policies = HEALING_POLICIES.get(failure_type, [])
        action_index = 0
        for i, policy in enumerate(policies):
            if policy['action_type'] == healing_action.action_type:
                action_index = i
                break
        
        self.update(failure_type, action_index, reward_value)
        
        print(f"[RL AGENT] Reward recorded: {reward_value:+d}")
        print(f"[RL AGENT] Current performance: {self.get_performance():.1%}")


# Global instance
rl_agent = SimpleRLAgent()