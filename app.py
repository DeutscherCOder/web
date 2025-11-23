from flask import Flask, request, Response, render_template_string
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, urlparse

app = Flask(__name__)

# Konfiguration: Session verhält sich wie ein echtes iPad/PC
requests_session = requests.Session()
requests_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15',
    'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Connection': 'keep-alive'
})

# --- DAS NEUE DESIGN (iPad/PC Optimiert) ---
HOME_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>GHOST PROXY V5</title>
    <style>
        :root { --primary: #00f2ff; --bg: #0a0a0f; --panel: #141419; --text: #e0e0e0; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
        
        body { 
            background: var(--bg); color: var(--text); 
            height: 100vh; display: flex; flex-direction: column; 
            align-items: center; justify-content: center; 
            overflow: hidden; 
        }
        
        .glass-panel {
            background: rgba(20, 20, 25, 0.8);
            width: 90%; max-width: 600px;
            padding: 40px 30px;
            border-radius: 24px;
            box-shadow: 0 0 40px rgba(0, 242, 255, 0.1);
            text-align: center;
            border: 1px solid rgba(255,255,255,0.08);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }

        h1 { 
            font-weight: 800; font-size: 2rem; 
            margin-bottom: 20px; 
            background: linear-gradient(90deg, #fff, var(--primary)); 
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent; 
            letter-spacing: -0.5px;
        }

        .input-group { position: relative; width: 100%; margin-bottom: 20px; }
        
        input { 
            width: 100%; padding: 18px 20px; 
            background: rgba(0,0,0,0.3); 
            border: 2px solid rgba(255,255,255,0.1); 
            border-radius: 16px; color: #fff; 
            font-size: 1.1rem; outline: none; 
            transition: all 0.3s ease;
        }
        
        input:focus { border-color: var(--primary); box-shadow: 0 0 15px rgba(0, 242, 255, 0.2); }
        
        button { 
            width: 100%; padding: 18px; 
            background: var(--primary); color: #000; 
            border: none; border-radius: 16px; 
            font-size: 1.2rem; font-weight: 700; 
            cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; 
        }
        
        button:active { transform: scale(0.98); }
        button:hover { box-shadow: 0 0 25px rgba(0, 242, 255, 0.4); }

        .shortcuts { margin-top: 25px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
        .chip {
            padding: 8px 16px; background: rgba(255,255,255,0.05);
            border-radius: 20px; font-size: 0.9rem; color: #aaa;
            cursor: pointer; border: 1px solid transparent;
            text-decoration: none; transition: 0.2s;
        }
        .chip:hover { border-color: var(--primary); color: #fff; background: rgba(0, 242, 255, 0.1); }

    </style>
</head>
<body>
    <div class="glass-panel">
        <h1>GHOST PROXY V5</h1>
        <form action="/proxy" method="get">
            <div class="input-group">
                <input type="text" name="url" placeholder="URL eingeben (z.B. poki.com)" required autocomplete="off">
            </div>
            <button type="submit">Verbinden</button>
        </form>
        
        <div class="shortcuts">
            <a href="/proxy?url=https://poki.com" class="chip">Poki</a>
            <a href="/proxy?url=https://wikipedia.org" class="chip">Wikipedia</a>
            <a href="/proxy?url=https://duckduckgo.com" class="chip">DuckDuckGo</a>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HOME_HTML)

@app.route('/proxy', methods=['GET', 'POST'])
def proxy():
    target_url = request.args.get('url')
    
    # Falls URL über Formular-POST kommt
    if not target_url and request.method == 'POST':
        target_url = request.form.get('url')

    if not target_url:
        return "Bitte eine URL eingeben.", 400

    # URL bereinigen
    target_url = target_url.strip()
    if not target_url.lower().startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    parsed_uri = urlparse(target_url)
    base_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

    try:
        # 1. Header vorbereiten (Wichtig: 'Accept-Encoding' entfernen, damit kein Mülltext kommt)
        headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'origin', 'content-length', 'accept-encoding', 'cookie']}
        headers['Referer'] = base_domain # Wir tun so, als kämen wir von der Seite selbst
        
        # 2. Anfrage senden
        if request.method == 'GET':
            resp = requests_session.get(target_url, headers=headers, allow_redirects=True, timeout=15)
        else:
            resp = requests_session.post(target_url, data=request.form, headers=headers, allow_redirects=True, timeout=15)

        final_url = resp.url
        
        # 3. Sicherheits-Header der Zielseite entfernen (CSP Killer)
        # Das erlaubt Poki, Skripte auch über unseren Proxy zu laden
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 
                            'content-security-policy', 'x-frame-options', 'strict-transport-security']
        
        response_headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]

        content_type = resp.headers.get('Content-Type', '').lower()

        # Wenn es kein HTML ist (Bilder, CSS, JS), direkt durchleiten
        if 'text/html' not in content_type:
            return Response(resp.content, resp.status_code, response_headers)

        # 4. HTML umschreiben (Der wichtigste Teil)
        # Wir versuchen, UTF-8 zu erzwingen
        try:
            content = resp.content.decode('utf-8', errors='replace')
        except:
            content = resp.content.decode('latin-1', errors='replace')

        soup = BeautifulSoup(content, 'html.parser')

        # Hilfsfunktion zum Umschreiben von Links
        def rewrite_link(link):
            if not link: return link
            link = link.strip()
            # Wenn schon Proxy, ignorieren
            if link.startswith('/proxy?url='): return link
            # Data-URIs und Anker ignorieren
            if link.startswith(('data:', '#', 'mailto:', 'javascript:')): return link
            
            # Absolute URL erstellen
            full_link = urljoin(final_url, link)
            return f"/proxy?url={quote(full_link)}"

        # Alle wichtigen HTML-Tags durchsuchen und Attribute umschreiben
        tags_map = {
            'a': 'href',
            'link': 'href',
            'script': 'src',
            'img': ['src', 'srcset', 'data-src'], # Poki nutzt data-src oft
            'iframe': 'src',
            'form': 'action',
            'source': 'src',
            'video': ['src', 'poster']
        }

        for tag_name, attributes in tags_map.items():
            for tag in soup.find_all(tag_name):
                if isinstance(attributes, list):
                    for attr in attributes:
                        if tag.has_attr(attr):
                            tag[attr] = rewrite_link(tag[attr])
                else:
                    if tag.has_attr(attributes):
                        tag[attributes] = rewrite_link(tag[attributes])

        return Response(str(soup), resp.status_code, response_headers)

    except Exception as e:
        return f"""
        <div style="font-family:sans-serif; text-align:center; padding:50px; color:#fff; background:#111; height:100vh;">
            <h2 style="color:#ff3333">Verbindungsfehler</h2>
            <p>Konnte {target_url} nicht laden.</p>
            <p style="color:#666">{str(e)}</p>
            <a href="/" style="color:#00f2ff; text-decoration:none; border:1px solid #00f2ff; padding:10px 20px; border-radius:10px;">Zurück</a>
        </div>
        """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
