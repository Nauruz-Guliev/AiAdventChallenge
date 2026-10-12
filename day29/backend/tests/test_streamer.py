from app.presentation.streamer import TelegramMessageStreamer


class FakeMessage:
    def __init__(self):
        self.text = ""
        self.parse_mode = None


class FakeBot:
    def __init__(self):
        self.messages = []
        self.edits = []

    async def send(self, text, parse_mode=None):
        m = FakeMessage()
        m.text = text
        m.parse_mode = parse_mode
        self.messages.append(m)
        return m

    async def edit(self, m, text, parse_mode=None):
        self.edits.append((text, parse_mode))
        m.text = text
        m.parse_mode = parse_mode


async def test_finish_renders_html():
    bot = FakeBot()
    s = TelegramMessageStreamer(send=bot.send, edit=bot.edit, min_interval=0.0)
    await s.start()
    await s.push("**жирный**")
    await s.finish("**жирный**", "footer")
    last_text, last_pm = bot.edits[-1]
    assert "<b>жирный</b>" in last_text and last_pm == "HTML"
    assert "<p>" not in last_text


async def test_streaming_renders_html_not_raw():
    bot = FakeBot()
    s = TelegramMessageStreamer(send=bot.send, edit=bot.edit, min_interval=0.0)
    await s.start()
    await s.push("`code`")
    text, pm = bot.edits[-1]
    assert "<code>code</code>" in text and pm == "HTML"
