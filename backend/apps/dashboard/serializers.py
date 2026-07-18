from rest_framework import serializers
from .models import DashboardWidget

class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = ['id', 'widget_type', 'title', 'position_x', 'position_y', 'width', 'height', 'visible', 'config']