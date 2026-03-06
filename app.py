from dotenv import load_dotenv
import os
from sarvamai import SarvamAI

load_dotenv()

Saravam_API_key = os.getenv("SARVAM_API_KEY")

client = SarvamAI(
    api_subscription_key=Saravam_API_key,
)

response = client.text.translate(
    input="Hi, My Name is Ayush.",
    source_language_code="auto",
    target_language_code="hi-IN",
    speaker_gender="Male"
)

print(response)

response = client.speech_to_text.transcribe(
    file=open("audio.wav", "rb"),
    model="saaras:v3",
    mode="transcribe"  # or "translate", "verbatim", "translit", "codemix"
)
print(response)