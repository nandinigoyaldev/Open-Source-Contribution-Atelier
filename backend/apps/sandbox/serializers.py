from rest_framework import serializers
from .models import CodeSnapshot, Project, ProjectFile

class CodeSnapshotSerializer(serializers.ModelSerializer):
    is_auto = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = CodeSnapshot
        fields = ['id', 'user', 'code', 'timestamp', 'label', 'is_auto']
        read_only_fields = ['id', 'user', 'timestamp']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ProjectFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = ['id', 'project', 'path', 'content', 'language', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProjectSerializer(serializers.ModelSerializer):
    files = ProjectFileSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'user', 'name', 'files', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


from .models import CodeExecutionTrace

class CodeExecutionTraceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeExecutionTrace
        fields = ['id', 'user', 'code', 'trace_events', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

