# -*- coding: utf-8 -*-
import asyncio
import tempfile
import os
from typing import AsyncGenerator, List
from pathlib import Path

from moviepy.video.fx.FadeIn import FadeIn
from moviepy.video.fx.FadeOut import FadeOut
from moviepy import (
    TextClip,
    AudioFileClip,
    VideoFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
)
from moviepy.video.tools.subtitles import SubtitlesClip

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    Role,
    Content,
    RunStatus,
    TextContent,
    DataContent,
)
from agentscope_bricks.utils.tracing_utils import trace, TraceType
from agentscope_bricks.utils.logger_util import logger
from agentscope_bricks.utils.message_util import (
    get_agent_message_finish_reason,
    merge_agent_message,
)

from demos.multimodal_generation.backend.config import g_config
from demos.multimodal_generation.backend.common.handler import Handler
from demos.multimodal_generation.backend.common.stage_manager import (
    StageSession,
    Stage,
)
from demos.multimodal_generation.backend.utils.file_util import download_file
from demos.multimodal_generation.backend.utils.oss_client import OssClient

_current_dir = os.path.dirname(os.path.abspath(__file__))
_font_path = os.path.normpath(
    os.path.join(
        _current_dir,
        "../resource/AlibabaPuHuiTi-3-55-Regular.otf",
    ),
)


class FilmHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("film", {})
        self.temp_dir = Path(tempfile.mkdtemp())
        self.oss_client = OssClient(
            directory=f"multimodal_generation/{self.stage_session.session_id}",
        )

    def _create_subtitle_data(
        self,
        subtitle_texts: List[str],
        video_clips: List,
    ) -> List:
        """
        Create subtitle data in format required by SubtitlesClip

        Args:
            subtitle_texts: List of subtitle texts
            video_clips: List of video clips to get timing

        Returns:
            List: Subtitle data in format [((start_time, end_time), text), ...]
        """
        subtitles = []
        current_time = 0.0

        for i, (text, clip) in enumerate(zip(subtitle_texts, video_clips)):
            start_time = current_time
            end_time = current_time + clip.duration
            subtitles.append(((start_time, end_time), text))
            current_time = end_time

        return subtitles

    def _create_subtitle_generator(self, video_size: tuple):
        """
        Create subtitle text generator function for SubtitlesClip

        Args:
            video_size: Size of the video (width, height)

        Returns:
            Function: Text generator function
        """

        def text_generator(text: str) -> TextClip:
            return TextClip(
                font=_font_path,
                text=text,
                font_size=self.config.get("font_size", 24),
                color=self.config.get("font_color", "white"),
                stroke_color=self.config.get("stroke_color", "#000000"),
                stroke_width=self.config.get("stroke_width", 2),
                horizontal_align="center",
                vertical_align="bottom",
                size=video_size,
                margin=(
                    None,
                    -60,
                    None,
                    None,
                ),  # Bottom margin to prevent cutoff
            )

        return text_generator

    def _create_single_film_clip(
        self,
        video_path: Path,
        audio_path: Path,
        duration: float,
    ) -> VideoFileClip:
        """
        Create a single film clip with video and audio (without subtitle)

        Args:
            video_path: Path to video file
            audio_path: Path to audio file
            duration: Duration of the clip

        Returns:
            VideoFileClip: Combined video clip with audio
        """
        # Load video and audio
        video_clip = VideoFileClip(str(video_path))
        audio_clip = AudioFileClip(str(audio_path))

        # Ensure same duration
        min_duration = min(video_clip.duration, audio_clip.duration, duration)
        video_clip = video_clip.subclipped(0, min_duration)
        audio_clip = audio_clip.subclipped(0, min_duration)

        # Combine video and audio
        video_with_audio = video_clip.with_audio(audio_clip)
        logger.info(f"Created video clip with duration: {min_duration}")

        return video_with_audio

    def _add_transition_effects(
        self,
        clips: List[VideoFileClip],
    ) -> List[VideoFileClip]:
        """
        Add transition effects between clips

        Args:
            clips: List of video clips

        Returns:
            List[CompositeVideoClip]: Clips with transition effects
        """
        if len(clips) <= 1:
            return clips

        fadein_duration = self.config.get("fadein_duration", 0.0)
        fadeout_duration = self.config.get("fadeout_duration", 0.0)

        # Add fade in/out effects
        for i, clip in enumerate(clips):
            effects = []

            if i != 0 and fadein_duration > 0:
                effects.append(FadeIn(duration=fadein_duration))

            if i == len(clips) - 1 and fadeout_duration > 0:
                effects.append(FadeOut(duration=fadeout_duration))

            if effects:
                clips[i] = clip.with_effects(
                    effects,
                )

        return clips

    @staticmethod
    def _extract_subtitles(line_message: Message) -> List[str]:
        """
        Extract Chinese subtitles from line message

        Args:
            line_message: Message containing line content

        Returns:
            List[str]: List of Chinese subtitle texts
        """
        if not line_message or not line_message.content:
            return []

        subtitles = []
        content_list = [
            content
            for content in line_message.content
            if content.type == "text"
            and hasattr(content, "text")
            and content.text
        ]

        # Process content in triplets (role, dialogue, voice)
        # We only need the dialogue (Chinese subtitles)
        for i in range(1, len(content_list), 3):
            if i < len(content_list):
                subtitles.append(content_list[i].text)

        return subtitles

    async def _synthesize_film(
        self,
        video_urls: List[str],
        audio_urls: List[str],
        subtitle_texts: List[str],
    ) -> str:
        """
        Synthesize film from multiple video, audio and subtitle inputs

        Args:
            video_urls: List of video URLs
            audio_urls: List of audio URLs
            subtitle_texts: List of subtitle texts

        Returns:
            str: Path to the final film file
        """
        try:
            # Download all files
            video_paths = []
            audio_paths = []

            for i, (video_url, audio_url) in enumerate(
                zip(video_urls, audio_urls),
            ):
                video_path = self.temp_dir / f"video_{i}.mp4"
                audio_path = self.temp_dir / f"audio_{i}.wav"

                # Download files
                video_path = await download_file(video_url, video_path)
                audio_path = await download_file(audio_url, audio_path)
                if not video_path or not audio_path:
                    raise RuntimeError(
                        f"Failed to download files for clip {i}: "
                        f"audio_path={audio_path}, video_path={video_path}",
                    )

                video_paths.append(video_path)
                audio_paths.append(audio_path)

            if not video_paths or not audio_paths:
                raise ValueError("No valid video or audio files downloaded")

            # Create individual film clips (without subtitles)
            film_clips = []
            for i, (video_path, audio_path) in enumerate(
                zip(video_paths, audio_paths),
            ):
                # Get duration from video
                temp_video = VideoFileClip(str(video_path))
                duration = temp_video.duration
                temp_video.close()

                # Create film clip without subtitle
                film_clip = self._create_single_film_clip(
                    video_path,
                    audio_path,
                    duration,
                )
                film_clips.append(film_clip)

            # Add transition effects
            film_clips = self._add_transition_effects(film_clips)

            # Concatenate all clips
            concatenated_video = concatenate_videoclips(
                film_clips,
                method="compose",
            )

            # Create subtitle data and SubtitlesClip
            subtitle_data = self._create_subtitle_data(
                subtitle_texts,
                film_clips,
            )
            subtitle_generator = self._create_subtitle_generator(
                film_clips[0].size,
            )
            subtitle_clip = SubtitlesClip(
                subtitle_data,
                make_textclip=subtitle_generator,
            )

            # Combine video with subtitles
            final_film = CompositeVideoClip(
                [concatenated_video, subtitle_clip],
            )

            logger.info(
                f"Created final film with {len(subtitle_texts)} subtitles",
            )

            # Export final film
            output_path = self.temp_dir / "film.mp4"
            final_film.write_videofile(
                str(output_path),
                codec="libx264",
                audio_codec="aac",
                temp_audiofile="temp-audio.m4a",
                remove_temp=True,
            )

            # Clean up individual clips
            for clip in film_clips:
                clip.close()
            final_film.close()

            return str(output_path)

        except Exception as e:
            raise RuntimeError(f"Error synthesizing film: {e}")

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="film_stage",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Generate final film by combining audio, video and subtitle inputs

        Returns:
            Generated film output
        """
        # Get inputs from stage session
        audio_message = self.stage_session.get_stage_message(Stage.AUDIO)
        video_message = self.stage_session.get_stage_message(Stage.VIDEO)
        line_message = self.stage_session.get_stage_message(Stage.LINE)

        if not audio_message or not audio_message.content:
            raise ValueError("No audio message found")

        if not video_message or not video_message.content:
            raise ValueError("No video message found")

        if not line_message or not line_message.content:
            raise ValueError("No line message found")

        # Create assistant message
        assistant_message = Message(
            role=Role.ASSISTANT,
            content=[],
        )

        # Extract video URLs from video message
        video_urls = []
        for content in video_message.content:
            if (
                content.type == "data"
                and hasattr(content, "data")
                and content.data
            ):
                # In DataContent, URLs are keys and texts are values
                video_urls.extend(content.data.keys())

        # Extract audio URLs from audio message
        audio_urls = []
        for content in audio_message.content:
            if (
                content.type == "data"
                and hasattr(content, "data")
                and content.data
            ):
                # In DataContent, URLs are keys and texts are values
                audio_urls.extend(content.data.keys())

        # Extract Chinese subtitles from line message
        subtitle_texts = self._extract_subtitles(line_message)
        logger.info(f"Extracted subtitles: {subtitle_texts}")

        if len(video_urls) != len(audio_urls) or len(video_urls) != len(
            subtitle_texts,
        ):
            raise ValueError(
                f"Mismatch between video ({len(video_urls)}), "
                f"audio ({len(audio_urls)}) and subtitle "
                f"({len(subtitle_texts)}) counts",
            )

        # Synthesize film
        try:
            film_path = await self._synthesize_film(
                video_urls,
                audio_urls,
                subtitle_texts,
            )

            oss_path = await self.oss_client.upload_file_and_sign(film_path)

            # Create video content for the final film
            film_content = DataContent(
                data={"video_url": oss_path},
                index=0,
                delta=False,
                msg_id=assistant_message.id,
                status=RunStatus.Completed,
            )

            # Update message with final content and status
            assistant_message.content = [film_content]
            assistant_message.status = RunStatus.Completed

            # Yield the completed message
            yield assistant_message.completed()

            # Set stage messages
            self.stage_session.set_stage_message(
                Stage.FILM,
                assistant_message,
            )

        except Exception as e:
            raise RuntimeError(f"Failed to synthesize film: {e}")

    def __del__(self):
        """Clean up temporary files"""
        try:
            import shutil
            import sys

            # Only cleanup if Python is not shutting down
            if (
                hasattr(sys, "meta_path")
                and sys.meta_path is not None
                and self.temp_dir.exists()
            ):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            raise RuntimeError(f"Error cleaning up temp directory: {e}")


if __name__ == "__main__":
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.FILM)

    message = Message(
        role=Role.USER,
        content=[TextContent(text="百炼橙汁")],
    )

    asyncio.run(test_handler(FilmHandler, message, stage_session))
