from healing.actuator import HealingActuator


def test_sandbox_accepts_safe_command():
    assert HealingActuator()._validate_in_sandbox('restart service frr') is True


def test_sandbox_blocks_destructive_command():
    assert HealingActuator()._validate_in_sandbox('rm -rf /') is False
