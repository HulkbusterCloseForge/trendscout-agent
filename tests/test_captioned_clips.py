from pathlib import Path

import subprocess

from trendcut_agent.captioned_clips import build_captioned_clip_pack_from_plan, build_captioned_clip_pack_from_transcripts
from trendcut_agent.transcript import TranscriptSegment, VideoTranscript
from trendcut_agent.transcript_intelligence import TranscriptEditPlan, TranscriptInsight


def test_build_captioned_clip_pack(tmp_path: Path):
    plan = TranscriptEditPlan(
        niche="test niche",
        headline="headline",
        thesis="thesis",
        insights=[
            TranscriptInsight("First clip", "Caption for first clip", 0.9, quote="quote one"),
            TranscriptInsight("Second clip", "Caption for second clip", 0.8, quote="quote two"),
        ],
    )
    pack = build_captioned_clip_pack_from_plan(niche="test niche", edit_plan=plan, output_dir=tmp_path, seconds_per_clip=0.5)
    assert len(pack.clips) == 2
    assert (tmp_path / "clip_pack_manifest.json").exists()
    for clip in pack.clips:
        assert Path(clip.output_path).exists()


def test_build_captioned_clip_pack_from_transcripts(tmp_path: Path):
    source = tmp_path / "source.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=360x640:d=2",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100:d=2",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source),
    ], check=True, capture_output=True)
    transcript = VideoTranscript(
        source_path=str(source),
        title="source",
        transcript_text="First important moment. Second important moment.",
        segments=[TranscriptSegment(0.0, 1.0, "First important moment."), TranscriptSegment(1.0, 2.0, "Second important moment.")],
    )
    pack = build_captioned_clip_pack_from_transcripts(niche="test niche", transcripts=[transcript], output_dir=tmp_path / "pack", max_clips=2)
    assert len(pack.clips) == 2
    for clip in pack.clips:
        assert Path(clip.output_path).exists()
        assert Path(clip.output_path).with_suffix(".srt").exists()
