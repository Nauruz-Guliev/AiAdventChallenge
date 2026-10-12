from app.domain.models import GenerationStats
from app.ports.llm import ModelInfo, StreamDelta, StreamDone


def test_stream_events_construct():
    d = StreamDelta(kind="content", text="hi")
    assert (d.kind, d.text) == ("content", "hi")
    done = StreamDone(stats=GenerationStats(model="m", completion_tokens=3))
    assert done.stats.completion_tokens == 3


def test_model_info_defaults():
    assert ModelInfo(name="gemma4:12b").parameter_size == ""
