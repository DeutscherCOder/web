from flask import Flask, request, Response, render_template_string, redirect
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, unquote, urlparse
import re

app = Flask(__name__)
app.secret_key = 'ghost_proxy_v7_secret'

# Setup a session that looks like a real browser to avoid blocks
requests_session = requests.Session()
requests_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.google.com/'
})

# --- UI DESIGN (Modern & Dark) ---
HOME_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ghost Proxy V7</title>
    <style>
        body { background-color: #0d0d0d; color: #00ffcc; font-family: 'Courier New', monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .container { background: #1a1a1a; padding: 40px; border-radius: 16px; border: 1px solid #333; box-shadow: 0 0 30px rgba(0, 255, 204, 0.1); width: 90%; max-width: 600px; text-align: center; }
        h1 { margin-bottom: 20px; text-shadow: 0 0 10px #00ffcc; }
        input { width: 80%; padding: 15px; margin-bottom: 20px; border-radius: 8px; border: 1px solid #444; background: #000; color: #fff; font-size: 16px; outline: none; }
        input:focus { border-color: #00ffcc; }
        button { padding: 15px 30px; border-radius: 8px; border: none; background: #00ffcc; color: #000; font-weight: bold; cursor: pointer; font-size: 16px; transition: 0.3s; }
        button:hover { background: #00cca3; box-shadow: 0 0 20px rgba(0, 255, 204, 0.4); }
        .chips { margin-top: 20px; display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; }
        .chip { background: #333; color: #aaa; padding: 8px 12px; border-radius: 20px; text-decoration: none; font-size: 12px; transition: 0.2s; }
        .chip:hover { background: #00ffcc; color: #000; }
    </style>
</head>
<body>
    <div class="container">
        <h1>GHOST PROXY V7</h1>
        <form action="/proxy" method="get">
            <input type="text" name="url" placeholder="https://example.com" required autocomplete="off">
            <br>
            <button type="submit">CONNECT</button>
        </form>
        <div class="chips">
            <a href="/proxy?url=https://aniworld.to" class="chip">AniWorld</a>
            <a href="/proxy?url=https://poki.com" class="chip">Poki</a>
            <a href="/proxy?url=https://duckduckgo.com" class="chip">DuckDuckGo</a>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HOME_HTML)

# --- THE RESCUE SYSTEM (Fixes 404 errors for fonts/images) ---
# This catches requests like /webfonts/fa-solid.woff and redirects them back to the proxy
@app.route('/<path:undefined_path>')
def catch_all(undefined_path):
    # Check if the user came from a proxied page
    referer = request.headers.get('Referer')
    if referer and '/proxy?url=' in referer:
        try:
            # Extract the last visited site from the Referer URL
            # Example: .../proxy?url=https://aniworld.to/anime/stream
            previous_url = unquote(referer.split('/proxy?url=')[1])
            
            # Reconstruct the correct full URL
            # Logic: If previous was https://site.com/page, and path is /font.woff
            # Result: https://site.com/font.woff
            fixed_target = urljoin(previous_url, undefined_path)
            
            # Send them back into the proxy tunnel
            return redirect(f"/proxy?url={quote(fixed_target)}")
        except:
            pass
    return f"Error: 404 Resource Not Found. Path: {undefined_path}", 404

# --- THE MAIN PROXY LOGIC ---
@app.route('/proxy', methods=['GET', 'POST'])
def proxy():
    target_url = request.args.get('url')
    if not target_url and request.method == 'POST':
        target_url = request.form.get('url')

    if not target_url:
        return redirect('/')

    # Clean URL
    target_url = target_url.strip()
    if not target_url.lower().startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    try:
        # Filter headers (Drop 'Accept-Encoding' to prevent garbage text)
        headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'origin', 'content-length', 'accept-encoding']}
        
        # Perform Request
        if request.method == 'GET':
            resp = requests_session.get(target_url, headers=headers, allow_redirects=True, timeout=20)
        else:
            resp = requests_session.post(target_url, data=request.form, headers=headers, allow_redirects=True, timeout=20)

        final_url = resp.url
        
        # Prepare Response Headers (Kill Security Policies that block proxies)
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'content-security-policy', 'x-frame-options']
        response_headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]

        content_type = resp.headers.get('Content-Type', '').lower()

        # --- HANDLER 1: CSS (Fixes Font/Image Loading in Styles) ---
        if 'text/css' in content_type:
            try:
                css_content = resp.content.decode('utf-8', errors='replace')
                # Regex to find url(...) inside CSS and wrap it
                # Example: url("/fonts/arial.ttf") -> url("/proxy?url=.../fonts/arial.ttf")
                def css_fixer(match):
                    url_val = match.group(1).strip(' \'"')
                    if url_val.startswith(('data:', '#', 'http')): return match.group(0)
                    absolute_link = urljoin(final_url, url_val)
                    return f'url("/proxy?url={quote(absolute_link)}")'
                
                fixed_css = re.sub(r'url\((.*?)\)', css_fixer, css_content)
                return Response(fixed_css, resp.status_code, response_headers)
            except:
                pass # If decode fails, send raw

        # --- HANDLER 2: HTML (Rewrites Links) ---
        if 'text/html' in content_type:
            try:
                content = resp.content.decode('utf-8', errors='replace')
            except:
                content = resp.content.decode('latin-1', errors='replace')

            soup = BeautifulSoup(content, 'html.parser')

            # Helper to rewrite a single URL
            def rewrite(link):
                if not link: return link
                if link.startswith(('/proxy?url=', 'data:', '#', 'mailto:', 'javascript:')): return link
                # Handle absolute and relative links
                full_link = urljoin(final_url, link)
                return f"/proxy?url={quote(full_link)}"

            # Rewrite common attributes
            tags_map = {
                'a': 'href', 'link': 'href', 'script': 'src',
                'img': ['src', 'srcset', 'data-src'], # Fixes lazy loading images
                'iframe': 'src', 'form': 'action',
                'source': 'src', 'video': ['src', 'poster']
            }

            for tag_name, attrs in tags_map.items():
                for tag in soup.find_all(tag_name):
                    if isinstance(attrs, list):
                        for attr in attrs:
                            if tag.has_attr(attr): tag[attr] = rewrite(tag[attr])
                    else:
                        if tag.has_attr(attrs): tag[attrs] = rewrite(tag[attrs])

            # Also fix inline styles: <div style="background-image: url(...)">
            for tag in soup.find_all(style=True):
                style_content = tag['style']
                if 'url(' in style_content:
                    # Simple replace for inline styles
                    def inline_css_fixer(match):
                        url_val = match.group(1).strip(' \'"')
                        if url_val.startswith('data:'): return match.group(0)
                        abs_link = urljoin(final_url, url_val)
                        return f'url("/proxy?url={quote(abs_link)}")'
                    
                    tag['style'] = re.sub(r'url\((.*?)\)', inline_css_fixer, style_content)

            # Inject a <base> tag to help browsers resolve relative scripts
            base_tag = soup.new_tag("base", href=final_url)
            if soup.head:
                soup.head.insert(0, base_tag)

            return Response(str(soup), resp.status_code, response_headers)

        # Default: Return raw content (Images, JS, Fonts, etc.)
        return Response(resp.content, resp.status_code, response_headers)

    except Exception as e:
        return f"Proxy Error: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
