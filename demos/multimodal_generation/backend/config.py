# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Dict, Any
from agentscope_bricks.utils.logger_util import logger


def get_config_file_path() -> Path:
    current_file_dir = Path(__file__).parent.absolute()
    config_file_path = current_file_dir / "config.json"

    if not config_file_path.exists():
        raise FileNotFoundError(f"配置文件未找到: {config_file_path}")

    return config_file_path


def load_config() -> Dict[str, Any]:
    config_file_path = get_config_file_path()

    try:
        with open(config_file_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        raise ValueError(f"配置文件格式错误: {e}")
    except Exception as e:
        raise RuntimeError(f"读取配置文件失败: {e}")


g_config = load_config()

logger.info(
    "loaded config:\n%s" % json.dumps(g_config, ensure_ascii=False, indent=4),
)
