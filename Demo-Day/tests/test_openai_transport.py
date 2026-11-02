import json

import httpx2 as httpx

from user_memory.app import MemoryApplication
from user_memory.config import Settings
from user_memory.provider import OpenAIProvider


def test_oa_02_03_08_http_destination_and_secret_boundary(monkeypatch, service, checkpointer, capsys, ctx):
    """Exercise the real SDK through an intercepted transport. No live request occurs."""
    destinations = []
    marker = "synthetic-secret-not-for-logs"

    def intercepted_send(client, request, **kwargs):
        destinations.append(str(request.url))
        assert request.headers["authorization"] == "Bearer " + marker
        payload = json.loads(request.content)
        if request.url.path.endswith("embeddings"):
            body = {
                "object": "list",
                "model": "text-embedding-3-small",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.01] * 1536}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            }
        else:
            schema = payload["response_format"]["json_schema"]["name"]
            content = {"reply": "I can help with your billing question.", "update_global_policy": False}
            if schema == "MemoryUpdate":
                content = {"new_facts": []}
            body = {
                "id": "fixture",
                "object": "chat.completion",
                "created": 1,
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(content)},
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        return httpx.Response(200, json=body, request=request)

    monkeypatch.setattr(httpx.Client, "send", intercepted_send)
    provider = OpenAIProvider(Settings(sync_strategy="every_turn"), api_key=marker)
    provider.embed_texts(["billing"])
    app = MemoryApplication(service, provider, checkpointer, Settings(sync_strategy="every_turn"))
    app.send(ctx, "t", "Please help with my billing.", "m1")
    assert destinations == [
        "https://api.openai.com/v1/embeddings",
        "https://api.openai.com/v1/chat/completions",
        "https://api.openai.com/v1/chat/completions",
    ]
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    checkpoint = checkpointer.get_tuple(app.config(ctx, "t"))
    assert marker not in repr(checkpoint.checkpoint)
    assert marker not in repr(provider.chat)
