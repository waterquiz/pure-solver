// Swift iOS / macOS URLSession Upload Example
import Foundation

func uploadImage(fileURL: URL, apiKey: String, completion: @escaping (String?) -> Void) {
    guard let apiEndpoint = URL(string: "http://localhost:8000/api/v1/images") else { return }
    var request = URLRequest(url: apiEndpoint)
    request.httpMethod = "POST"
    request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")

    let boundary = "Boundary-\(UUID().uuidString)"
    request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

    var body = Data()
    guard let fileData = try? Data(contentsOf: fileURL) else {
        print("Failed to read file data")
        return
    }

    body.append("--\(boundary)\r\n".data(using: .utf8)!)
    body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileURL.lastPathComponent)\"\r\n".data(using: .utf8)!)
    body.append("Content-Type: image/png\r\n\r\n".data(using: .utf8)!)
    body.append(fileData)
    body.append("\r\n".data(using: .utf8)!)

    body.append("--\(boundary)\r\n".data(using: .utf8)!)
    body.append("Content-Disposition: form-data; name=\"client_id\"\r\n\r\n".data(using: .utf8)!)
    body.append("iOS-App\r\n".data(using: .utf8)!)
    body.append("--\(boundary)--\r\n".data(using: .utf8)!)

    let task = URLSession.shared.uploadTask(with: request, from: body) { responseData, response, error in
        if let error = error {
            print("Error: \(error)")
            completion(nil)
            return
        }
        if let responseData = responseData, let json = String(data: responseData, encoding: .utf8) {
            completion(json)
        }
    }
    task.resume()
}
