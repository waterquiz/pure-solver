// Kotlin Android / JVM OkHttp Upload Example
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import java.io.IOException

class ImageUploader {
    private val client = OkHttpClient()

    fun upload(file: File, apiKey: String, apiUrl: String = "http://localhost:8000/api/v1/images") {
        if (!file.exists()) {
            println("File does not exist: ${file.absolutePath}")
            return
        }

        val mediaType = "image/png".toMediaTypeOrNull()
        val fileBody = file.asRequestBody(mediaType)

        val requestBody = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", file.name, fileBody)
            .addFormDataPart("client_id", "android-terminal")
            .addFormDataPart("description", "Uploaded from Kotlin app")
            .build()

        val request = Request.Builder()
            .url(apiUrl)
            .addHeader("X-API-Key", apiKey)
            .post(requestBody)
            .build()

        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("Unexpected code $response")
            println("Response: ${response.body?.string()}")
        }
    }
}
