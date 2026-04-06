from transformers import AutoModelForCausalLM, AutoTokenizer, LlamaTokenizerFast, BitsAndBytesConfig
import torch
import json
import re

class InterviewAI:
    def __init__(self, model_path="./llama_model_merged"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading model on {self.device}...")
        
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        ) if self.device == "cuda" else None

        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            quantization_config=bnb_config,
        )

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        except:
            self.tokenizer = LlamaTokenizerFast.from_pretrained(model_path)
        
        print("Model loaded successfully.")

    def generate_questions(self, jd_text, resume_text, num_questions=11, whiteboard_count=1, difficulty="Senior"):
        """
        Generates 11 structured interview questions based on JD and Resume.
        Follows the fixed interview format:
        1-Self Intro, 2-General, 3-Followup, 4-Project, 5-DSA/Arch(Whiteboard),
        6-Hard, 7-Internship, 8-Medium, 9-Medium, 10-Why Job, 11-Closing
        """
        system_prompt = (
            "You are an expert technical interviewer at a top-tier tech company. "
            "Generate exactly 11 interview questions in strict sequence, following this format:\n\n"
            "1. SELF_INTRO  - Ask the candidate to introduce themselves (type: TECHNICAL)\n"
            "2. GENERAL     - Start by saying 'Your resume looks pretty good. Now, let's start with...' followed by an easy warm-up question relevant to the role (type: TECHNICAL)\n"
            "3. FOLLOWUP    - A follow-up that naturally builds on Q2 (type: TECHNICAL)\n"
            "4. PROJECT     - Ask candidate to explain a project from their resume (type: TECHNICAL)\n"
            "5. DSA_ARCH    - A DSA or system architecture question requiring diagram/walkthrough (type: WHITEBOARD)\n"
            "6. HARD        - A hard, role-specific deep technical question (type: TECHNICAL)\n"
            "7. INTERNSHIP  - Ask about internship experience; if none, ask about a personal project (type: TECHNICAL)\n"
            "8. MEDIUM_1    - A medium-difficulty technical question related to the job (type: TECHNICAL)\n"
            "9. MEDIUM_2    - Another medium-difficulty question on a different topic (type: TECHNICAL)\n"
            "10. WHY_JOB   - Ask why the candidate wants this specific role/company (type: TECHNICAL)\n"
            "11. CLOSING    - A warm, motivational closing statement or question (type: TECHNICAL)\n\n"
            f"Target Level: {difficulty}\n"
            "Tailor each question to the provided JD and Resume.\n\n"
            "Output Format: Return ONLY a valid JSON array of objects, each with keys: 'text', 'type', and 'slot'. "
            "Types are 'TECHNICAL' or 'WHITEBOARD'."
        )

        user_content = (
            f"JOB DESCRIPTION:\n{jd_text}\n\n"
            f"CANDIDATE RESUME:\n{resume_text}\n\n"
            "Generate all 11 questions in order. RETURN ONLY THE JSON ARRAY."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            inputs = self.tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt"
            ).to(self.device)
        except Exception as e:
            print(f"Chat template error: {e}. Falling back to manual formatting.")
            formatted = f"System: {system_prompt}\nUser: {user_content}\nAssistant:"
            inputs = self.tokenizer(formatted, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=2048,
                temperature=0.3,
                do_sample=True,
                top_p=0.9,
                repetition_penalty=1.1
            )

        input_len = inputs.input_ids.shape[1]
        response_tokens = outputs[0][input_len:]
        response = self.tokenizer.decode(response_tokens, skip_special_tokens=True).strip()
        
        print(f"DEBUG: AI Response Length: {len(response)}")

        # Extraction logic
        try:
            match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
            
            start = response.find('[')
            end = response.rfind(']') + 1
            if start != -1 and end != 0:
                return json.loads(response[start:end])
        except Exception as e:
            print(f"Complex JSON Parsing error: {e}")
        
        return self._fallback_questions(response, num_questions, whiteboard_count)


    def evaluate_answer(self, question_text, user_answer, whiteboard_data=None):
        """
        Evaluates a candidate's answer to a specific question.
        
        Args:
            question_text (str): The question being asked.
            user_answer (str): The candidate's response.
            whiteboard_data (dict): The digital whiteboard JSON data (strokes/elements).
        """
        whiteboard_info = f"\nWHITEBOARD DATA (JSON): {json.dumps(whiteboard_data)[:1500]}" if whiteboard_data else ""
        
        system_prompt = (
            "You are a strict technical interviewer. Your task is to evaluate the candidate's answer "
            "to a technical question. Provide a score out of 10 and brief constructive feedback.\n"
            "If WHITEBOARD DATA is provided, prioritize analyzing the diagrams, architectural logic, or code sketches "
            "contained in that JSON structure.\n\n"
            "Output Format: You MUST return ONLY a valid JSON object with 'score' (number) and 'feedback' (string) keys."
        )
 
        user_content = (
            f"QUESTION: {question_text}\n"
            f"CANDIDATE ANSWER/TRANSCRIPT: {user_answer}\n"
            f"{whiteboard_info}\n\n"
            "Evaluate the overall accuracy. RETURN ONLY THE JSON OBJECT."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            inputs = self.tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt"
            ).to(self.device)
        except Exception as e:
            formatted = f"System: {system_prompt}\nUser: {user_content}\nAssistant:"
            inputs = self.tokenizer(formatted, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.1,
                do_sample=True,
                top_p=0.9
            )

        input_len = inputs.input_ids.shape[1]
        response_tokens = outputs[0][input_len:]
        response = self.tokenizer.decode(response_tokens, skip_special_tokens=True).strip()

        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            print(f"Evaluation JSON Parsing error: {e}")
        
        return {"score": 7, "feedback": "Answer received and acknowledged."}

    def _fallback_questions(self, text, num_questions, whiteboard_count):
        # Fallback: extract from plaintext if JSON parsing fails
        slots = [
            ("SELF_INTRO", "TECHNICAL"),
            ("GENERAL", "TECHNICAL"),
            ("FOLLOWUP", "TECHNICAL"),
            ("PROJECT", "TECHNICAL"),
            ("DSA_ARCH", "WHITEBOARD"),
            ("HARD", "TECHNICAL"),
            ("INTERNSHIP", "TECHNICAL"),
            ("MEDIUM_1", "TECHNICAL"),
            ("MEDIUM_2", "TECHNICAL"),
            ("WHY_JOB", "TECHNICAL"),
            ("CLOSING", "TECHNICAL"),
        ]
        default_texts = [
            "Please introduce yourself and walk us through your background.",
            "Your resume looks pretty good. Now, let's start with... Can you explain your experience with the core technologies listed in your resume?",
            "Can you elaborate more on that — specifically how you handled edge cases?",
            "Tell me about one of your most impactful projects in detail.",
            "Design a scalable URL shortener system. Please use the whiteboard to illustrate your architecture.",
            "Explain the internals of a distributed caching system and how you'd handle cache invalidation.",
            "Describe your most significant internship experience and the key things you learned.",
            "What is the difference between process and thread? When would you prefer one over the other?",
            "Explain the CAP theorem and how it applies to distributed databases.",
            "Why are you interested in this specific role and company?",
            "You've done very well today. Is there anything you'd like to add or ask us?",
        ]
        
        lines = text.split('\n')
        extracted = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if re.match(r'^[\d\.\-\s\*]+', line) or line.endswith('?'):
                q_text = re.sub(r'^[\d\.\-\s\*]+', '', line).strip()
                if len(q_text) > 25:
                    extracted.append(q_text)
        
        questions = []
        for i in range(min(num_questions, len(slots))):
            slot, q_type = slots[i]
            text_val = extracted[i] if i < len(extracted) else default_texts[i]
            questions.append({"text": text_val, "type": q_type, "slot": slot})

        return questions[:num_questions]

