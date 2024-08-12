from flask import Flask, request, Response
import requests
import logging
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

KOBOLD_API_URL = "http://127.0.0.1:5001/api"
ALTERNATIVE_API_URL = "http://127.0.0.1:5002/api"

api_urls = [KOBOLD_API_URL, ALTERNATIVE_API_URL]
current_api_index = 0

def get_next_api_url():
    global current_api_index
    url = api_urls[current_api_index]
    current_api_index = (current_api_index + 1) % len(api_urls)
    logging.info(f"Selected API URL: {url}")
    return url

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy(path):
    for attempt in range(2):
        try:
            api_url = get_next_api_url()
            target_url = f"{api_url}/{path}"
            logging.info(f"Proxying request to: {target_url}")

            # Forward the request to the target API
            resp = requests.request(
                method=request.method,
                url=target_url,
                headers={key: value for (key, value) in request.headers if key != 'Host'},
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                timeout=30
            )

            # Create a Flask Response object from the API response
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            headers = [(name, value) for (name, value) in resp.raw.headers.items()
                       if name.lower() not in excluded_headers]

            response = Response(resp.content, resp.status_code, headers)
            return response

        except requests.RequestException as e:
            logging.error(f"Error connecting to {api_url}: {str(e)}")

    logging.error("Failed to proxy request to both APIs")
    return Response("Failed to proxy request", status=500)

if __name__ == '__main__':
    logging.info("Starting Kobold API proxy")
    app.run(debug=True, host='0.0.0.0', port=5066)