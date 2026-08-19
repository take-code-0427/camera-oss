from flowcam.analytics import FlowAnalytics
from flowcam.config import AnalyticsConfig, CrossingLineConfig, RoiConfig
from flowcam.domain import TrackObservation


def test_roi_occupancy_and_line_crossing() -> None:
    config = AnalyticsConfig(
        roi=RoiConfig(id="roi", polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]),
        crossing_line=CrossingLineConfig(id="entrance", a=(0.5, 0.0), b=(0.5, 1.0)),
        track_ttl_seconds=5,
    )
    analytics = FlowAnalytics("cam", config)

    occupancy, events = analytics.update([TrackObservation(1, (0.25, 0.5))], 0.0)
    assert occupancy == 1
    assert events == []

    occupancy, events = analytics.update([TrackObservation(1, (0.75, 0.5))], 1.0)
    assert occupancy == 1
    assert len(events) == 1
    assert events[0].direction == "out"
    assert analytics.flow_out == 1


def test_stale_track_state_is_removed() -> None:
    config = AnalyticsConfig(
        crossing_line=CrossingLineConfig(id="entrance", a=(0.5, 0.0), b=(0.5, 1.0)),
        track_ttl_seconds=1,
    )
    analytics = FlowAnalytics("cam", config)
    analytics.update([TrackObservation(1, (0.25, 0.5))], 0.0)
    analytics.update([], 2.0)
    _, events = analytics.update([TrackObservation(1, (0.75, 0.5))], 2.1)
    assert events == []
