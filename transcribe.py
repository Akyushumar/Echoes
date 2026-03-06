from dotenv import load_dotenv
import os
from sarvamai import SarvamAI

load_dotenv()

sarvam_api_key = os.getenv("SARVAM_API_KEY")

client = SarvamAI(
    api_subscription_key=sarvam_api_key,
)
