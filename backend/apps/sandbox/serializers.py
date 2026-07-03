from rest_framework import serializers
from .models import CodeSnapshot

class CodeSnapshotSerializer(serializers.ModelSerializer):
    is_auto = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = CodeSnapshot
        fields = ['id', 'user', 'code', 'timestamp', 'label', 'is_auto']
        read_only_fields = ['id', 'user', 'timestamp']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
