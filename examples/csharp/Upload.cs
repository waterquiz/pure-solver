using System;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;

namespace RemoteImageClient
{
    class Program
    {
        static async Task Main(string[] args)
        {
            string apiUrl = "http://localhost:8000/api/v1/images";
            string apiKey = "YOUR_API_KEY";
            string imagePath = "image.png";

            if (!File.Exists(imagePath))
            {
                Console.WriteLine($"Image file not found: {imagePath}");
                return;
            }

            using var httpClient = new HttpClient();
            httpClient.DefaultRequestHeaders.Add("X-API-Key", apiKey);

            using var form = new MultipartFormDataContent();
            using var fileStream = File.OpenRead(imagePath);
            using var streamContent = new StreamContent(fileStream);

            form.Add(streamContent, "file", Path.GetFileName(imagePath));
            form.Add(new StringContent("csharp-client"), "client_id");
            form.Add(new StringContent("Uploaded from .NET C# client"), "description");

            var response = await httpClient.PostAsync(apiUrl, form);
            string responseBody = await response.Content.ReadAsStringAsync();

            Console.WriteLine($"HTTP Status: {response.StatusCode}");
            Console.WriteLine($"Response: {responseBody}");
        }
    }
}
