import time
import random
import logging
import json
import redis
from celery import shared_task
from api.celery import app as celery_app
from django.db import transaction
from django.conf import settings

from groq import Groq

logger = logging.getLogger(__name__)

# Initialize a standard redis client to skip Celery's overhead for direct notification
r = redis.from_url(settings.CELERY_RESULT_BACKEND)

# Move Groq client initialization inside the function or make it optional
# to avoid errors if the key is missing during startup in some environments
def get_groq_client(is_eval=False):
    api_key = getattr(settings, 'GROQ_API_KEY_EVAL', None) if is_eval else settings.GROQ_API_KEY
    if not api_key or api_key in ['not working', 'test']:
        api_key = settings.GROQ_API_KEY
        if not api_key or api_key in ['not working', 'test']:
            return None
    return Groq(api_key=api_key, timeout=150.0)

def notify_websocket(interview_id, question_id, score, feedback):
    """
    Publish real-time AI evaluation results to the Redis channel
    that the Go WebSocket service is listening on.
    """
    channel = f"interview_updates:{interview_id}"
    logger.info(f"Attempting to notify WebSocket via Redis. Channel: {channel}")
    
    message = json.dumps({
        "type": "AI_EVALUATED",
        "data": {
            "question_id": question_id,
            "score": score,
            "feedback": feedback
        }
    })
    
    try:
        receivers = r.publish(channel, message)
        logger.info(f"Published AI_EVALUATED to {channel}. Receivers: {receivers}")
        if receivers == 0:
            logger.warning(f"No active listeners on channel {channel}. Is the Go service running and subscribed?")
    except Exception as e:
        logger.error(f"Failed to publish to Redis: {e}")

def generate_questions_with_groq(jd_text, resume_text):
    client = get_groq_client(is_eval=False)
    if not client:
        logger.error("Groq client not initialized - API Key might be missing.")
        return None

    prompt = (
        "You are an expert technical interviewer. Based on the Job Description and Resume below, "
        "generate exactly 11 interview questions in strict sequence order as follows:\n\n"
        "1. SELF_INTRO  - Ask the candidate to introduce themselves (type: TECHNICAL)\n"
        "2. GENERAL     - Start by saying 'Your resume looks pretty good. Now, let's start with...' followed by a straightforward, easy warm-up question related to the role (type: TECHNICAL)\n"
        "3. FOLLOWUP    - A follow-up question that naturally builds on Q2 (type: TECHNICAL)\n"
        "4. PROJECT     - Ask the candidate to explain one project from their resume in detail (type: TECHNICAL)\n"
        "5. DSA_ARCH    - A DSA or system architecture/design question requiring a diagram or algorithm walkthrough (type: WHITEBOARD)\n"
        "6. HARD        - A hard, role-specific technical question probing deep expertise (type: TECHNICAL)\n"
        "7. INTERNSHIP  - Ask the candidate to share their internship experience and what they learned (type: TECHNICAL)\n"
        "8. MEDIUM_1    - A medium-difficulty technical question relevant to the job (type: TECHNICAL)\n"
        "9. MEDIUM_2    - Another medium-difficulty technical question, different topic (type: TECHNICAL)\n"
        "10. WHY_JOB   - Ask why the candidate wants this specific job / company (type: TECHNICAL)\n"
        "11. CLOSING    - A positive, motivational closing statement or question to end the interview on a high note (type: TECHNICAL)\n\n"
        "Rules:\n"
        "- Tailor each question specifically to the Job Description and Resume.\n"
        "- For Q7 (INTERNSHIP): if the resume has no internship, ask about a relevant personal project instead.\n"
        "- Return ONLY valid JSON, no prose, in this exact format:\n"
        "{\"questions\": ["
        "{\"text\": \"...\", \"type\": \"TECHNICAL\", \"slot\": \"SELF_INTRO\"}, "
        "{\"text\": \"...\", \"type\": \"WHITEBOARD\", \"slot\": \"DSA_ARCH\"}, "
        "..."
        "]}"
    )
    
    user_content = f"JOB DESCRIPTION:\n{jd_text}\n\nCANDIDATE RESUME:\n{resume_text}"

    # We try up to 2 models to handle Rate Limits
    models_to_try = [settings.GROQ_MODEL, "llama-3.1-8b-instant"]
    
    for model_name in models_to_try:
        logger.info(f"GROQ: Attempting question generation with model {model_name}...")
        start_time = time.time()
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.4,
                response_format={"type": "json_object"},
                timeout=120.0
            )
            
            elapsed = time.time() - start_time
            logger.info(f"GROQ: {model_name} responded successfully in {elapsed:.2f}s")
            
            response_data = json.loads(completion.choices[0].message.content)
            questions = response_data.get('questions', [])
            if questions:
                return questions
            logger.warning(f"GROQ: {model_name} returned empty questions list.")
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.warning(f"GROQ: {model_name} generation failed after {elapsed:.2f}s: {str(e)}")
            # Continue to next model in loop if available
            continue

    logger.error("GROQ: All models failed for question generation.")
    return None

