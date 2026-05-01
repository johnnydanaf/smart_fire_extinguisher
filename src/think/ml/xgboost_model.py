from base_model import BaseModel

class XGBoostModel(BaseModel):
    def __init__(self):
        super().__init__()
        self.model = None
