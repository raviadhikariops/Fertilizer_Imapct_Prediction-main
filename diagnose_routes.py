import traceback
from backend.app import app

client = app.test_client()
paths = [
    '/',
    '/login',
    '/register',
    '/about',
    '/developer',
    '/crop-recommendation',
    '/fertilizer-recommendation',
    '/crop-disease',
]
for path in paths:
    try:
        resp = client.get(path)
        print(path, resp.status_code)
        if resp.status_code >= 400:
            print(resp.data.decode('utf-8', errors='replace')[:2000])
    except Exception:
        print(path, 'EXCEPTION')
        traceback.print_exc()
