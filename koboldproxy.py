# proxy which switches between multiple koboldcpp api urls
from flask import Flask, request, Response, stream_with_context
import requests
import logging
from flask_cors import CORS
import time
import threading

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Configuration options
KOBOLD_API_URL = "http://127.0.0.1:5001/api"
ALTERNATIVE_API_URL = "http://127.0.0.1:5002/api"
api_urls = [KOBOLD_API_URL, ALTERNATIVE_API_URL]

# Control options
delay_between_switches = 1  # in seconds when in time mode or per generation in request mode
switch_mode = "request"  # can be "request" or "time"
switch_interval = 60  # in seconds, if switch_mode is "time"
max_retries = 3  # maximum number of retries for failed requests
request_timeout = 30  # in seconds

# Global variables
current_api_index = 0
last_switch_time = time.time()
request_count = 0

def get_next_api_url():
    global current_api_index, last_switch_time, request_count

    if switch_mode == "time":
        if time.time() - last_switch_time >= switch_interval:
            current_api_index = (current_api_index + 1) % len(api_urls)
            last_switch_time = time.time()
            logging.info(f"Switched API due to time interval. New API: {api_urls[current_api_index]}")
    elif switch_mode == "request":
        if request.path == '/v1/completions':  # Only count main generation requests
            request_count += 1
            if request_count >= delay_between_switches:
                current_api_index = (current_api_index + 1) % len(api_urls)
                request_count = 0
                logging.info(f"Switched API due to request count. New API: {api_urls[current_api_index]}")

    return api_urls[current_api_index]

def stream_response(response):
    for chunk in response.iter_content(chunk_size=1024):
        yield chunk

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def proxy(path):
    for attempt in range(max_retries):
        try:
            api_url = get_next_api_url()
            target_url = f"{api_url}/{path}"
            logging.info(f"Proxying request to: {target_url}")

            # Handle file uploads for audio transcriptions
            files = None
            if path == 'v1/audio/transcriptions' and request.method == 'POST':
                if 'file' not in request.files:
                    return Response("No file part in the request", status=400)
                file = request.files['file']
                files = {'file': (file.filename, file.stream, file.content_type)}

            # Forward the request to the target API
            resp = requests.request(
                method=request.method,
                url=target_url,
                headers={key: value for (key, value) in request.headers if key != 'Host'},
                data=request.get_data() if not files else None,
                files=files,
                cookies=request.cookies,
                allow_redirects=False,
                timeout=request_timeout,
                stream=True
            )

            # Handle streaming responses
            if path == 'api/extra/generate/stream':
                return Response(stream_with_context(stream_response(resp)), content_type=resp.headers.get('content-type'))

            # Create a Flask Response object from the API response
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
            response = Response(resp.content, resp.status_code, headers)
            return response

        except requests.RequestException as e:
            logging.error(f"Error connecting to {api_url}: {str(e)}")
            time.sleep(1)  # Wait for 1 second before retrying

    logging.error(f"Failed to proxy request after {max_retries} attempts")
    return Response("Failed to proxy request", status=500)

def switch_api_periodically():
    global current_api_index, last_switch_time
    while True:
        time.sleep(switch_interval)
        if switch_mode == "time":
            current_api_index = (current_api_index + 1) % len(api_urls)
            last_switch_time = time.time()
            logging.info(f"Periodically switched API. New API: {api_urls[current_api_index]}")

if __name__ == '__main__':
    logging.info("Starting Kobold API proxy")
    if switch_mode == "time":
        threading.Thread(target=switch_api_periodically, daemon=True).start()
    app.run(debug=True, host='0.0.0.0', port=5066)