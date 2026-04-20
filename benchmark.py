from transformers import AutoProcessor, AutoModelForCausalLM
import torch
import os

# Get HF token from env if available
token = os.getenv("HUGGINGFACE_TOKEN")

# Using local model path
model_path = os.path.join(os.getcwd(), "models", "functiongemma-270m-it")

# Check for GPU
device_map = "auto" if torch.cuda.is_available() else "cpu"
print(f"Using device_map: {device_map}")

print(f"Loading model and processor from {model_path}...")
processor = AutoProcessor.from_pretrained(model_path, device_map=device_map, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(model_path, dtype="auto", device_map=device_map, local_files_only=True)

weather_function_schema = {
    "type": "function",
    "function": {
        "name": "get_current_temperature",
        "description": "Gets the current temperature for a given location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city name, e.g. San Francisco",
                },
            },
            "required": ["location"],
        },
    }
}

message = [
    {
        "role": "developer",
        "content": "You are a model that can do function calling with the following functions"
    },
    {
        "role": "user", 
        "content": "What's the temperature in London?"
    }
]

print("Generating response...")
inputs = processor.apply_chat_template(
    message, 
    tools=[weather_function_schema], 
    add_generation_prompt=True, 
    return_dict=True, 
    return_tensors="pt"
)

out = model.generate(**inputs.to(model.device), pad_token_id=processor.eos_token_id, max_new_tokens=128)
output = processor.decode(out[0][len(inputs["input_ids"][0]):], skip_special_tokens=True)

print("\n--- Model Output ---")
print(output)
