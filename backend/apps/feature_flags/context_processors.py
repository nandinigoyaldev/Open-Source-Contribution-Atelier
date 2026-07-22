import waffle
from django.core.cache import cache


def feature_flags(request):
    """
    Exposes all waffle flags and switches to templates/frontend.
    Cached for 30s to avoid two full-table queries on every request —
    flag/switch state changes are infrequent (admin toggles), so a short
    staleness window is an acceptable tradeoff for the reduced DB load.
    """
    if not hasattr(request, 'user'):
        return {"feature_flags": {"flags": {}, "switches": {}}}

    cache_key = "waffle_flags_switches_v1"
    cached = cache.get(cache_key)

    if cached is None:
        Flag = waffle.get_waffle_flag_model()
        Switch = waffle.get_waffle_switch_model()
        cached = {
            "flag_names": list(Flag.objects.values_list("name", flat=True)),
            "switch_states": {
                s.name: waffle.switch_is_active(s.name)
                for s in Switch.objects.all()
            },
        }
        cache.set(cache_key, cached, timeout=30)

    flags_dict = {
        name: {"enabled": waffle.flag_is_active(request, name)}
        for name in cached["flag_names"]
    }
    switches_dict = {
        name: {"enabled": enabled}
        for name, enabled in cached["switch_states"].items()
    }

    return {"feature_flags": {"flags": flags_dict, "switches": switches_dict}}