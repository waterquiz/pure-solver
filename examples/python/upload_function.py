"""
Reusable Python upload function for Remote Image Display API
"""
import requests
from typing import Optional, Dict, Any


def upload_image(
    image_path: str,
    api_key: str,
    api_url: str = "http://localhost:8000/api/v1/images",
    client_id: Optional[str] = None,
    description: Optional[str] = None,
    timeout: int = 60
) -> Dict[str, Any]:
    """
    Uploads an image to the Remote Image Display API server.

    Args:
        image_path: Local filesystem path to the image.
        api_key: Secret API key (starts with sk_live_).
        api_url: Full URL to the /api/v1/images endpoint.
        client_id: Optional client/device identifier.
        description: Optional notes/caption.
        timeout: HTTP request timeout in seconds.

    Returns:
        Dict containing server response with image metadata.
    """
    headers = {
        "X-API-Key": api_key
    }

    with open(image_path, "rb") as image:
        files = {
            "file": (
                image_path,
                image,
                "application/octet-stream"
            )
        }
        data = {}
        if client_id:
            data["client_id"] = client_id
        if description:
            data["description"] = description

        response = requests.post(
            api_url,
            headers=headers,
            files=files,
            data=data,
            timeout=timeout
        )

    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    # Example usage:
    # result = upload_image("photo.jpg", "sk_live_...", client_id="my-camera")
    # print(result)
    pass
