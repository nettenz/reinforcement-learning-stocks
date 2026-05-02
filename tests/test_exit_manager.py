import json

import numpy as np

from src.exit_manager import ExitManager
from src.trading_agent import EnsembleAgent


def test_confidence_rule_boundary() -> None:
    manager = ExitManager("confidence", {"threshold": 0.60, "n_bars": 3})
    state = {"in_position": True, "unrealized_pnl": 0.0, "time_in_position": 1}

    assert manager.should_exit(state, 0.80) is False
    assert manager.should_exit(state, 0.59) is False
    assert manager.should_exit(state, 0.58) is False
    assert manager.should_exit(state, 0.57) is True


def test_trailing_stop_rule_boundary() -> None:
    manager = ExitManager("trailing_stop", {"stop_pct": 0.05})

    assert manager.should_exit({"in_position": True, "unrealized_pnl": 0.02, "time_in_position": 1}, 0.9) is False
    assert manager.should_exit({"in_position": True, "unrealized_pnl": 0.06, "time_in_position": 2}, 0.9) is False
    assert manager.should_exit({"in_position": True, "unrealized_pnl": 0.03, "time_in_position": 3}, 0.9) is False
    assert manager.should_exit({"in_position": True, "unrealized_pnl": 0.01, "time_in_position": 4}, 0.9) is True


def test_time_rule_boundary() -> None:
    manager = ExitManager("time", {"max_bars": 20})

    assert manager.should_exit({"in_position": True, "unrealized_pnl": 0.02, "time_in_position": 19}, 0.9) is False
    assert manager.should_exit({"in_position": True, "unrealized_pnl": 0.02, "time_in_position": 20}, 0.9) is True


def test_reset_clears_state() -> None:
    manager = ExitManager("confidence", {"threshold": 0.60, "n_bars": 2})
    state = {"in_position": True, "unrealized_pnl": 0.0, "time_in_position": 1}

    assert manager.should_exit(state, 0.59) is False
    manager.reset()
    assert manager.should_exit(state, 0.59) is False


class _DummyObsSpace:
    shape = (5,)


class _DummyModel:
    observation_space = _DummyObsSpace()


class _DummyEnsemble:
    def __init__(self, action: int, confidence: float):
        self.models = {13: _DummyModel()}
        self._action = action
        self._confidence = confidence

    def ensemble_predict(self, _obs: np.ndarray, method: str = "voting"):
        return self._action, self._confidence


def test_exit_override_and_new_buy_signal(tmp_path) -> None:
    config = {
        "nvda": {
            "production_ready": True,
            "active_seeds": [13],
            "ensemble_method": "voting",
        }
    }
    config_path = tmp_path / "ensemble_config.json"
    config_path.write_text(json.dumps(config))

    manager = ExitManager("time", {"max_bars": 3})
    agent = EnsembleAgent(
        ensemble=_DummyEnsemble(action=1, confidence=0.95),
        config_path=str(config_path),
        ticker="NVDA",
        exit_manager=manager,
    )

    action, _, debug = agent.step(
        market_features=np.array([], dtype=np.float32),
        news_features=np.array([], dtype=np.float32),
        account_state=np.array([1000.0, 5.0, 1.0, 0.01, 3.0], dtype=np.float32),
    )
    assert action == 0
    assert debug["exit_fired"] is True
    assert debug["exit_rule"] == "time"

    action, _, debug = agent.step(
        market_features=np.array([], dtype=np.float32),
        news_features=np.array([], dtype=np.float32),
        account_state=np.array([1000.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32),
    )
    assert action == 1
    assert debug["exit_fired"] is False
