import json
import logging

logger = logging.getLogger(__name__)
from django.http import StreamingHttpResponse
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
            except Exception as e:
                logger.warning("Caught exception: %s", e)

        def event_stream():
            try:
                # Assumes AiTutorService provides a generator method for streaming chunks,
                # e.g., AiTutorService.get_streaming_response(...)
                stream_generator = getattr(
                    AiTutorService, "get_streaming_response", None
                )
                
                if stream_generator:
                    for chunk in stream_generator(
                        question=question,
                        lesson_context=lesson_context,
                        history=history,
                    ):
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                else:
                    # Fallback if streaming isn't natively configured on service yet
                    answer = AiTutorService.get_response(
                        question=question,
                        lesson_context=lesson_context,
                        history=history,
                    )
                    yield f"data: {json.dumps({'chunk': answer})}\n\n"

                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error("Streaming error: %s", e)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
