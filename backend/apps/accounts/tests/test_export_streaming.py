import csv
import io
import zipfile

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts import export
from apps.accounts.export import DataExportService, iterate_async
from apps.chat.models import Message

User = get_user_model()

URL = "/api/users/me/export/?export_format=csv"


@pytest.fixture
def user():
    return User.objects.create_user(
        username="streamer", email="stream@example.com", password="password"
    )


def open_zip(chunks):
    return zipfile.ZipFile(io.BytesIO(b"".join(chunks)))


def read_csv(archive, name):
    with archive.open(name) as handle:
        return list(csv.DictReader(io.TextIOWrapper(handle, "utf-8", newline="")))


@pytest.mark.django_db
def test_large_export_arrives_in_several_chunks(user, monkeypatch):
    monkeypatch.setattr(export, "CHUNK_ROWS", 100)
    Message.objects.bulk_create(
        Message(user=user, room_id="room", content=f"message {i} " * 40)
        for i in range(2000)
    )

    chunks = list(DataExportService(user).stream_csv_zip())

    assert len(chunks) > 3
    archive = open_zip(chunks)
    assert archive.testzip() is None
    assert len(read_csv(archive, "messages.csv")) == 2000


@pytest.mark.django_db
def test_no_queries_run_until_the_stream_is_read(user, django_assert_num_queries):
    with django_assert_num_queries(0):
        DataExportService(user).stream_csv_zip()


@pytest.mark.django_db
def test_escaping_and_column_order(user):
    content = 'comma, "quotes"\nand a new line, ünïcode'
    Message.objects.create(user=user, room_id="room", content=content)

    archive = open_zip(DataExportService(user).stream_csv_zip())
    rows = read_csv(archive, "messages.csv")

    assert rows[0]["content"] == content
    assert list(rows[0]) == [
        field.name for field in Message._meta.fields if field.name != "user"
    ]


@pytest.mark.django_db
def test_export_without_activity_is_a_valid_zip(user):
    archive = open_zip(DataExportService(user).stream_csv_zip())

    assert archive.testzip() is None
    assert archive.namelist() == ["user_profile.csv"]


@pytest.mark.django_db
def test_view_streams_and_rejects_anonymous_callers(user):
    client = APIClient()
    denied = client.get(URL)
    assert denied.status_code == 401
    assert not denied.streaming

    client.force_authenticate(user=user)
    response = client.get(URL)
    assert response.streaming
    assert open_zip(response.streaming_content).namelist() == ["user_profile.csv"]


def test_async_wrapper_pulls_one_chunk_at_a_time():
    pulled = []

    def source():
        for chunk in (b"a", b"b"):
            pulled.append(chunk)
            yield chunk

    async def consume():
        seen = []
        async for chunk in iterate_async(source()):
            seen.append((chunk, len(pulled)))
        return seen

    assert async_to_sync(consume)() == [(b"a", 1), (b"b", 2)]
