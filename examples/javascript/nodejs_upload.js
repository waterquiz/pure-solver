// Node.js v18+ Native Fetch Upload Example
import fs from "fs";

const API_URL = "http://localhost:8000/api/v1/images";
const API_KEY = "YOUR_API_KEY";
const filePath = "image.png";

async function uploadImageNode() {
  if (!fs.existsSync(filePath)) {
    console.error(`File not found: ${filePath}`);
    return;
  }

  const fileBuffer = fs.readFileSync(filePath);
  const blob = new Blob([fileBuffer], { type: "image/png" });

  const form = new FormData();
  form.append("file", blob, "image.png");
  form.append("client_id", "nodejs-worker-process");
  form.append("description", "Uploaded from Node.js runtime");

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "X-API-Key": API_KEY
      },
      body: form
    });

    const result = await response.json();
    console.log("Status:", response.status);
    console.log("Result:", result);
  } catch (err) {
    console.error("Upload error:", err);
  }
}

uploadImageNode();
