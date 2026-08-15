from openai import OpenAI
from app.config import (
    OMNIROUTE_BASE_URL,
    OMNIROUTE_API_KEY,
    AGRI_AI_MODEL,
)
client = OpenAI(
    base_url=OMNIROUTE_BASE_URL,
    api_key=OMNIROUTE_API_KEY,
)
SYSTEM_PROMPT = """
You are an agricultural adviser.
Your job is to help farmers make practical, evidence-informed
agricultural decisions.
When answering:
1. Understand the farmer's crop, location, season, and situation.
2. Give practical recommendations in clear language.
3. Explain the reasoning briefly.
4. If important information is missing, ask for it instead of guessing.
5. Distinguish between general guidance and location-specific advice.
6. Never invent weather, soil-test results, disease diagnoses, pesticide
   labels, fertilizer rates, or other field data.
7. For pesticide or chemical recommendations, emphasize that the farmer
   must follow the locally registered product label and applicable
   regulations.
8. When uncertainty is significant, clearly state it.
9. Prefer concise, actionable answers.
"""
def ask_adviser(question: str) -> str:
    response = client.chat.completions.create(
        model=AGRI_AI_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": question,
            },
        ],
    )
    return response.choices[0].message.content
if __name__ == "__main__":
    question = (
        "I am growing wheat in Punjab, Pakistan. "
        "When should I normally sow it, and what basic factors "
        "should I consider before sowing?"
    )
    print("===== AGRICULTURAL ADVISER =====")
    print(ask_adviser(question))
