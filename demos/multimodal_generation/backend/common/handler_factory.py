# -*- coding: utf-8 -*-
from typing import Optional
from demos.multimodal_generation.backend.stage.audio import AudioHandler
from demos.multimodal_generation.backend.stage.film import FilmHandler
from demos.multimodal_generation.backend.stage.first_frame_description import (
    FirstFrameDescriptionHandler,
)
from demos.multimodal_generation.backend.stage.first_frame_image import (
    FirstFrameImageHandler,
)
from demos.multimodal_generation.backend.stage.line import LineHandler
from demos.multimodal_generation.backend.stage.role_description import (
    RoleDescriptionHandler,
)
from demos.multimodal_generation.backend.stage.role_image import (
    RoleImageHandler,
)
from demos.multimodal_generation.backend.stage.script import ScriptHandler
from demos.multimodal_generation.backend.common.stage_manager import (
    StageSession,
    Stage,
)
from demos.multimodal_generation.backend.stage.storyboard import (
    StoryboardHandler,
)
from demos.multimodal_generation.backend.stage.video import VideoHandler
from demos.multimodal_generation.backend.stage.video_description import (
    VideoDescriptionHandler,
)
from demos.multimodal_generation.backend.common.handler import Handler


class HandlerFactory:

    @staticmethod
    def get_handler(
        stage: Stage,
        stage_session: StageSession,
    ) -> Optional[Handler]:
        class_name = _handler_map.get(stage)
        if class_name is None:
            return None
        return class_name(stage_session)


_handler_map = {
    Stage.TOPIC: None,
    Stage.SCRIPT: ScriptHandler,
    Stage.STORYBOARD: StoryboardHandler,
    Stage.ROLE_DESCRIPTION: RoleDescriptionHandler,
    Stage.ROLE_IMAGE: RoleImageHandler,
    Stage.FIRST_FRAME_DESCRIPTION: FirstFrameDescriptionHandler,
    Stage.FIRST_FRAME_IMAGE: FirstFrameImageHandler,
    Stage.VIDEO_DESCRIPTION: VideoDescriptionHandler,
    Stage.VIDEO: VideoHandler,
    Stage.LINE: LineHandler,
    Stage.AUDIO: AudioHandler,
    Stage.FILM: FilmHandler,
}
