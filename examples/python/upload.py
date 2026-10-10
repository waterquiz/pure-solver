"""
Python example for Remote Image Display API
Install dependency:
    pip install requests
"""
import requests

API_URL = "http://localhost:8000/api/v1/images"
API_KEY = "YOUR_API_KEY"

image_path = "image.png"

headers = {
    "X-API-Key": API_KEY
}

# Example file upload
try:
    with open(image_path, "rb") as image:
        files = {
            "file": (
                "image.png",
                image,
                "image/png"
            )
        }
        data = {
            "text": "Blone and moon",
            "client_id": "python-script-01"
        }

        # Request uploads the image, receives Puter AI output, and auto-deletes in 4s
        response = requests.post(
            API_URL,
            headers=headers,
            params={"wait_for_ai": "true", "auto_delete_seconds": 4},
            files=files,
            data=data,
            timeout=30
        )

    print(f"Status Code: {response.status_code}")
    res_data = response.json()
    print("Response JSON:", res_data)
    if "matched_cells" in res_data:
        print(f"🎯 Puter AI Matched Cells: {res_data['matched_cells']}")
        print(f"📝 Raw Output: {res_data.get('output')}")
except FileNotFoundError:
    print(f"File not found: {image_path}. Please provide a valid image file path.")
except Exception as e:
    print(f"Error uploading image: {e}")
