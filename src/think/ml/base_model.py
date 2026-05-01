import xgboost as xgb
import numpy as np
from abc import ABC, abstractmethod

class BaseModel(ABC):
    def __init__(self, config: str):
        self.config_file = config        
    
    @abstractmethod
    def fit(self):
        pass

    @abstractmethod
    def predict(self):
        pass

    @abstractmethod
    def save(self):
        pass

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def feature_importance(self):
        pass