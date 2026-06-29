"""
Reinforcement Learning Agent for NeuroSynapse.
Epsilon-greedy Q-learning with experience replay for healing action selection.
"""

import random

from monitoring.models import RLReward, RLPolicy


class SimpleRLAgent:
    """
    Q-learning agent that learns which healing actions work best per failure type.

    State: failure_type (SERVICE_CRASH, LINK_FAILURE, DDOS_ATTACK)
    Action: index into the healing actions list for that failure type
    Reward: +1 success, -1 failure/timeout
    """

    REWARD_SUCCESS = 1.0
    REWARD_FAILURE = -1.0
    REWARD_TIMEOUT = -1.0
    REPLAY_BUFFER_SIZE = 512
    REPLAY_BATCH_SIZE = 8
    TARGET_IMPROVEMENT = 0.15

    def __init__(self, learning_rate=0.1, discount_factor=0.9, epsilon=0.2):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.q_table = {}
        self.action_counts = {}
        self.performance_history = []
        self.replay_buffer = []
        self.episode_count = 0
        self.baseline_performance = 0.5
        self._load_from_db()

    def _parse_tuple_key(self, key):
        if isinstance(key, str) and key.startswith('('):
            try:
                return eval(key)
            except Exception:
                return key
        return key

    def _load_from_db(self):
        try:
            latest_policy = RLPolicy.objects.order_by('-updated_at').first()
            if latest_policy and latest_policy.policy_data:
                raw_q_table = latest_policy.policy_data.get('q_table', {})
                self.q_table = {
                    self._parse_tuple_key(k): v for k, v in raw_q_table.items()
                }

                raw_action_counts = latest_policy.policy_data.get('action_counts', {})
                self.action_counts = {
                    self._parse_tuple_key(k): v for k, v in raw_action_counts.items()
                }

                self.learning_rate = latest_policy.policy_data.get('learning_rate', 0.1)
                self.epsilon = latest_policy.policy_data.get('epsilon', 0.2)
                self.episode_count = latest_policy.training_episodes
                self.performance_history = latest_policy.policy_data.get('performance_history', [])
                self.replay_buffer = latest_policy.policy_data.get('replay_buffer', [])
                self.baseline_performance = latest_policy.policy_data.get(
                    'baseline_performance', 0.5
                )
                print(f"[RL AGENT] Loaded policy: {latest_policy.policy_name}")
                print(f"[RL AGENT] Episodes: {self.episode_count}, Epsilon: {self.epsilon}")
        except Exception as e:
            print(f"[RL AGENT] No existing policy found, starting fresh: {e}")

    def _save_to_db(self):
        serializable_q_table = {str(k): v for k, v in self.q_table.items()}
        serializable_action_counts = {str(k): v for k, v in self.action_counts.items()}

        recent_performance = self.performance_history[-20:] if self.performance_history else [0.5]
        performance_score = sum(recent_performance) / len(recent_performance)

        policy_data = {
            'q_table': serializable_q_table,
            'learning_rate': self.learning_rate,
            'discount_factor': self.discount_factor,
            'epsilon': self.epsilon,
            'performance_history': self.performance_history[-200:],
            'action_counts': serializable_action_counts,
            'replay_buffer': self.replay_buffer[-self.REPLAY_BUFFER_SIZE:],
            'baseline_performance': self.baseline_performance,
        }

        RLPolicy.objects.update_or_create(
            policy_name='default_q_learning_policy',
            defaults={
                'policy_data': policy_data,
                'performance_score': performance_score,
                'training_episodes': self.episode_count,
            },
        )

    def get_q_value(self, failure_type, action_index):
        return self.q_table.get((failure_type, action_index), 0.0)

    def set_q_value(self, failure_type, action_index, value):
        self.q_table[(failure_type, action_index)] = value

    def select_action(self, failure_type, num_actions):
        """Epsilon-greedy action selection."""
        if num_actions <= 0:
            return 0

        explore = random.random() < self.epsilon
        if explore:
            action = random.randrange(num_actions)
            print(
                f"[RL AGENT] Exploring: action {action}/{num_actions} "
                f"(epsilon={self.epsilon:.3f})"
            )
            return action

        q_values = [self.get_q_value(failure_type, i) for i in range(num_actions)]
        max_q = max(q_values)
        best_actions = [i for i, q in enumerate(q_values) if q == max_q]
        action = random.choice(best_actions)
        print(
            f"[RL AGENT] Exploiting: action {action}/{num_actions} "
            f"(Q={max_q:.3f})"
        )
        return action

    def _apply_q_update(self, failure_type, action_index, reward, increment_episode=True):
        current_q = self.get_q_value(failure_type, action_index)
        new_q = current_q + self.learning_rate * (reward - current_q)
        self.set_q_value(failure_type, action_index, new_q)

        key = (failure_type, action_index)
        self.action_counts[key] = self.action_counts.get(key, 0) + 1

        if increment_episode:
            self.episode_count += 1
            self.performance_history.append(1 if reward > 0 else 0)
            self.epsilon = max(0.05, self.epsilon * 0.995)

        print(f"[RL AGENT] Update: {failure_type}, action {action_index}")
        print(f"  Reward: {reward:+.1f}, Q-value: {current_q:.3f} -> {new_q:.3f}")
        if increment_episode:
            print(f"  Episode: {self.episode_count}, Epsilon: {self.epsilon:.3f}")

    def add_experience(self, failure_type, action_index, reward):
        experience = {
            'failure_type': failure_type,
            'action_index': action_index,
            'reward': reward,
        }
        self.replay_buffer.append(experience)
        if len(self.replay_buffer) > self.REPLAY_BUFFER_SIZE:
            self.replay_buffer.pop(0)

    def replay_experiences(self):
        """Replay a mini-batch from the experience buffer after each loop execution."""
        if len(self.replay_buffer) < 2:
            return

        batch_size = min(self.REPLAY_BATCH_SIZE, len(self.replay_buffer))
        batch = random.sample(self.replay_buffer, batch_size)
        for item in batch:
            self._apply_q_update(
                item['failure_type'],
                item['action_index'],
                item['reward'],
                increment_episode=False,
            )

    def update(self, failure_type, action_index, reward):
        self._apply_q_update(failure_type, action_index, reward, increment_episode=True)
        self.add_experience(failure_type, action_index, reward)
        self.replay_experiences()
        self._save_to_db()

    def get_performance(self, window=20):
        recent = self.performance_history[-window:] if self.performance_history else []
        if not recent:
            return 0.0
        return sum(recent) / len(recent)

    def get_optimization_delta(self):
        current = self.get_performance()
        return current - self.baseline_performance

    def get_stats(self):
        return {
            'episode_count': self.episode_count,
            'epsilon': round(self.epsilon, 4),
            'learning_rate': self.learning_rate,
            'recent_performance': round(self.get_performance(), 3),
            'overall_performance': round(
                sum(self.performance_history) / len(self.performance_history), 3
            ) if self.performance_history else 0,
            'optimization_delta': round(self.get_optimization_delta(), 3),
            'target_improvement': self.TARGET_IMPROVEMENT,
            'replay_buffer_size': len(self.replay_buffer),
            'q_table_size': len(self.q_table),
            'best_actions': self._get_best_actions(),
        }

    def _get_best_actions(self):
        failure_types = {key[0] for key in self.q_table.keys()}
        best = {}
        for failure_type in failure_types:
            actions = [
                (index, self.get_q_value(failure_type, index))
                for (ft, index) in self.q_table.keys()
                if ft == failure_type
            ]
            if actions:
                best_action = max(actions, key=lambda item: item[1])
                best[failure_type] = {
                    'action_index': best_action[0],
                    'q_value': round(best_action[1], 3),
                }
        return best

    def _resolve_action_index(self, healing_action):
        from healing.actuator import actuator

        incident = healing_action.incident
        device_type = incident.device.device_type or 'generic'
        actions = actuator.get_actions_for_failure(incident.failure_type, device_type)

        for index, action in enumerate(actions):
            if action['action_type'] == healing_action.action_type:
                return index
        return 0

    def record_reward(self, healing_action, success, timed_out=False):
        if timed_out:
            reward_value = self.REWARD_TIMEOUT
        elif success:
            reward_value = self.REWARD_SUCCESS
        else:
            reward_value = self.REWARD_FAILURE

        RLReward.objects.create(
            healing_action=healing_action,
            reward_value=int(reward_value),
            state_context={
                'failure_type': healing_action.incident.failure_type,
                'action_type': healing_action.action_type,
                'incident_id': healing_action.incident.id,
                'timed_out': timed_out,
            },
        )

        failure_type = healing_action.incident.failure_type
        action_index = self._resolve_action_index(healing_action)
        self.update(failure_type, action_index, reward_value)

        print(f"[RL AGENT] Reward recorded: {reward_value:+.1f}")
        print(f"[RL AGENT] Current performance: {self.get_performance():.1%}")
        print(
            f"[RL AGENT] Optimization delta: {self.get_optimization_delta():+.1%} "
            f"(target: {self.TARGET_IMPROVEMENT:.0%})"
        )


rl_agent = SimpleRLAgent()
