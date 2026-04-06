import sys
import os
sys.path.append(os.getcwd())

from ai_utils import InterviewAI

def test_generation():
    jd = """
    We are looking for a Senior Python Developer with experience in:
    - Django and Django Rest Framework
    - PostgreSQL and Redis
    - Celery for background tasks
    - Experience with LLMs and prompt engineering is a plus.
    """
    
    resume = """
    John Doe
    Python Developer with 5 years of experience.
    Skills: Python, Flask, Django, MySQL, RabbitMQ.
    Projects:
    - Built a real-time chat application using WebSockets and Redis.
    - Integrated OpenAI API for automated content generation.
    """
    
    print("Initializing AI...")
    ai = InterviewAI()
    
    print("Generating questions...")
    questions = ai.generate_questions(jd, resume)
    
    print("\nGenerated Questions:")
    for i, q in enumerate(questions):
        print(f"{i+1}. [{q['type']}] {q['text']}")

if __name__ == "__main__":
    test_generation()
