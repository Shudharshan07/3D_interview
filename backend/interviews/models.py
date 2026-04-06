import uuid
from django.db import models

class Interview(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jd_text = models.TextField()
    resume_text = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    final_report = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Interview {self.id} - {self.status}"

class Question(models.Model):
    TYPE_CHOICES = [
        ('TECHNICAL', 'Technical'),
        ('WHITEBOARD', 'Whiteboard'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ANSWERED', 'Answered'),
        ('EVALUATED', 'Evaluated'),
    ]

    interview = models.ForeignKey(Interview, related_name='questions', on_delete=models.CASCADE)
    question_text = models.TextField()
    sequence_order = models.IntegerField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    user_answer = models.TextField(null=True, blank=True)
    whiteboard_json_data = models.JSONField(null=True, blank=True)
    feedback_text = models.TextField(null=True, blank=True)
    score = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['sequence_order']

    def __str__(self):
        return f"Question {self.sequence_order} for Interview {self.interview.id}"
