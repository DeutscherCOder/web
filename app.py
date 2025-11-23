from flask import Flask, request, Response, render_template_string, session as flask_session
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, unquote, urlparse

app = Flask(__name__)
app.secret_key = 'super_secret_random_key_for_proxy_session'

requests_session = requests.Session()
requests_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Referer': 'https://www.google.com/'
})

HOME_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ V4 Anti-Glitch Proxy</title>
    <style>
        body { background: #0f0f0f; color: #00ff9d; font-family: monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .box { background: #1a1a1a; padding: 40px; border: 2px solid #00ff9d; box-shadow: 0 0 20px #00ff9d; width: 90%; max-width: 600px; text-align: center; }
        input { width: 70%; padding: 10px; background: #000; border: 1px solid #333; color: #fff; margin-bottom: 20px; }
        button { padding: 10px 20px; background: #00ff9d; color: #000; border: none; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="box">
        <h1>PROXY V4 (DECODED)</h1>
        <form action="/proxy" method="get">
            <input type="text" name="url" placeholder="https://example.com" required>
            <button type="submit">BROWSE</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HOME_HTML)

@app.route('/proxy', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy():
    target_url = request.args.get('url')
    if not target_url and request.method == 'POST':
        target_url = request.form.get('url')

    if not target_url:
        return "Error: No URL provided.", 400

    target_url = target_url.strip()
    if not target_url.lower().startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    parsed_uri = urlparse(target_url)
    base_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

    try:
        # --- FIX IS HERE: Don't tell server we accept compression ---
        # We filter out 'accept-encoding' so the server sends plain text or Python handles it.
        headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'origin', 'content-length', 'accept-encoding']}
        headers['Referer'] = base_url
        
        if request.method == 'GET':
            resp = requests_session.get(target_url, headers=headers, allow_redirects=True, timeout=15)
        elif request.method == 'POST':
            resp = requests_session.post(target_url, data=request.form, headers=headers, allow_redirects=True, timeout=15)
        else:
            return "Method not supported", 405

        final_url = resp.url
        
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'content-security-policy']
        response_headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]

        content_type = resp.headers.get('Content-Type', '').lower()

        # If binary (image, video, etc), return as-is
        if 'text/html' not in content_type and 'javascript' not in content_type and 'css' not in content_type:
            return Response(resp.content, resp.status_code, response_headers)

        # Decode content manually to ensure no garbage text
        try:
            content = resp.content.decode('utf-8', errors='replace')
        except:
            # Fallback if utf-8 fails
            content = resp.content.decode('latin-1', errors='replace')

        soup = BeautifulSoup(content, 'html.parser')

        def rewrite_url(link):
            if not link: return link
            link = link.strip()
            if link.startswith('/proxy?url='): return link
            if link.startswith('data:'): return link
            if link.startswith('#'): return link
            
            # Handle relative links
            full_link = urljoin(final_url, link)
            return f"/proxy?url={quote(full_link)}"

        tags_attributes = {
            'a': 'href', 'link': 'href', 'script': 'src', 'img': ['src', 'srcset'],
            'iframe': 'src', 'form': 'action', 'source': 'src', 'video': 'src', 'audio': 'src'
        }

        for tag_name, attributes in tags_attributes.items():
            for tag in soup.find_all(tag_name):
                if isinstance(attributes, list):
                    for attr in attributes:
                        if tag.has_attr(attr):
                            tag[attr] = rewrite_url(tag[attr])
                else:
                    if tag.has_attr(attributes):
                        tag[attributes] = rewrite_url(tag[attributes])

        return Response(str(soup), resp.status_code, response_headers)

    except Exception as e:
        return f"Error: {e}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
