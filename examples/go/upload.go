package main

import (
	"bytes"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
)

func main() {
	apiUrl := "http://localhost:8000/api/v1/images"
	apiKey := "YOUR_API_KEY"
	filePath := "image.png"

	file, err := os.Open(filePath)
	if err != nil {
		fmt.Printf("File error: %v\n", err)
		return
	}
	defer file.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	part, err := writer.CreateFormFile("file", "image.png")
	if err != nil {
		fmt.Printf("Multipart error: %v\n", err)
		return
	}
	_, err = io.Copy(part, file)
	if err != nil {
		fmt.Printf("Copy error: %v\n", err)
		return
	}

	_ = writer.WriteField("client_id", "go-uploader")
	_ = writer.WriteField("description", "Uploaded from Go client")
	writer.Close()

	req, err := http.NewRequest("POST", apiUrl, body)
	if err != nil {
		fmt.Printf("Request creation error: %v\n", err)
		return
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())
	req.Header.Set("X-API-Key", apiKey)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("Request error: %v\n", err)
		return
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	fmt.Printf("HTTP Status: %s\n", resp.Status)
	fmt.Printf("Response Body: %s\n", string(respBody))
}
