"""Audio processor using OpenAI Whisper API."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from openai import OpenAI

from ingestion.metadata import ExtractedContent
from ingestion.processors.base import BaseProcessor


class AudioProcessor(BaseProcessor):
    """Process audio files to extract transcriptions."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        model: str = "whisper-1",
        language: Optional[str] = None,
        response_format: str = "verbose_json",
    ):
        """
        Initialize audio processor.

        Args:
            openai_api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Whisper model to use ("whisper-1")
            language: Language code (e.g., "en", "es") - auto-detect if None
            response_format: Response format ("json", "text", "verbose_json")
        """
        self.client = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model
        self.language = language
        self.response_format = response_format

    def can_process(self, content: ExtractedContent) -> bool:
        """Check if content is audio."""
        return (
            content.metadata.source_type == "audio"
            or content.metadata.original_format
            in (
                "mp3",
                "wav",
                "m4a",
                "ogg",
                "flac",
            )
        )

    def process(self, content: ExtractedContent, **kwargs) -> ExtractedContent:
        """Process audio to extract transcription."""
        start_time = time.time()

        audio_path = content.raw_content_path
        if not audio_path or not audio_path.exists():
            raise ValueError(f"Audio file not found: {audio_path}")

        # Get audio duration for cost estimation
        duration_seconds = self._get_audio_duration(audio_path)

        # Transcribe with Whisper
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    language=self.language,
                    response_format=self.response_format,
                )

            # Parse response
            if self.response_format == "verbose_json":
                text = transcript.text
                language = getattr(transcript, "language", None)
                segments = getattr(transcript, "segments", None)
            else:
                text = transcript if isinstance(transcript, str) else transcript.text
                language = None
                segments = None

            # Update metadata
            content.metadata.processing_steps.append("audio_transcription")
            content.metadata.processing_model = self.model
            content.metadata.processing_cost_usd = self._estimate_cost(duration_seconds)
            content.metadata.processing_duration_seconds = time.time() - start_time
            content.metadata.language = language
            content.metadata.confidence_score = (
                0.95  # Whisper is generally very accurate
            )

            # Store transcript
            content.text = f"# Audio Transcription\n\n{text}"

            # Store segments if available
            if segments:
                segments_text = "\n\n".join(
                    [
                        f"[{seg.get('start', 0):.1f}s - {seg.get('end', 0):.1f}s] {seg.get('text', '')}"
                        for seg in segments
                    ]
                )
                content.additional_texts["transcript_segments"] = segments_text

            return content

        except Exception as e:
            raise Exception(f"Audio transcription failed: {e}") from e

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds."""
        try:
            import ffmpeg

            probe = ffmpeg.probe(str(audio_path))
            duration = float(probe.get("format", {}).get("duration", 0))
            return duration
        except Exception:
            # Fallback: estimate based on file size (rough)
            size_mb = audio_path.stat().st_size / (1024 * 1024)
            # Rough estimate: 1MB ≈ 1 minute for compressed audio
            return size_mb * 60

    def _estimate_cost(self, duration_seconds: float) -> float:
        """Estimate API cost for audio transcription."""
        # Whisper API: $0.006 per minute
        duration_minutes = duration_seconds / 60.0
        return duration_minutes * 0.006
