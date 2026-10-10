# Ruby Upload Example
require 'net/http'
require 'uri'

api_url = URI.parse("http://localhost:8000/api/v1/images")
api_key = "YOUR_API_KEY"
file_path = "image.png"

unless File.exist?(file_path)
  puts "Image file not found: #{file_path}"
  exit 1
end

boundary = "----RubyMultipartBoundary#{Time.now.to_i}"
file_content = File.binread(file_path)

post_body = []
post_body << "--#{boundary}\r\n"
post_body << "Content-Disposition: form-data; name=\"file\"; filename=\"#{File.basename(file_path)}\"\r\n"
post_body << "Content-Type: image/png\r\n\r\n"
post_body << file_content
post_body << "\r\n--#{boundary}\r\n"
post_body << "Content-Disposition: form-data; name=\"client_id\"\r\n\r\n"
post_body << "ruby-script\r\n"
post_body << "--#{boundary}--\r\n"

http = Net::HTTP.new(api_url.host, api_url.port)
req = Net::HTTP::Post.new(api_url.request_uri)
req['X-API-Key'] = api_key
req['Content-Type'] = "multipart/form-data; boundary=#{boundary}"
req.body = post_body.join

res = http.request(req)
puts "Status: #{res.code}"
puts "Response: #{res.body}"
