from flask import Flask, request, Response, render_template_string, session as flask_session
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, unquote, urlparse

app = Flask(__name__)
app.secret_key = 'super_secret_random_key_for_proxy_session'

# A persistent session to keep cookies (like a real browser)
requests_session = requests.Session()
requests_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.google.com/'
})

HOME_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ V3 High-Speed Proxy</title>
    <style>
        body { background: #121212; color: #e0e0e0; font-family: 'Courier New', monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .box { background: #1e1e1e; padding: 40px; border-radius: 12px; border: 1px solid #333; box-shadow: 0 0 20px rgba(0, 255, 136, 0.1); width: 90%; max-width: 600px; text-align: center; }
        h1 { color: #00ff88; margin-top: 0; text-transform: uppercase; letter-spacing: 2px; }
        input { width: 75%; padding: 15px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 4px; outline: none; margin-bottom: 20px; font-size: 1.1rem; }
        input:focus { border-color: #00ff88; }
        button { padding: 15px 30px; background: #00ff88; color: #000; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 1.1rem; transition: 0.2s; }
        button:hover { background: #00cc6a; box-shadow: 0 0 15px #00ff88; }
        .status { margin-top: 20px; font-size: 0.8rem; color: #666; }
    </style>
</head>
<body>
    <div class="box">
        <h1>Stealth Proxy V3</h1>
        <form action="/proxy" method="get">
            <input type="text" name="url" placeholder="https://poki.com" required autocomplete="off">
            <br>
            <button type="submit">CONNECT SECURELY</button>
        </form>
        <p class="status">Supports: GET/POST, Cookies, Redirects</p>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HOME_HTML)

# Handle GET, POST, PUT, DELETE to support games sending data
@app.route('/proxy', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy():
    target_url = request.args.get('url')
    
    # If we are coming from a form inside the proxy, the URL might be in the form data
    if not target_url and request.method == 'POST':
        target_url = request.form.get('url')

    if not target_url:
        return "Error: Endpoint lost. Please return to home.", 400

    # Clean URL
    target_url = target_url.strip()
    if not target_url.lower().startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    # Calculate the "Base URL" to fix relative links (e.g. /css/style.css)
    parsed_uri = urlparse(target_url)
    base_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

    try:
        # 1. PREPARE HEADERS (Forwarding headers helps games work)
        headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'origin', 'content-length']}
        headers['Referer'] = base_url  # Fake the referer so the game thinks we are on their site
        
        # 2. MAKE THE REQUEST (Support GET and POST)
        if request.method == 'GET':
            resp = requests_session.get(target_url, headers=headers, allow_redirects=True, timeout=15)
        elif request.method == 'POST':
            resp = requests_session.post(target_url, data=request.form, headers=headers, allow_redirects=True, timeout=15)
        else:
            return "Method not supported in this simple proxy", 405

        final_url = resp.url
        
        # 3. FILTER HEADERS FOR RESPONSE
        # We need to strip some headers that confuse the browser when proxying
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'content-security-policy']
        response_headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]

        # 4. HANDLE CONTENT
        content_type = resp.headers.get('Content-Type', '').lower()

        # If it's a binary file (Image, Font, Video, Zip), stream it back directly
        if 'text/html' not in content_type and 'javascript' not in content_type and 'css' not in content_type:
            return Response(resp.content, resp.status_code, response_headers)

        # 5. REWRITE HTML (The Magic Part)
        # We decode to text to manipulate links
        try:
            content = resp.content.decode('utf-8', errors='ignore')
        except:
            # If decoding fails, just return raw bytes
            return Response(resp.content, resp.status_code, response_headers)

        soup = BeautifulSoup(content, 'html.parser')

        def rewrite_url(link):
            if not link: return link
            link = link.strip()
            # If it's already a proxy link, ignore
            if link.startswith('/proxy?url='): return link
            # If it's a relative path (/game/start), make it absolute
            full_link = urljoin(final_url, link)
            return f"/proxy?url={quote(full_link)}"

        # Rewrite standard HTML attributes
        tags_attributes = {
            'a': 'href',
            'link': 'href',
            'script': 'src',
            'img': ['src', 'srcset'],
            'iframe': 'src',
            'form': 'action',
            'source': 'src',
            'video': 'src',
            'audio': 'src'
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

        # 6. RETURN MODIFIED CONTENT
        return Response(str(soup), resp.status_code, response_headers)

    except Exception as e:
        # If something crashes, show a cool error page
        return f"""
        <div style="background:#111; color:red; padding:20px; text-align:center; font-family:monospace;">
            <h2>CONNECTION INTERRUPTED</h2>
            <p>Target: {target_url}</p>
            <p>Error: {str(e)}</p>
            <a href="/" style="color:#00ff88">RETURN TO BASE</a>
        </div>
        """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
