import re
from datasets import load_dataset, Dataset

def clean_anthropic_data():
    raw_dataset = load_dataset(
        "csv",
        data_files="data/workforce_transcripts.csv",
        split="train"
    )
    
    formatted_data = []

    for entry in raw_dataset:
        transcript = entry['text']
        
        # Split the transcript into turns using Regex
        # It looks for "Assistant:", "AI:", or "User:"
        parts = re.split(r'(Assistant:|AI:|User:)', transcript)
        
        messages = []
        # Add a professional System Prompt to every conversation
        messages.append({
            "role": "system", 
            "content": "You are a professional hiring manager. Conduct a structured, polite, and insightful interview."
        })
        
        current_role = None
        for i in range(1, len(parts), 2):
            label = parts[i].strip()
            text = parts[i+1].strip()
            
            # Map labels to Llama roles
            if label == "User:":
                messages.append({"role": "user", "content": text})
            elif label in ("Assistant:", "AI:"):
                messages.append({"role": "assistant", "content": text})
        
        # Only keep conversations that have a proper back-and-forth
        if len(messages) > 2:
            formatted_data.append({"conversations": messages})

    # 2. Convert to Hugging Face Dataset format
    clean_dataset = Dataset.from_list(formatted_data)
    
    # 3. Save locally so it's "ready to go"
    clean_dataset.save_to_disk("cleaned_interview_data")
    print(f"Success! Cleaned {len(clean_dataset)} interview sessions.")
    return clean_dataset

# Run the cleaner
dataset = clean_anthropic_data()