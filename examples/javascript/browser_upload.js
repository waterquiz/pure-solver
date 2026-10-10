// Browser JavaScript Upload Example
const API_URL = "http://localhost:8000/api/v1/images";
const API_KEY = "YOUR_API_KEY";

async function uploadImage(file, clientId = "browser-client") {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("client_id", clientId);
  formData.append("description", "Uploaded from web browser");

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "X-API-Key": API_KEY
      },
      body: formData
    });

    const result = await response.json();
    console.log("Upload response:", result);
    return result;
  } catch (error) {
    console.error("Error uploading image:", error);
    throw error;
  }
}

// Example HTML file input listener:
// const input = document.querySelector("#image");
// input.addEventListener("change", () => {
//   const file = input.files[0];
//   if (file) uploadImage(file);
// });
