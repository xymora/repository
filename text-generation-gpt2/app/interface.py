
import streamlit as st
from transformers import pipeline, set_seed

st.set_page_config(page_title="LLM Text Generator", layout="centered")

st.title("✨ GPT-2 Text Generator")

prompt = st.text_area("Enter your prompt:", "Once upon a time")

temperature = st.slider("Temperature", 0.1, 1.5, 0.7)
top_k = st.slider("Top_k", 10, 100, 50)
max_length = st.slider("Max Length", 50, 200, 100)

if st.button("Generate"):
    generator = pipeline("text-generation", model="gpt2")
    set_seed(42)
    output = generator(prompt, max_length=max_length, temperature=temperature, top_k=top_k, num_return_sequences=1)
    st.subheader("Generated Text")
    st.write(output[0]['generated_text'])
