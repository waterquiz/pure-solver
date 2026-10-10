import java.io.IOException;
import java.net.URI;
import java.net.http.*;
import java.nio.file.Files;
import java.nio.file.Path;

public class Upload {
    public static void main(String[] args) throws IOException, InterruptedException {
        String apiUrl = "http://localhost:8000/api/v1/images";
        String apiKey = "YOUR_API_KEY";
        Path imagePath = Path.of("image.png");

        if (!Files.exists(imagePath)) {
            System.err.println("File not found: " + imagePath);
            return;
        }

        String boundary = "---" + System.currentTimeMillis();
        byte[] fileBytes = Files.readAllBytes(imagePath);

        StringBuilder body = new StringBuilder();
        body.append("--").append(boundary).append("\r\n");
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"image.png\"\r\n");
        body.append("Content-Type: image/png\r\n\r\n");

        byte[] headerBytes = body.toString().getBytes();
        byte[] footerBytes = ("\r\n--" + boundary + "--\r\n").getBytes();

        byte[] payload = new byte[headerBytes.length + fileBytes.length + footerBytes.length];
        System.arraycopy(headerBytes, 0, payload, 0, headerBytes.length);
        System.arraycopy(fileBytes, 0, payload, headerBytes.length, fileBytes.length);
        System.arraycopy(footerBytes, 0, payload, headerBytes.length + fileBytes.length, footerBytes.length);

        HttpClient client = HttpClient.newHttpClient();
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(apiUrl))
                .header("X-API-Key", apiKey)
                .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .POST(HttpRequest.BodyPublishers.ofByteArray(payload))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println("Status: " + response.statusCode());
        System.out.println("Response: " + response.body());
    }
}
