from notion_docs.notion_api import NotionClient


class _FakePages:
    def __init__(self):
        self.update_calls = []

    def retrieve(self, page_id):
        raise Exception(f"Provided ID {page_id} is a database, not a page. Use the retrieve database API instead.")

    def update(self, **kwargs):
        self.update_calls.append(kwargs)


class _FakeDatabases:
    def retrieve(self, database_id):
        return {"id": database_id, "properties": {}}


class _FakeClient:
    def __init__(self):
        self.pages = _FakePages()
        self.databases = _FakeDatabases()


def test_get_metadata_returns_none_for_database_root():
    client = NotionClient("secret")
    client.client = _FakeClient()

    assert client.get_metadata("db-root-id") == (None, None)


def test_set_metadata_skips_database_root():
    client = NotionClient("secret")
    client.client = _FakeClient()

    client.set_metadata("db-root-id", "text-hash", "subtree-hash")

    assert client.client.pages.update_calls == []
