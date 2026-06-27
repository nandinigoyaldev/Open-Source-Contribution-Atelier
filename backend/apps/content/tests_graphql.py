import pytest
from apps.content.models import Exercise, Lesson, Organization
from config.schema import schema
from graphene.test import Client


@pytest.fixture
def graphene_client():
    return Client(schema)


@pytest.fixture
def setup_data():
    org = Organization.objects.create(
        name="GraphQL Org", slug="graphql-org", popularity_score=100
    )
    lesson = Lesson.objects.create(
        organization=org,
        difficulty="Beginner",
        title="Intro to GraphQL",
        slug="intro-to-graphql",
        summary="A summary",
        content="Some content",
        estimated_minutes=15,
        order=1,
    )
    exercise = Exercise.objects.create(
        lesson=lesson,
        title="First Exercise",
        prompt="Do something",
        expected_command="do something",
        points=10,
    )
    return org, lesson, exercise


class DummyUser:
    def __init__(self, organization=None, is_authenticated=True):
        self.organization = organization
        self.organization_id = organization.id if organization else None
        self.is_authenticated = is_authenticated


class DummyContext:
    def __init__(self, user):
        self.user = user


@pytest.mark.django_db
def test_all_lessons_query_unauthenticated(graphene_client, setup_data):
    # Unauthenticated should return all
    context = DummyContext(DummyUser(is_authenticated=False))
    query = """
    query {
      allLessons {
        id
        title
        slug
        exercises {
          title
        }
      }
    }
    """
    result = graphene_client.execute(query, context_value=context)
    assert "errors" not in result
    assert len(result["data"]["allLessons"]) == 1
    assert result["data"]["allLessons"][0]["title"] == "Intro to GraphQL"
    assert result["data"]["allLessons"][0]["exercises"][0]["title"] == "First Exercise"


@pytest.mark.django_db
def test_lesson_by_slug(graphene_client, setup_data):
    context = DummyContext(DummyUser(is_authenticated=False))
    query = """
    query {
      lessonBySlug(slug: "intro-to-graphql") {
        id
        title
      }
    }
    """
    result = graphene_client.execute(query, context_value=context)
    assert "errors" not in result
    assert result["data"]["lessonBySlug"]["title"] == "Intro to GraphQL"


@pytest.mark.django_db
def test_all_organizations(graphene_client, setup_data):
    context = DummyContext(DummyUser(is_authenticated=False))
    query = """
    query {
      allOrganizations {
        name
        slug
      }
    }
    """
    result = graphene_client.execute(query, context_value=context)
    assert "errors" not in result
    assert len(result["data"]["allOrganizations"]) == 1
    assert result["data"]["allOrganizations"][0]["name"] == "GraphQL Org"
