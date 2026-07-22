from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Category, IssueCategoryAssignment, IssueTag, IssueTagAssignment, CategorySuggestion
from .serializers import CategorySerializer, IssueCategoryAssignmentSerializer, IssueTagSerializer, IssueTagAssignmentSerializer, CategorySuggestionSerializer

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

class IssueCategoryAssignmentViewSet(viewsets.ModelViewSet):
    queryset = IssueCategoryAssignment.objects.all()
    serializer_class = IssueCategoryAssignmentSerializer
    permission_classes = [IsAuthenticated]

class IssueTagViewSet(viewsets.ModelViewSet):
    queryset = IssueTag.objects.all()
    serializer_class = IssueTagSerializer
    permission_classes = [IsAuthenticated]

class IssueTagAssignmentViewSet(viewsets.ModelViewSet):
    queryset = IssueTagAssignment.objects.all()
    serializer_class = IssueTagAssignmentSerializer
    permission_classes = [IsAuthenticated]

class CategorySuggestionViewSet(viewsets.ModelViewSet):
    queryset = CategorySuggestion.objects.all()
    serializer_class = CategorySuggestionSerializer
    permission_classes = [IsAuthenticated]

