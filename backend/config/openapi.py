from drf_spectacular.openapi import AutoSchema


class ThrottleAutoSchema(AutoSchema):
    """
    Custom AutoSchema to automatically document HTTP 429 Too Many Requests
    responses for endpoints that have throttling enabled.
    """

    def get_responses(self):
        responses = super().get_responses()

        # Check if the view uses throttles
        get_throttles = getattr(self.view, "get_throttles", None)
        if get_throttles and get_throttles():
            # drf-spectacular expects standard OpenAPI dicts in the response map
            if "429" not in responses:
                responses["429"] = {
                    "description": "Too Many Requests - Rate limit exceeded.",
                }

        return responses
