from openai import OpenAI

from app.config import AGRI_AI_MODEL, OMNIROUTE_BASE_URL, require_omniroute_api_key


if __name__ == "__main__":
    client = OpenAI(
        base_url=OMNIROUTE_BASE_URL,
        api_key=require_omniroute_api_key(),
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
