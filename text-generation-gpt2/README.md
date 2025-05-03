# ✨ LLM-Based Creative Text Generator

This project demonstrates how to use a pre-trained Large Language Model (LLM) like GPT-2 from Hugging Face to generate creative or assisted text. The application provides a user-friendly interface built with Streamlit, allowing dynamic control of model parameters and showcasing real-world use cases.

## 🎯 Objective

To provide an interactive environment for generating coherent, fluent, and diverse text outputs using GPT-2. This serves as a demonstration of how LLMs can be leveraged for tasks such as:
- Automated content writing
- Product description generation
- Conversational AI responses
- Storytelling

## 🧠 Techniques Used

- GPT-2 model from Hugging Face Transformers
- Text generation with tunable parameters: temperature, top_k, max_length
- Evaluation of generated text via manual inspection and configuration
- Streamlit interface for end-user interaction

## 🛠️ Technologies

- Python 3.9+
- transformers (Hugging Face)
- torch
- streamlit

## 📁 Project Structure

llm-text-generation/
├── app/
│   ├── interface.py              # Streamlit interface for text generation
├── examples/
│   └── example_prompts.txt       # Example input prompts for testing
├── requirements.txt              # Python dependencies
└── README.md                     # Project documentation

## 🚀 How to Run

```bash
pip install -r requirements.txt
streamlit run app/interface.py
```

## ⚙️ Parameters

The interface allows real-time tuning of:
- `temperature`: randomness in output
- `top_k`: restricts the number of next token candidates
- `max_length`: length of the generated text

## 📦 Output

The application displays the generated text directly within the UI. Users can copy or save the results for further use.

## 📌 Future Enhancements

- Add support for other models like T5
- Allow saving session history
- Integrate evaluation metrics for automated quality checks

## 📄 License

MIT License