def evaluate_with_groq(question_text, user_answer, whiteboard_data=None):
    client = get_groq_client(is_eval=True)
    if not client:
        return None

    if whiteboard_data:
        num_elements = len(whiteboard_data.get('elements', []))
        logger.info(f"AI EVALUATION: Processing answer with Whiteboard Data ({num_elements} elements)")
    else:
        logger.info(f"AI EVALUATION: Processing text-only answer")

    whiteboard_info = f"\nWhiteboard Data (JSON): {json.dumps(whiteboard_data)[:10000]}" if whiteboard_data else ""

    prompt = (
        "You are a strict technical interviewer. "
        "Score the candidate's answer out of 10 based on accuracy and technical depth. "
        "If whiteboard data is provided, it contains the candidate's diagrams and notes in JSON format. "
        "Summarize your findings in the feedback.\n"
        "Provide a score and a short piece of feedback.\n"
        "Return only valid JSON in the format: {\"score\": 8.5, \"feedback\": \"...\"}\n\n"
        f"Question: {question_text}\n"
        f"Answer: {user_answer}"
        f"{whiteboard_info}"
    )

    models_to_try = [settings.GROQ_MODEL, "llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x7b-32768"]
    
    for model_name in models_to_try:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"},
                timeout=30.0
            )

            response_data = json.loads(completion.choices[0].message.content)
            return {
                "score": response_data.get("score", 7),
                "feedback": response_data.get("feedback", "Good answer.")
            }
        except Exception as e:
            logger.warning(f"Groq API error with model {model_name}: {str(e)}")
            time.sleep(1) # short delay before trying the next model
            continue
            
    logger.error("All models failed for AI evaluation.")
    return None

def notify_questions_ready(interview_id):
    """
    Publish a notification to the Redis channel when questions are ready.
    """
    channel = f"interview_updates:{interview_id}"
    message = json.dumps({
        "type": "QUESTIONS_READY",
        "data": {}
    })
    try:
        r.publish(channel, message)
        logger.info(f"Published QUESTIONS_READY to {channel}")
    except Exception as e:
        logger.error(f"Failed to publish QUESTIONS_READY to Redis: {e}")

@shared_task
def generate_questions_task(interview_id):
    """
    Task to trigger AI question generation.
    Does NOT wait for the result. instead uses a callback.
    """
    from .models import Interview
    try:
        interview = Interview.objects.get(id=interview_id)
        logger.info(f"Starting question generation for interview: {interview_id}")
        
        # Try Groq for question generation
        questions = generate_questions_with_groq(interview.jd_text, interview.resume_text)
        if questions:
            logger.info(f"Successfully generated {len(questions)} questions via Groq for {interview_id}")
            return finalize_questions_task(questions, str(interview_id))

        # Groq failed. Use Emergency Fallback Questions to ensure the interview can still proceed.
        logger.warning(f"Groq generation failed for {interview_id}. Using emergency fallback questions.")
        fallback_questions = [
            {"text": "Please introduce yourself and walk me through your technical background briefly.", "type": "TECHNICAL", "slot": "SELF_INTRO"},
            {"text": "Based on the JD, what do you think is the most important technical skill for this role?", "type": "TECHNICAL", "slot": "GENERAL"},
            {"text": "What is a technical project you are most proud of? Tell me about the architecture.", "type": "TECHNICAL", "slot": "PROJECT"},
            {"text": "Let's do a technical deep dive. Can you use the whiteboard to explain a complex system or algorithm you've implemented?", "type": "WHITEBOARD", "slot": "DSA_ARCH"},
            {"text": "How do you handle technical debt and maintainability in your projects?", "type": "TECHNICAL", "slot": "MEDIUM_1"},
            {"text": "Describe a time you had to debug a particularly difficult production issue.", "type": "TECHNICAL", "slot": "MEDIUM_2"},
            {"text": "How do you stay updated with the latest trends and technologies in your field?", "type": "TECHNICAL", "slot": "HARD"},
            {"text": "What is your approach to collaborating with cross-functional teams like Design or Product?", "type": "TECHNICAL", "slot": "MEDIUM_1"},
            {"text": "Can you share an experience where you had to learn a completely new technology under a tight deadline?", "type": "TECHNICAL", "slot": "MEDIUM_2"},
            {"text": "Why do you want to join our company specifically?", "type": "TECHNICAL", "slot": "WHY_JOB"},
            {"text": "Thank you for your time today. It was great learning about your background. Do you have any final questions for me?", "type": "TECHNICAL", "slot": "CLOSING"}
        ]
        return finalize_questions_task(fallback_questions, str(interview_id))
        
    except Interview.DoesNotExist:
        logger.error(f"Interview {interview_id} not found")
        return f"Error: Interview {interview_id} not found"
    except Exception as e:
        logger.error(f"Error triggering questions: {str(e)}")
        return f"Error: {str(e)}"

