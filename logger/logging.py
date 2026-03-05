import logging
import logging.config
import os
from pathlib import Path

import yaml


def setup_logging(
    default_level=logging.INFO, default_path="logging_config.yaml", env_key="LOG_CFG"
):
    path = os.getenv(env_key, default_path)
    if os.path.exists(path):
        with open(path, "rt") as f:
            config = yaml.safe_load(f)

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)
