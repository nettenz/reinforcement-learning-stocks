"""
Baseline and supervised learning policy wrappers for Stage 1 signal proof-of-concept.

These policies implement the standard predict() interface so they can be used
directly with the trading environment and evaluation pipeline.
"""

import numpy as np
from typing import Tuple, Optional, Any
from functools import lru_cache
import warnings
warnings.filterwarnings('ignore')


@lru_cache(maxsize=1)
def _detect_xgboost_cuda_params() -> dict[str, Any]:
    """Return XGBoost kwargs that enable CUDA, or an empty dict if unavailable."""
    try:
        import xgboost as xgb
    except ImportError:
        return {}

    # Tiny probe fit to verify the installed xgboost build can really use CUDA.
    X_probe = np.array([[0.0], [1.0], [2.0], [3.0]], dtype=np.float32)
    y_probe = np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float32)

    candidate_params = [
        {"tree_method": "hist", "device": "cuda"},   # xgboost >= 2.x
        {"tree_method": "gpu_hist"},                    # older builds
    ]

    for params in candidate_params:
        try:
            model = xgb.XGBRegressor(
                n_estimators=1,
                max_depth=1,
                learning_rate=0.3,
                random_state=42,
                verbosity=0,
                **params,
            )
            model.fit(X_probe, y_probe)
            return params
        except Exception:
            continue

    return {}


def _xgboost_base_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.05,
        "random_state": 42,
        "verbosity": 0,
    }
    kwargs.update(_detect_xgboost_cuda_params())
    return kwargs


class BaselinePolicy:
    """Base class for all policies (RL and supervised)."""
    
    def predict(self, obs: np.ndarray, deterministic: bool = True) -> Tuple[float, None]:
        """
        Predict next action given observation.
        
        Returns:
            action: float in [-1.0, 1.0] representing target portfolio weight
            state: None (for consistency with RL agent interface)
        """
        raise NotImplementedError


class RandomPolicy(BaselinePolicy):
    """Random action policy (baseline sanity check)."""
    
    def __init__(self, seed: int = 42):
        self.rng = np.random.RandomState(seed)
    
    def predict(self, obs: np.ndarray, deterministic: bool = True) -> Tuple[float, None]:
        """Random uniform action in [-1.0, 1.0]."""
        action = self.rng.uniform(-1.0, 1.0)
        return action, None


class BuyHoldPolicy(BaselinePolicy):
    """Buy-and-hold policy (market baseline)."""
    
    def __init__(self):
        pass
    
    def predict(self, obs: np.ndarray, deterministic: bool = True) -> Tuple[float, None]:
        """Always hold long position (weight = 1.0)."""
        return 1.0, None


class FlatPolicy(BaselinePolicy):
    """Stay flat / cash baseline."""
    
    def __init__(self):
        pass
    
    def predict(self, obs: np.ndarray, deterministic: bool = True) -> Tuple[float, None]:
        """Always stay flat (weight = 0.0)."""
        return 0.0, None


class ThresholdPolicy(BaselinePolicy):
    """
    Simple threshold-based rule using first feature.
    
    If feature[0] > threshold: long (weight=1.0)
    If feature[0] < -threshold: short (weight=-1.0)
    Else: flat (weight=0.0)
    """
    
    def __init__(self, threshold: float = 0.0):
        self.threshold = threshold
    
    def predict(self, obs: np.ndarray, deterministic: bool = True) -> Tuple[float, None]:
        """Threshold-based action on first feature."""
        if obs.ndim > 1:
            obs = obs.flatten()
        
        feature_value = obs[0]  # Use first feature (typically log return)
        
        if feature_value > self.threshold:
            action = 1.0  # long
        elif feature_value < -self.threshold:
            action = -1.0  # short
        else:
            action = 0.0  # flat
        
        return action, None


