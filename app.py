from dotenv import load_dotenv
import os
from sarvamai import SarvamAI

load_dotenv()

sarvam_api_key = os.getenv("SARVAM_API_KEY")

client = SarvamAI(
    api_subscription_key=sarvam_api_key,
)

def speech_to_text(audio):
    response = client.speech_to_text.transcribe(
        file=open("audio.wav", "rb"),
        model="saaras:v3",
        mode="transcribe"  # or "translate", "verbatim", "translit", "codemix"
    )

response = client.text.translate(
    input="Hi, My Name is Ayush.",
    source_language_code="auto",
    target_language_code="hi-IN",
    speaker_gender="Male"
)

print(response)

filepath = "audio.wav"
response = speech_to_text(filepath)
print(response)