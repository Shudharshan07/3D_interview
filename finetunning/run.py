from transformers import AutoModelForCausalLM, AutoTokenizer, LlamaTokenizerFast, BitsAndBytesConfig
import torch

model_path = r"./llama_model_merged"

# Check GPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Configure 4-bit
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
) if device == "cuda" else None

# Load model
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",
    quantization_config=bnb_config,
)

# Load tokenizer
try:
    tokenizer = AutoTokenizer.from_pretrained(model_path)
except:
    tokenizer = LlamaTokenizerFast.from_pretrained(model_path)

# Test Prompt
messages = [
    {"role": "system", "content": "You are a professional technical interviewer."},
    {"role": "user", "content": "Tell me about the importance of memory management in Python."},
]

inputs = tokenizer.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_tensors="pt"
).to(device)

# Generate
with torch.no_grad():
    outputs = model.generate(
        **inputs, # Pass the tensors directly
        max_new_tokens=128,
        temperature=0.7,
    )

print("-" * 30)
print(tokenizer.batch_decode(outputs, skip_special_tokens=True)[0])
print("-" * 30)
