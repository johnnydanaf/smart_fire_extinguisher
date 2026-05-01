from base_model import BaseModel

class XGBoostModel(BaseModel):
    def __init__(self, config_file: str):
        super().__init__(config_file)
        self.model = None
