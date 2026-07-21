import waffle


def feature_flags(request):
    """
    Exposes all waffle flags and switches to templates and the frontend.
    Flags and switches are namespaced separately (rather than merged into
    one dict keyed by name) since Waffle allows a Flag and a Switch to
    share the same name — merging them would silently drop one's state
    on a collision.
    """
    Flag = waffle.get_waffle_flag_model()
    Switch = waffle.get_waffle_switch_model()

    flags_dict = {}
    switches_dict = {}

    if hasattr(request, 'user'):
        for flag in Flag.objects.all():
            flags_dict[flag.name] = {
                "enabled": waffle.flag_is_active(request, flag.name)
            }

    for switch in Switch.objects.all():
        switches_dict[switch.name] = {
            "enabled": waffle.switch_is_active(switch.name)
        }

    return {"feature_flags": {"flags": flags_dict, "switches": switches_dict}}