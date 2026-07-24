from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny


class GitHubStatsInfoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "stars": 42,
                "forks": 12,
                "contributors": 7,
                "status": "Healthy and active!",
            }
        )
