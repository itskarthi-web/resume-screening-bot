from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="Reply with exactly: GEMINI LITE WORKING"
)

print(response.text)