# -*- coding: utf-8 -*-
import json
import asyncio
import aiohttp
from typing import Dict, Any, Optional

from agentscope_bricks.utils.logger_util import get_logger

logger = get_logger()

STAGE_ORDER = [
    "Topic",
    "Script",
    "Storyboard",
    "RoleDescription",
    "RoleImage",
    "FirstFrameDescription",
    "FirstFrameImage",
    "VideoDescription",
    "Video",
    "Line",
    "Audio",
    "Film",
]

STAGE_MESSAGES = {
    "Topic": "百炼椰汁",
    "Script": "百炼椰汁",
    "Storyboard": "百炼椰汁",
    "RoleDescription": "百炼椰汁",
    "RoleImage": "百炼椰汁",
    "FirstFrameDescription": "百炼椰汁",
    "FirstFrameImage": "百炼椰汁",
    "VideoDescription": "小熊学百炼椰汁踢球",
    "Video": "百炼椰汁",
    "Line": "百炼椰汁",
    "Audio": "百炼椰汁",
    "Film": "百炼椰汁",
}


class FilmClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        session_id: str = "mock_session_id",
    ):
        if not base_url:
            base_url = "http://localhost:8080"

        self.base_url = base_url
        self.session_id = session_id
        self.endpoint = f"{base_url}/process"

    def create_request_payload(
        self,
        stage: str,
        text_content: str,
    ) -> Dict[str, Any]:
        """Create request payload for a specific stage"""
        return {
            "session_id": self.session_id,
            "input": [
                {
                    "type": stage,
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": text_content,
                        },
                    ],
                },
            ],
        }

    async def send_request(
        self,
        session: aiohttp.ClientSession,
        stage: str,
        text_content: str,
    ) -> bool:
        """Send request for a specific stage and wait for completion"""
        payload = self.create_request_payload(stage, text_content)

        logger.info(f"=== Sending {stage} request ===")
        logger.info(
            f"Request payload: {json.dumps(payload, ensure_ascii=False)}",
        )

        try:
            async with session.post(self.endpoint, json=payload) as response:
                if response.status != 200:
                    logger.error(
                        f"HTTP error"
                        f" {response.status}: {await response.text()}",
                    )
                    return False

                # Process streaming response
                async for line in response.content:
                    if line:
                        try:
                            # Decode the line and parse JSON
                            line_str = line.decode("utf-8").strip()
                            if line_str.startswith("data: "):
                                json_str = line_str[
                                    6:
                                ]  # Remove 'data: ' prefix
                                if json_str == "[DONE]":
                                    continue

                                response_data = json.loads(json_str)
                                responses_json = json.dumps(
                                    response_data,
                                    ensure_ascii=False,
                                )
                                logger.info(f"Response: {responses_json}")

                                # Check for completion
                                if (
                                    response_data.get("object") == "response"
                                    and response_data.get("status")
                                    == "completed"
                                ):
                                    logger.info(
                                        f"=== {stage} "
                                        f"completed successfully ===",
                                    )
                                    return True

                                # Check for error status
                                status = response_data.get("status")
                                if status and status not in [
                                    "created",
                                    "in_progress",
                                    "completed",
                                ]:
                                    logger.error(
                                        f"Error status received: {status}",
                                    )
                                    return False

                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"Failed to parse JSON: "
                                f"{line_str}, error: {e}",
                            )
                            continue
                        except Exception as e:
                            logger.error(
                                f"Error processing response line: {e}",
                            )
                            continue

        except Exception as e:
            logger.error(f"Request failed for stage {stage}: {e}")
            return False

        logger.warning(f"No completion signal received for stage {stage}")
        return False

    async def run_test_sequence(self):
        """Run the complete test sequence through all stages"""
        logger.info("=== Starting Film Generation Test Sequence ===")
        logger.info(f"Session ID: {self.session_id}")
        logger.info(f"Endpoint: {self.endpoint}")

        async with aiohttp.ClientSession() as session:
            for i, stage in enumerate(STAGE_ORDER):
                logger.info(
                    f"Processing stage {i + 1}/{len(STAGE_ORDER)}: {stage}",
                )

                text_content = STAGE_MESSAGES.get(stage, f"继续处理{stage}")
                success = await self.send_request(session, stage, text_content)

                if not success:
                    logger.error(
                        f"Failed to complete stage {stage}. Stopping test.",
                    )
                    return False

                # Add a small delay between requests
                await asyncio.sleep(1)

        logger.info("=== All stages completed successfully! ===")
        return True


async def main():
    """Main function to run the client test"""
    client = FilmClient()

    try:
        success = await client.run_test_sequence()
        if success:
            logger.info("✅ Test completed successfully!")
        else:
            logger.error("❌ Test failed!")

    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
