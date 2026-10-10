#!/bin/bash
# Upload image to Remote Image Display API via cURL

API_URL="http://localhost:8000/api/v1/images"
API_KEY="YOUR_API_KEY"
IMAGE_FILE="image.png"

curl -X POST "${API_URL}" \
  -H "X-API-Key: ${API_KEY}" \
  -F "file=@${IMAGE_FILE}" \
  -F "client_id=curl-bash-script" \
  -F "description=Uploaded via bash script" \
  --verbose