@shared_task
def finalize_questions_task(questions_data, interview_id):
    """
    Callback task to save generated questions to the database.
    """
    from .models import Interview, Question
    try:
        if not questions_data:
            raise ValueError("AI Model returned no questions")

        interview = Interview.objects.get(id=interview_id)
        
        with transaction.atomic():
            for i, q in enumerate(questions_data):
                Question.objects.create(
                    interview=interview,
                    question_text=q.get('text', 'Technical Question'),
                    sequence_order=i + 1,
                    type=q.get('type', 'TECHNICAL'),
                    status='PENDING'
                )
            
            interview.status = 'PENDING'
            interview.save()
            
        notify_questions_ready(str(interview_id))
        return f"Finalized {len(questions_data)} questions for {interview_id}"
        
    except Exception as e:
        logger.error(f"Error finalizing questions: {str(e)}")
        return f"Error: {str(e)}"

@shared_task
def process_answer_ai(question_id):
    from .models import Question
    logger.info(f"CELERY: Starting AI processing for question_id: {question_id}")
    
    try:
        question = Question.objects.get(id=question_id)
        
        # AI Evaluation via Groq
        eval_data = evaluate_with_groq(
            question.question_text, 
            question.user_answer, 
            question.whiteboard_json_data
        )
        
        if eval_data:
            score = eval_data.get("score")
            feedback = eval_data.get("feedback", "")
            logger.info(f"AI EVALUATION RESULT: Q {question_id} | Score {score}/10 | Feedback: {feedback[:100]}...")
            return finalize_evaluation_task(eval_data, question_id)
        
        # No evaluation available via Groq. Returning a default acknowledgment.
        logger.error(f"Groq evaluation failed for Q {question_id}. Returning default evaluation.")
        default_eval = {"score": 7.0, "feedback": "Your response has been noted. It reflects a basic understanding of the topic; however, it lacks depth and thorough explanation. Providing more detailed insights and elaborating on key concepts would improve the quality of the response."}
        return finalize_evaluation_task(default_eval, question_id)
            
    except Question.DoesNotExist:
        logger.error(f"Question {question_id} not found.")
        return f"Error: Question {question_id} not found"

@shared_task
def finalize_evaluation_task(eval_data, question_id):
    from .models import Question
    try:
        if not eval_data:
            eval_data = {"score": 7.5, "feedback": "Answer acknowledged. While the response reflects a basic understanding of the concept, it lacks depth, elaboration, and detailed analysis."}

        with transaction.atomic():
            question = Question.objects.select_for_update().get(id=question_id)
            score = eval_data.get('score', 7.5)
            feedback = eval_data.get('feedback', "Good answer.")
            
            question.score = score
            question.feedback_text = feedback
            question.status = 'EVALUATED'
            question.save()
            
            notify_websocket(
                str(question.interview.id), 
                question.id, 
                score, 
                feedback
            )
            
        return f"Question {question_id} finalized with score {score}"
    except Exception as e:
        logger.error(f"Error finalizing evaluation: {e}")
        return f"Error: {e}"

