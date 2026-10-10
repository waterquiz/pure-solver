@echo off
REM Windows batch script to upload image via curl

set API_URL=http://localhost:8000/api/v1/images
set API_KEY=YOUR_API_KEY
set IMAGE_FILE=image.png

curl -X POST "%API_URL%" ^
  -H "X-API-Key: %API_KEY%" ^
  -F "file=@%IMAGE_FILE%" ^
  -F "client_id=windows-batch" ^
  -F "description=Uploaded via Windows batch script"

echo.
pause
