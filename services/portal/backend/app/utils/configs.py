from pathlib import Path
from digitaltwins import Querier, Uploader, Workflow

class DotDict:
    def __init__(self, dictionary):
        self._dict = dictionary

    def __getattr__(self, name):
        if name in self._dict:
            return self._dict[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        if name != "_dict":
            self._dict[name] = value
        else:
            super().__setattr__(name, value)

current_file = Path(__file__).resolve()
root_dir = current_file.parent.parent.parent
config_path = root_dir / "configs.ini"
querier = Querier(config_path)
uploader = Uploader(config_path)
workflow_dtp_executor = Workflow(config_path)
digitaltwins_configs = DotDict({
    "querier": querier,
    "uploader": uploader,
    "workflow_dtp_executor": workflow_dtp_executor,
})