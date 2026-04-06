import os
from celery import Celery
from ai_utils import InterviewAI
import logging
from dotenv import load_dotenv

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env from root if it exists
# Root .env is likely in ../backend/.env relative to this file's directory
root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend', '.env')
if os.path.exists(root_env):
    logger.info(f"Loading environment from {root_env}")
    load_dotenv(root_env)

# Broker URL (Standardizing to Redis to match backend)
BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/1')
RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')

app = Celery('ai_worker', broker=BROKER_URL, backend=RESULT_BACKEND)

# Initialize AI Model (Loads once at startup)
ai = None

@app.task(name='interviews.tasks.generate_questions_ai_model', queue='inference')
def generate_questions_ai_model(jd_text, resume_text):
    global ai
    if ai is None:
        logger.info("Initializing AI Model for the first time...")
        ai = InterviewAI()
    
    logger.info("Generating questions from JD and Resume...")
    questions = ai.generate_questions(jd_text, resume_text)
    logger.info(f"Successfully generated {len(questions)} questions.")
    return questions

@app.task(name='interviews.tasks.evaluate_answer_ai_model', queue='inference')
def evaluate_answer_ai_model(question_text, user_answer, whiteboard_data=None):
    global ai
    if ai is None:
        logger.info("Initializing AI Model for the first time...")
        ai = InterviewAI()
    
    logger.info(f"Evaluating answer for question: {question_text[:50]}...")
    result = ai.evaluate_answer(question_text, user_answer, whiteboard_data)
    logger.info("Evaluation complete.")
    return result

if __name__ == '__main__':
    # Start the worker if run directly
    # Usage: celery -A worker worker -Q inference --loglevel=info
    print("AI Worker starting... Use celery command to run.")
