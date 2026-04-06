from django.contrib import admin
from .models import Interview, Question

@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'created_at')
    list_filter = ('status',)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'interview', 'sequence_order', 'status', 'score')
    list_filter = ('status', 'type')
    search_fields = ('question_text', 'user_answer')
