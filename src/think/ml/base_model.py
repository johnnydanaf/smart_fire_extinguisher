import xgboost as xgb
import numpy as np
from abc import ABC, abstractmethod

class BaseModel(ABC):
    def __init__(self, config: str):
        _importance_cache: dict[str, float]
        
    
    @abstractmethod
    def fit():
        pass

    @abstractmethod
    def predict():
        pass

    @abstractmethod
    def save():
        pass

    @abstractmethod
    def load():
        pass

    @abstractmethod
    def feature_importance():
        pass