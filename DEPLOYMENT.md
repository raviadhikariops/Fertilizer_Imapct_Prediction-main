# Deployment guide

This project can be deployed using Docker, Heroku (container or buildpack), or Google Cloud Run. Below are quick instructions.

1) Build and run locally with Docker

```bash
docker build -t fertilizer-app .
docker run -e OPENWEATHER_API_KEY=$OPENWEATHER_API_KEY -p 5000:8080 fertilizer-app
# Open http://localhost:5000
```

2) Using docker-compose (local)

```bash
docker-compose up --build
# App available at http://localhost:5000
```

3) Deploy to Google Cloud Run

- Ensure `gcloud` is installed and configured.
- Build and push an image:

```bash
gcloud builds submit --tag gcr.io/PROJECT-ID/fertilizer-app
gcloud run deploy fertilizer-app --image gcr.io/PROJECT-ID/fertilizer-app --platform managed --region us-central1 --allow-unauthenticated --set-env-vars OPENWEATHER_API_KEY=YOUR_KEY
```

4) Deploy to Heroku (Container)

```bash
heroku container:login
heroku create my-fertilizer-app
heroku container:push web --app my-fertilizer-app
heroku container:release web --app my-fertilizer-app
heroku config:set OPENWEATHER_API_KEY=YOUR_KEY --app my-fertilizer-app
```

5) Notes
- Set environment variables (OPENWEATHER_API_KEY, any DB or secret keys) in your cloud provider.
- Use a managed database or storage for production; the project currently uses SQLite by default.
