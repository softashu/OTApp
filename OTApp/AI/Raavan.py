import os
from pprint import pprint

from google import genai
from google.genai import types
from google.genai.types import ThinkingLevel


class Raavan:
    """
    ### THE RAAVAN ENGINE: A Confluence of Ten-Fold Wisdom ###

    A tribute to the Dashanan—the Great Scholar of Lanka.
    Like the ten heads that mastered the 4 Vedas and 6 Shastras,
    this class serves as a multidisciplinary core for:

    1. Manas (Mind)      6. Kama (Desire/Goal)
    2. Buddhi (Intellect) 7. Krodha (Power/Action)
    3. Chitta (Will)     8. Lobha (Resource Acquisition)
    4. Ahamkara (Ego)    9. Moha (Logic Flow)
    5. Mada (Focus)     10. Matsarya (Competitive Edge)

    "Knowledge is a weapon; its mastery is the only true sovereignty."
    """
    # Initialize the client
    # load_dotenv()  # This loads the variables from the .env file
    GENAI_API_KEY = os.getenv('genai_api_key')
    client = genai.Client(api_key=GENAI_API_KEY)

    def __init__(self):
        pass

    @classmethod
    def ask_raavan_analyst(cls, market_context: str):
        """
        Sends raw market data to Gemini for a 'Strategic Review'.
        """
        prompt = f"""
        You are a economic calendar . 
        Review this context and decide if we should HALT or PROCEED with the 15-delta strangle based on impact of event.
        
        Context: {market_context}
        
        Return your answer in JSON format: {{"action": "HALT/PROCEED", "reason": "short string","event_name":"short string"}}
        """

        response = cls.client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                # THIS IS THE SECRET SAUCE:
                response_mime_type="application/json",
                system_instruction="You are Raavan, the Master of Ten-Fold Wisdom and Crypto Options Quant. Your goal is to analyze the market for a 15-delta short-volatility strategy. Do not hallucinate. Use only the provided real-world events",
                # 'low' thinking level = faster response, perfect for bots
                thinking_config=types.ThinkingConfig(thinking_level=ThinkingLevel.LOW),
            )
        )
        return response.text


# Example Usage:
# context = "BTC IVR is 45. Tomorrow is the Fed meeting at 12:30 AM."
context = "Is there any event on date 19-feb-2026 that have high impact on my 15-delta strategy if yes how to overcome this? also give the name of event / events"
decision = Raavan.ask_raavan_analyst(context)
pprint(decision)

# TODO : Wil complete later
