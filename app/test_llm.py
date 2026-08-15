from openai import OpenAI
from app.config import OMNIROUTE_BASE_URL, OMNIROUTE_API_KEY, AGRI_AI_MODEL
client = OpenAI(
    base_url=OMNIROUTE_BASE_URL,
    api_key=OMNIROUTE_API_KEY,
)
response = client.chat.completions.create(
    model=AGRI_AI_MODEL,
    messages=[
        {
            "role": "user",
            "content": "Explain wheat sowing in Punjab, Pakistan, in one short sentence.",
        }
    ],
)
print("===== AI RESPONSE =====")
print(response.choices[0].message.content)
