from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch

model = GPT2LMHeadModel.from_pretrained("fine_tuned_gpt2_model")
tokenizer = GPT2Tokenizer.from_pretrained("fine_tuned_gpt2_model")

prompt = "The future of AI is"
inputs = tokenizer.encode(prompt, return_tensors="pt")
outputs = model.generate(inputs, max_length=50, num_return_sequences=1)

print(tokenizer.decode(outputs[0]))