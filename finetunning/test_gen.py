import sys
import os

# Add the current directory to path
sys.path.append(os.getcwd())

from ai_utils import InterviewAI
import json

def test_gen():
    try:
        # Note: This requires the model to be present at ./llama_model_merged
        # If not present, we will wrap in try-except to see if we can at least test logic
        ai = InterviewAI()
        
        jd = "Senior React Developer with 5+ years experience. Must know Redux, TypeScript, and testing with Jest."
        resume = "Junior frontend dev with 2 years experience. Knows React, CSS, and basic JavaScript. Worked on personal projects."
        
        print("Testing with Senior JD vs Junior Resume...")
        questions = ai.generate_questions(jd, resume, num_questions=3, whiteboard_count=1, difficulty="Senior")
        
        print(f"Generated {len(questions)} questions:")
        print(json.dumps(questions, indent=2))
        
        assert len(questions) == 3
        types = [q['type'] for q in questions]
        assert "WHITEBOARD" in types
        
        print("\nSUCCESS: Questions generated and validated.")
        
    except Exception as e:
        print(f"Error during test: {e}")
        if "llama_model_merged" in str(e) or "Loading model" in str(e):
            print("Skipping full model test as model path might be missing in this environment.")
        else:
            raise e

if __name__ == "__main__":
    test_gen()
