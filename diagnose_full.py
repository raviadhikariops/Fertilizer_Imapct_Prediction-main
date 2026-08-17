from backend.app import app
from flask import session
client = app.test_client()
# register or login using a test credentials if already exists
resp = client.post("/register", data={"name":"Test User","email":"test@example.com","password":"secret123","farm_name":"Test Farm","location":"Here"}, follow_redirects=True)
print("REGISTER", resp.status_code)
keys = list(session.keys())
print("SESSION KEYS", keys)
protected = ["/", "/crop-recommendation", "/fertilizer-recommendation", "/chat", "/crop-disease", "/all_responses", "/account", "/about", "/developer"]
for path in protected:
    resp = client.get(path)
    print(path, resp.status_code)
    if resp.status_code >= 400:
        print(resp.data.decode("utf-8", errors="replace")[:1200])
print("API rec", client.post("/api/recommendations", json={"nitrogen":10,"phosphorus":10,"potassium":10,"temperature":25,"humidity":60,"ph":6.5,"rainfall":100,"moisture":20,"soil":"Loamy","crop":"rice","fertilizer":"Urea","amount":100}).status_code)
print("API iot", client.post("/api/iot-sensor", json={"sensor_data":{"temperature":25,"humidity":60,"rainfall":100,"moisture":20}}).status_code)
