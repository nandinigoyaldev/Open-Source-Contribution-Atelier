import pytest
from unittest.mock import patch
from apps.progress.models import CodeSubmission, PlagiarismReport
from apps.progress.services.plagiarism_detector import extract_ast_nodes, calculate_structural_similarity
from apps.progress.tasks import analyze_submission_plagiarism
from django.contrib.auth import get_user_model

User = get_user_model()


def test_ast_node_extraction():
    """
    Test that AST extraction ignores variable names and comments
    """
    code1 = """
def solve():
    x = 10
    # this is a comment
    return x * 2
    """

    code2 = """
def solution():
    value = 10
    return value * 2
    """

    # Nodes should match perfectly despite renaming and comments
    nodes1 = extract_ast_nodes(code1)
    nodes2 = extract_ast_nodes(code2)
    assert nodes1 == nodes2
    assert calculate_structural_similarity(code1, code2) == 1.0


def test_structural_similarity():
    """
    Test varying degrees of similarity.
    """
    base_code = """
def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)
"""
    diff_code = """
def sum_array(arr):
    total = 0
    for num in arr:
        total += num
    return total
"""
    # They should not be 1.0 structurally identical
    score = calculate_structural_similarity(base_code, diff_code)
    assert score < 0.6


@pytest.mark.django_db
def test_plagiarism_task_execution():
    user1 = User.objects.create(username="user1", email="u1@test.com")
    user2 = User.objects.create(username="user2", email="u2@test.com")

    # user1 submits code
    sub1 = CodeSubmission.objects.create(
        user=user1,
        title="Challenge 1",
        code_snippet="""
def solve(n):
    if n <= 1: return n
    return solve(n-1) + solve(n-2)
"""
    )

    # user2 submits identical logic but renamed variables
    sub2 = CodeSubmission.objects.create(
        user=user2,
        title="Challenge 1",
        code_snippet="""
def my_func(x):
    if x <= 1: return x
    return my_func(x-1) + my_func(x-2)
"""
    )

    # Note: signal might have already queued sub2 depending on settings, 
    # but we can explicitly call the task synchronously for testing.
    analyze_submission_plagiarism(sub2.id)

    # Verify a PlagiarismReport was generated
    reports = PlagiarismReport.objects.filter(submission=sub2)
    assert reports.count() == 1
    
    report = reports.first()
    assert report.matched_submission == sub1
    assert report.similarity_score == 1.0
    assert report.is_flagged is True


@pytest.mark.django_db
def test_plagiarism_task_avoids_self_and_unrelated():
    user = User.objects.create(username="user1", email="u1@test.com")
    sub1 = CodeSubmission.objects.create(
        user=user,
        title="Challenge 2",
        code_snippet="print('hello')"
    )
    # Self-submission shouldn't trigger plagiarism reports
    analyze_submission_plagiarism(sub1.id)
    assert PlagiarismReport.objects.count() == 0
