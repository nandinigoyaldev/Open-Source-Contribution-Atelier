from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageCms
from rest_framework.test import APIClient

from apps.accounts import serializers as account_serializers
from apps.accounts.models import UserProfile

ORIENTATION = 0x0112
CAMERA_MODEL = 0x0110


def _photo(image_format, orientation):
    """A 40x20 landscape image, red on the left half, with EXIF data."""
    img = Image.new("RGB", (40, 20), (0, 0, 255))
    img.paste((255, 0, 0), (0, 0, 20, 20))
    exif = Image.Exif()
    exif[ORIENTATION] = orientation
    exif[CAMERA_MODEL] = "PhoneCam"
    buffer = BytesIO()
    img.save(buffer, format=image_format, exif=exif.tobytes(), quality=95)
    return SimpleUploadedFile(f"photo.{image_format.lower()}", buffer.getvalue())


@pytest.mark.django_db
@pytest.mark.parametrize("image_format", ["JPEG", "WEBP"])
def test_avatar_is_rotated_upright_and_exif_is_removed(
    settings, tmp_path, image_format
):
    settings.MEDIA_ROOT = tmp_path
    user = get_user_model().objects.create_user(username="exif", password="pw-12345!")
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # Orientation 6: the viewer has to rotate the image 90 degrees clockwise.
    profile.avatar = _photo(image_format, orientation=6)
    profile.save()

    with profile.avatar.open("rb") as stored:
        result = Image.open(stored)
        result.load()

    assert result.format == "WEBP"
    assert result.size == (20, 40)
    red, _, blue = result.convert("RGB").getpixel((10, 5))
    assert red > 200 and blue < 60
    assert not result.getexif()


def _save_avatar(settings, tmp_path, upload):
    settings.MEDIA_ROOT = tmp_path
    user = get_user_model().objects.create_user(username="webp", password="pw-12345!")
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.avatar = upload
    profile.save()
    with profile.avatar.open("rb") as stored:
        return Image.open(BytesIO(stored.read()))


@pytest.mark.django_db
def test_xmp_metadata_is_removed_from_webp_uploads(settings, tmp_path):
    buffer = BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="WEBP", xmp=b"<x:xmpmeta/>")
    upload = SimpleUploadedFile("tagged.webp", buffer.getvalue())

    result = _save_avatar(settings, tmp_path, upload)

    assert not result.info.get("xmp")


@pytest.mark.django_db
def test_animated_webp_keeps_its_frames_and_is_rotated(settings, tmp_path):
    exif = Image.Exif()
    exif[ORIENTATION] = 6
    frames = [Image.new("RGB", (40, 20), colour) for colour in ("red", "blue")]
    buffer = BytesIO()
    frames[0].save(
        buffer,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=[120, 240],
        loop=3,
        exif=exif.tobytes(),
    )
    upload = SimpleUploadedFile("moving.webp", buffer.getvalue())

    result = _save_avatar(settings, tmp_path, upload)

    assert result.n_frames == 2
    assert result.info["loop"] == 3
    assert not result.getexif()
    durations = []
    for index in range(result.n_frames):
        result.seek(index)
        result.load()
        assert result.size == (20, 40)
        durations.append(result.info["duration"])
    assert durations == [120, 240]


@pytest.mark.django_db
def test_color_profile_survives_the_conversion(settings, tmp_path):
    profile_bytes = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    buffer = BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="WEBP", icc_profile=profile_bytes)
    upload = SimpleUploadedFile("profiled.webp", buffer.getvalue())

    result = _save_avatar(settings, tmp_path, upload)

    assert result.info.get("icc_profile") == profile_bytes


@pytest.mark.django_db
def test_oversized_animation_is_stored_as_its_first_frame(
    settings, tmp_path, monkeypatch
):
    monkeypatch.setattr("apps.accounts.models.MAX_ANIMATION_PIXELS", 100)
    frames = [Image.new("RGB", (40, 20), colour) for colour in ("red", "blue")]
    buffer = BytesIO()
    frames[0].save(buffer, format="WEBP", save_all=True, append_images=frames[1:])
    upload = SimpleUploadedFile("huge.webp", buffer.getvalue())

    result = _save_avatar(settings, tmp_path, upload)

    assert getattr(result, "n_frames", 1) == 1
    red, _, blue = result.convert("RGB").getpixel((5, 5))
    assert red > 200 and blue < 60


def _two_frames(name):
    frames = [Image.new("RGB", (40, 20), colour) for colour in ("red", "blue")]
    buffer = BytesIO()
    frames[0].save(buffer, format="WEBP", save_all=True, append_images=frames[1:])
    return SimpleUploadedFile(name, buffer.getvalue(), "image/webp")


@pytest.mark.parametrize("filename", ["huge.webp", "photo.png"])
@pytest.mark.parametrize(
    "serializer_name, field",
    [
        ("AvatarUploadSerializer", "avatar"),
        ("UserUpdateSerializer", "avatar"),
        ("UserUpdateSerializer", "cover_image"),
    ],
)
def test_oversized_animation_is_rejected_by_the_serializer(
    monkeypatch, serializer_name, field, filename
):
    monkeypatch.setattr("apps.accounts.models.MAX_ANIMATION_PIXELS", 100)
    serializer_class = getattr(account_serializers, serializer_name)

    serializer = serializer_class(data={field: _two_frames(filename)}, partial=True)

    assert not serializer.is_valid()
    assert "too large" in str(serializer.errors[field][0])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method, url, field",
    [
        ("post", "/api/auth/profile/avatar/", "avatar"),
        ("put", "/api/auth/me/", "avatar"),
        ("put", "/api/auth/me/", "cover_image"),
    ],
)
def test_oversized_animation_upload_returns_400(monkeypatch, method, url, field):
    monkeypatch.setattr("apps.accounts.models.MAX_ANIMATION_PIXELS", 100)
    user = get_user_model().objects.create_user(username="http", password="pw-12345!")
    client = APIClient()
    client.force_authenticate(user)

    response = getattr(client, method)(
        url, {field: _two_frames("photo.png")}, format="multipart", secure=True
    )

    assert response.status_code == 400
    assert "too large" in response.content.decode()


@pytest.mark.django_db
def test_animation_named_png_keeps_its_frames(settings, tmp_path):
    result = _save_avatar(settings, tmp_path, _two_frames("photo.png"))

    assert result.n_frames == 2
