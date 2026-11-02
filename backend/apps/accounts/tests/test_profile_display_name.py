from apps.accounts.serializers import UserListSerializer, UserUpdateSerializer


def test_update_serializer_accepts_display_name():
    serializer = UserUpdateSerializer(data={"first_name": "  Chanchal  "})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["first_name"] == "Chanchal"


def test_update_serializer_allows_blank_display_name():
    serializer = UserUpdateSerializer(data={"first_name": ""})
    assert serializer.is_valid(), serializer.errors


def test_update_serializer_rejects_overlong_display_name():
    serializer = UserUpdateSerializer(data={"first_name": "x" * 151})
    assert not serializer.is_valid()
    assert "first_name" in serializer.errors


def test_user_serializer_exposes_display_name():
    assert "first_name" in UserListSerializer.Meta.fields
