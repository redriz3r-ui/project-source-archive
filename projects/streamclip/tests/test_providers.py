import json

from streamclip.providers import TwitchProvider


def test_parses_twitchdownloader_native_comments(tmp_path):
    path = tmp_path / "chat.json"
    path.write_text(json.dumps({"comments": [{
        "content_offset_seconds": 123.5,
        "commenter": {"_id": "42", "display_name": "viewer"},
        "message": {"body": "LMAO no way"},
    }]}))
    messages = TwitchProvider().parse_chat(path)
    assert len(messages) == 1
    assert messages[0].timestamp == 123.5
    assert messages[0].author == "42"
    assert messages[0].text == "LMAO no way"
