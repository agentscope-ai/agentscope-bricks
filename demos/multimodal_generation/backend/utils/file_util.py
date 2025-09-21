# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp

from agentscope_bricks.utils.logger_util import logger


async def download_file(url: str, file_path: Path) -> Optional[Path]:
    """
    Download file from URL to local path

    Args:
        url: URL to download from
        file_path: Local path to save file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(file_path, "wb") as f:
                        await f.write(await response.read())
                    return file_path
                else:
                    logger.error(
                        f"Failed to download {url}: {response.status}",
                    )
                    return None
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return None
