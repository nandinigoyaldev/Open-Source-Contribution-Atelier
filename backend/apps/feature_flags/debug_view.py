from django.shortcuts import render


def feature_flags_debug_view(request):
    return render(request, "feature_flags_debug.html")
