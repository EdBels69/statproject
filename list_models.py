from zhipuai import ZhipuAI
import os
from dotenv import load_dotenv

load_dotenv()

client = ZhipuAI(api_key=os.getenv("GLM_API_KEY")) # Use default URL first

try:
    response = client.models.list()
    # Paging might be needed?
    print("Models:", response)
except Exception as e:
    print("Error:", e)
