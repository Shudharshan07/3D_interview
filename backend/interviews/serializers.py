from rest_framework import serializers
from .models import Interview, Question

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = '__all__'

class InterviewSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True, required=False)
    aggregate_score = serializers.SerializerMethodField()
    total_questions = serializers.SerializerMethodField()
    evaluated_questions = serializers.SerializerMethodField()
    
    class Meta:
        model = Interview
        fields = ['id', 'jd_text', 'resume_text', 'status', 'final_report', 'created_at', 'questions', 'aggregate_score', 'total_questions', 'evaluated_questions']
        read_only_fields = ['id', 'status', 'final_report', 'created_at', 'questions']

    def get_aggregate_score(self, obj):
        qs = obj.questions.all()
        scores = [q.score for q in qs if q.score is not None]
        if not scores:
            return 0
        return round(sum(scores) / len(qs), 1)

    def get_total_questions(self, obj):
        return obj.questions.count()

    def get_evaluated_questions(self, obj):
        return obj.questions.filter(status='EVALUATED').count()

class InterviewCreateSerializer(serializers.Serializer):
    jd_text = serializers.CharField(required=True)
    resume_text = serializers.CharField(required=True)

class AnswerSubmissionSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(required=True)
    answer = serializers.CharField(required=True)
    whiteboard_data = serializers.JSONField(required=False, allow_null=True)
