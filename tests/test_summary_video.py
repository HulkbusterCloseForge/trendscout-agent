from pathlib import Path

from trendcut_agent.summary_video import SummaryBeat, SummaryVideoPlan, build_summary_video
from trendcut_agent.beatmatch import ffprobe_duration


def test_build_summary_video(tmp_path: Path):
    out = tmp_path / "summary.mp4"
    plan = SummaryVideoPlan(
        niche="test niche",
        headline="test headline",
        beats=[SummaryBeat("One", "This is a short summary beat."), SummaryBeat("Two", "This is another beat.")],
        seconds_per_beat=0.6,
        output_path=out,
    )
    result = build_summary_video(plan)
    assert result.exists()
    assert result.with_suffix(".summary.json").exists()
    assert ffprobe_duration(result) > 1.0
