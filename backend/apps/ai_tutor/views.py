from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import AiTutorService


class TutorAskView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        question = request.data.get("question", "").strip()
        lesson_slug = request.data.get("lesson_slug", "")
        history = request.data.get("history", [])

        if not question:
            return Response(
                {"error": "Question is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lesson_context = ""
        if lesson_slug:
            try:
                from apps.content.models import Lesson

                lesson = Lesson.objects.filter(slug=lesson_slug).first()
                if lesson:
                    summary_text = getattr(lesson, "summary", "") or getattr(
                        lesson, "description", ""
                    )
                    lesson_context = (
                        f"Lesson title: {lesson.title}\nSummary: {summary_text[:500]}"
                    )
            except Exception:
                pass

        answer = AiTutorService.get_response(
            question=question,
            lesson_context=lesson_context,
            history=history,
        )

        return Response({"answer": answer})
