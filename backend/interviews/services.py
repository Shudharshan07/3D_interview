import random
from .models import Interview, Question
from .tasks import process_answer_ai

class InterviewService:
    @staticmethod
    def create_interview(jd_text, resume_text):
        interview = Interview.objects.create(
            jd_text=jd_text,
            resume_text=resume_text,
            status='PENDING'
        )
        
        # Trigger AI question generation task
        from .tasks import generate_questions_task
        generate_questions_task.delay(interview.id)
            
        return interview

    @staticmethod
    def get_interview_report(interview_uuid):
        try:
            interview = Interview.objects.get(id=interview_uuid)
            questions = interview.questions.all()
            
            total_score = 0
            evaluated_count = 0
            feedback_list = []
            
            for q in questions:
                if q.status == 'EVALUATED' and q.score is not None:
                    total_score += q.score
                    evaluated_count += 1
                    feedback_list.append(f"Q{q.sequence_order}: {q.feedback_text}")
            
            avg_score = round(total_score / evaluated_count, 1) if evaluated_count > 0 else 0
            
            report = {
                'aggregate_score': avg_score,
                'summary_feedback': "\n".join(feedback_list),
                'total_questions': questions.count(),
                'evaluated_questions': evaluated_count
            }
            
            interview.final_report = report
            interview.status = 'COMPLETED' if evaluated_count == questions.count() else interview.status
            interview.save()
            
            return report
        except Interview.DoesNotExist:
            return None

class QuestionService:
    @staticmethod
    def submit_answer(question_id, user_answer, whiteboard_json_data):
        try:
            question = Question.objects.get(id=question_id)
            question.user_answer = user_answer
            question.whiteboard_json_data = whiteboard_json_data
            question.status = 'ANSWERED'
            question.save()
            
            # Start interview if Not already
            if question.interview.status == 'PENDING':
                question.interview.status = 'IN_PROGRESS'
                question.interview.save()

            # Trigger Celery Task
            process_answer_ai.delay(question.id)
            
            return question
        except Question.DoesNotExist:
            return None
