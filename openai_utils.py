# backend/openai_utils.py

import openai
import logging
import json
from datetime import datetime

# ✅ Set up logging to console — works with Render logs
logging.basicConfig(level=logging.INFO)

def log_openai_request(model, messages, temperature=0.7):
    client = openai.OpenAI()
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature
        )

        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "temperature": temperature,
            "messages": messages,
            "response": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }

        # Show log in Render's Logs tab
        logging.info("🔍 OpenAI API Interaction:\n%s", json.dumps(log_data, indent=2))

        return response

    except Exception as e:
        logging.error("❌ OpenAI API Error: %s", str(e))
        raise
