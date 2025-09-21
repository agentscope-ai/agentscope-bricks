# -*- coding: utf-8 -*-
import json
import traceback
from typing import (
    Optional,
    Any,
    AsyncGenerator,
    Union,
)

from agentscope_runtime.engine.agents.base_agent import Agent
from agentscope_runtime.engine.schemas.agent_schemas import (
    Content,
    Message,
)
from agentscope_runtime.engine.schemas.context import Context
from agentscope_bricks.utils.logger_util import logger
from common.handler_factory import (
    HandlerFactory,
)
from common.stage_manager import (
    get_stage_session,
)
from classifier import Classifier
from utils.message_util import (
    unpack_message,
)


class FilmAgent(Agent):
    def __init__(
        self,
        name: str = "FilmAgent",
        agent_config: Optional[dict] = None,
    ):
        """
        FilmAgent is an agent that uses the AgentDev framework to run.
        """
        super().__init__(name=name, agent_config=agent_config)
        self._attr = {
            "agent_config": self.agent_config,
        }

    def copy(self) -> "FilmAgent":
        return FilmAgent(**self._attr)

    async def run_async(
        self,
        context: Context,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[Message, Content], None]:

        try:
            request = context.request

            if not request:
                logger.error("No request found in context.")
                raise ValueError("No request found in context.")

            logger.info(
                f"receive request:"
                f"{json.dumps(request.model_dump(), ensure_ascii=False)}",
            )

            session_id = request.session_id
            if not session_id:
                logger.error("No session_id found in request.")
                raise ValueError("No session_id found in request.")

            # TODO(zhiyi): using session service
            stage_session = get_stage_session(session_id)

            input_message = request.input[0]
            # Create classifier and classify the user input
            classifier = Classifier(stage_session)
            target_stage = await classifier.classify(input_message)

            logger.info(f"Classified target stage: {target_stage}")

            # Execute the handler for the classified stage
            if not target_stage:
                # Return a simple response message
                response_msg = Message(
                    role="assistant",
                )

                # Complete the message to indicate it's finished
                response_msg = response_msg.completed()
                yield response_msg
            else:
                logger.info(f"=== Executing {target_stage} Handler ===")

                handler = HandlerFactory.get_handler(
                    target_stage,
                    stage_session,
                )

                async for response in handler.handle(input_message):
                    if response is None:
                        continue

                    logger.info(
                        "handler response: %s"
                        % json.dumps(
                            response.model_dump(),
                            ensure_ascii=False,
                        ),
                    )

                    yield response

            # Log stage session after handler
            stages_data = {}
            for stage, message in stage_session.get_all_stages().items():
                stages_data[stage] = (
                    message.model_dump()
                    if hasattr(message, "model_dump")
                    else str(message)
                )
            logger.info(
                "stage session: %s",
                json.dumps(stages_data, ensure_ascii=False),
            )

            logger.info(f"=== {target_stage} Handler Completed ===")

        except Exception as e:
            logger.error(f"Error in FilmAgent run_async: {e}")
            raise
