from flask import Flask, request, Response, render_template_string
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, unquote

app = Flask(__name__)
session = requests.Session()

# Fake user agent to look like a real browser
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

HOME_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Unlocked Web Proxy</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #222; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .container { background: #333; padding: 2rem; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); text-align: center; width: 90%; max-width: 500px; }
        h1 { margin-bottom: 1.5rem; color: #00d2ff; }
        input { width: 70%; padding: 12px; border: none; border-radius: 5px; outline: none; font-size: 16px; }
        button { padding: 12px 20px; background: #00d2ff; border: none; border-radius: 5px; color: #000; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #00aacc; }
        p { color: #aaa; margin-top: 20px; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌐 Unlocked Proxy</h1>
        <form action="/proxy" method="get">
            <input type="text" name="url" placeholder="example.com" required>
            <button type="submit">Visit</button>
        </form>
        <p>Enter a blocked URL above.</p>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HOME_HTML)

@app.route('/proxy')
def proxy():
    target_url = request.args.get('url')
    if not target_url:
        return "Error: No URL provided", 400

    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    try:
        # Fetch the URL
        resp = session.get(target_url, allow_redirects=True, timeout=10)
        final_url = resp.url
        
        # Check content type
        content_type = resp.headers.get('Content-Type', '')

        # If it's an image/css/js, return it directly
        if 'text/html' not in content_type:
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
            return Response(resp.content, resp.status_code, headers)

        # If it's HTML, rewrite links
        soup = BeautifulSoup(resp.content, 'html.parser')

        def rewrite(link):
            if link.startswith(('http', '//', '/')):
                absolute = urljoin(final_url, link)
                return f"/proxy?url={quote(absolute)}"
            return link

        for tag in soup.find_all(['a', 'link', 'area', 'base']):
            if tag.has_attr('href'):
                tag['href'] = rewrite(tag['href'])
        
        for tag in soup.find_all(['img', 'script', 'iframe', 'embed', 'source']):
            if tag.has_attr('src'):
                tag['src'] = rewrite(tag['src'])

        return Response(str(soup), content_type=content_type)

    except Exception as e:
        return f"<h1>Proxy Error</h1><p>Could not load: {target_url}</p><p>Reason: {e}</p>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
