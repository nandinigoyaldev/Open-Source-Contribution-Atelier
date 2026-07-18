import waffle

def feature_flags(request):
    """
    Exposes all waffle flags and switches as a dictionary to templates and the frontend.
    """
    Flag = waffle.get_waffle_flag_model()
    Switch = waffle.get_waffle_switch_model()
    
    flags_dict = {}
    
    if hasattr(request, 'user'):
        for flag in Flag.objects.all():
            flags_dict[flag.name] = {
                "enabled": waffle.flag_is_active(request, flag.name)
            }
            
    for switch in Switch.objects.all():
        if switch.name not in flags_dict:
            flags_dict[switch.name] = {
                "enabled": waffle.switch_is_active(switch.name)
            }
            
    return {"feature_flags": flags_dict}