class SupervisedRegressionPolicy(BaselinePolicy):
    """
    Supervised regression policy: train model to predict next-step return.
    
    Convert continuous prediction to portfolio weight:
    - weight = np.clip(prediction, -1.0, 1.0)
    
    Supports sklearn-compatible regressors: LinearRegression, RandomForestRegressor, etc.
    """
    
    def __init__(self, model_class: str = 'linear'):
        """
        Initialize policy with specified model type.
        
        Args:
            model_class: 'linear', 'rf', 'xgb', or 'mlp'
        """
        self.model_class = model_class
        self.model = None
        self._is_trained = False
    
    def _create_model(self):
        """Create the underlying sklearn model."""
        if self.model_class == 'linear':
            from sklearn.linear_model import Ridge
            self.model = Ridge(alpha=1.0)
        
        elif self.model_class == 'rf':
            from sklearn.ensemble import RandomForestRegressor
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
        
        elif self.model_class == 'xgb':
            try:
                import xgboost as xgb
                self.model = xgb.XGBRegressor(**_xgboost_base_kwargs())
            except ImportError:
                raise ImportError("xgboost not installed. Install with: pip install xgboost")
        
        elif self.model_class == 'mlp':
            from sklearn.neural_network import MLPRegressor
            self.model = MLPRegressor(
                hidden_layer_sizes=(64, 32),
                max_iter=500,
                random_state=42,
                early_stopping=True,
                validation_fraction=0.1
            )
        
        else:
            raise ValueError(f"Unknown model_class: {self.model_class}")
    
    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        """
        Train the supervised model.
        
        Args:
            X_train: Feature matrix (n_samples, n_features)
            y_train: Target returns (n_samples,)
        """
        if self.model is None:
            self._create_model()
        
        self.model.fit(X_train, y_train)
        self._is_trained = True
    
    def predict(self, obs: np.ndarray, deterministic: bool = True) -> Tuple[float, None]:
        """
        Predict portfolio weight from observation.
        
        Args:
            obs: Single observation (n_features,) or (1, n_features)
            deterministic: Ignored (always deterministic for regression)
        
        Returns:
            action: Portfolio weight in [-1.0, 1.0]
        """
        if not self._is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        if obs.ndim > 1:
            obs = obs.reshape(1, -1)
        else:
            obs = obs.reshape(1, -1)
        
        prediction = self.model.predict(obs)[0]
        action = np.clip(prediction, -1.0, 1.0)
        
        return action, None


class SupervisedClassificationPolicy(BaselinePolicy):
    """
    Supervised classification policy: train model to predict action class.
    
    Classes: 0 = flat (weight=0), 1 = long (weight=1), -1 = short (weight=-1)
    
    Supports sklearn-compatible classifiers.
    """
    
    def __init__(self, model_class: str = 'rf'):
        """
        Initialize policy with specified model type.
        
        Args:
            model_class: 'rf', 'xgb', 'svm', 'mlp'
        """
        self.model_class = model_class
        self.model = None
        self._is_trained = False
    
    def _create_model(self):
        """Create the underlying sklearn model."""
        if self.model_class == 'rf':
            from sklearn.ensemble import RandomForestClassifier
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
        
        elif self.model_class == 'xgb':
            try:
                import xgboost as xgb
                self.model = xgb.XGBClassifier(**_xgboost_base_kwargs())
            except ImportError:
                raise ImportError("xgboost not installed. Install with: pip install xgboost")
        
        elif self.model_class == 'svm':
            from sklearn.svm import SVC
            self.model = SVC(kernel='rbf', probability=True, random_state=42)
        
        elif self.model_class == 'mlp':
            from sklearn.neural_network import MLPClassifier
            self.model = MLPClassifier(
                hidden_layer_sizes=(64, 32),
                max_iter=500,
                random_state=42,
                early_stopping=True,
                validation_fraction=0.1
            )
        
        else:
            raise ValueError(f"Unknown model_class: {self.model_class}")
    
    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        """
        Train the supervised classifier.
        
        Args:
            X_train: Feature matrix (n_samples, n_features)
            y_train: Action labels (n_samples,) with values in {-1, 0, 1}
        """
        if self.model is None:
            self._create_model()
        
        # Map labels to 0, 1, 2 for sklearn (which requires consecutive integers)
        label_map = {-1: 0, 0: 1, 1: 2}
        y_train_mapped = np.array([label_map[y] for y in y_train])
        
        self.model.fit(X_train, y_train_mapped)
        self._is_trained = True
        self._label_map = label_map
    
    def predict(self, obs: np.ndarray, deterministic: bool = True) -> Tuple[float, None]:
        """
        Predict portfolio weight from observation.
        
        Args:
            obs: Single observation (n_features,) or (1, n_features)
        
        Returns:
            action: Portfolio weight in {-1.0, 0.0, 1.0}
        """
        if not self._is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        if obs.ndim > 1:
            obs = obs.reshape(1, -1)
        else:
            obs = obs.reshape(1, -1)
        
        prediction_mapped = self.model.predict(obs)[0]
        
        # Reverse map: 0 → -1, 1 → 0, 2 → 1
        reverse_map = {0: -1, 1: 0, 2: 1}
        action = float(reverse_map[prediction_mapped])
        
        return action, None
