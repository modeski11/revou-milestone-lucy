from openai import OpenAI
import base64
import os
def describe_image(image_bytes):
    OPENAI_KEY = os.environ.get('OPENAI_API_KEY')
    client = OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "You are an IT support assistant. The following image will not be visible to the technical support team, so your description is critical for troubleshooting. Please describe the image in detail from an IT support perspective: include any visible error messages, warning icons, system notifications, device screens, cable connections, hardware issues, or anything else relevant for diagnosing IT problems. Be thorough and precise, as your description will be the only information the support team receives. At the end of your description, list several keywords that summarize the main issues or elements in the image. These keywords will be used for searching a problem repository or using Retrieval-Augmented Generation (RAG) to find similar issues. Write with only Bahasa Indonesia and make it as brief and detailed as possible"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()}}
                ]
            }
        ]
    )
    return response.choices[0].message.content.strip()
