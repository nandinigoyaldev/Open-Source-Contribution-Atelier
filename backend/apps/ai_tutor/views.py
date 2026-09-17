import logging

from django.http import StreamingHttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import AiTutorService
from .throttles import AiTutorRateThrottle

logger = logging.getLogger(__name__)


class TutorAskView(APIView):
    """Main AI Tutor endpoint handling Socratic questions, attempts, and hints.

    Accepts POST with:
    - question: str
    - lesson_slug: optional str
    - history: optional list of {question, answer}
    - action: optional str ('ask' | 'evaluate' | 'hint')
    - expected_command: optional str (for 'evaluate' action)
    - hint_level: optional int (1, 2, 3 for 'hint' action)
    - stream: optional bool (default True)
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AiTutorRateThrottle]

    def post(self, request):
        action = request.data.get("action", "ask")
        question = request.data.get("question", "").strip()
        lesson_slug = request.data.get("lesson_slug", "")
        history = request.data.get("history", [])
        expected_command = request.data.get("expected_command", "")
        hint_level = int(request.data.get("hint_level", 1))
        stream = request.data.get("stream", True)
        learner_level = request.data.get("learner_level", "beginner")

        lesson_context = ""
        lesson_title = ""
        if lesson_slug:
            try:
                from apps.content.models import Lesson

                lesson = Lesson.objects.filter(slug=lesson_slug).first()
                if lesson:
                    lesson_title = lesson.title
                    summary_text = getattr(lesson, "summary", "") or getattr(
                        lesson, "description", ""
                    )
                    lesson_context = (
                        f"Lesson: {lesson.title}\nCategory: {lesson.category}\n"
                        f"Summary: {summary_text[:400]}"
                    )
            except Exception as e:
                logger.warning("Caught exception fetching lesson: %s", e)

        # Build structured tutor context
        tutor_context = AiTutorService.build_tutor_context(
            learner_level=learner_level,
            current_lesson=lesson_title or "General Open Source",
            exercise_prompt=expected_command,
        )

        # Handle 'evaluate' action
        if action == "evaluate":
            if not question:
                return Response(
                    {"error": "User input or command is required for evaluation."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            result = AiTutorService.evaluate_attempt(
                user_input=question,
                expected_concept_or_command=expected_command,
                lesson_context=lesson_context,
                tutor_context=tutor_context,
            )
            return Response(result, status=status.HTTP_200_OK)

        # Handle 'hint' action
        if action == "hint":
            hint_text = AiTutorService.get_hint(
                hint_level=hint_level,
                topic_or_exercise=expected_command or question or lesson_title,
                lesson_context=lesson_context,
            )
            return Response(
                {"hint": hint_text, "hint_level": hint_level},
                status=status.HTTP_200_OK,
            )

        # Handle 'ask' action (default)
        if not question:
            return Response(
                {"error": "Question is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not stream:
            answer = AiTutorService.get_response(
                question=question,
                lesson_context=lesson_context,
                history=history,
                tutor_context=tutor_context,
            )
            return Response({"answer": answer}, status=status.HTTP_200_OK)

        stream_generator = AiTutorService.get_streaming_response(
            question=question,
            lesson_context=lesson_context,
            history=history,
            tutor_context=tutor_context,
        )

        return StreamingHttpResponse(
            stream_generator,
            content_type="text/event-stream",
        )


class TutorEvaluateView(APIView):
    """Convenience dedicated endpoint for evaluating learner attempts."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user_input = request.data.get("user_input", "").strip()
        expected = request.data.get("expected", "").strip()
        lesson_slug = request.data.get("lesson_slug", "")

        if not user_input:
            return Response(
                {"error": "user_input is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        evaluation = AiTutorService.evaluate_attempt(
            user_input=user_input,
            expected_concept_or_command=expected,
        )
        return Response(evaluation, status=status.HTTP_200_OK)
