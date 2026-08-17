# Fertilizer Impact Prediction Using AI and Data Analytics: A Smart Agricultural System for Crop Recommendation, Yield Planning, and Crop Disease Detection Project Report

## 1. Project Overview
Fertilizer Impact Prediction Using AI and Data Analytics: A Smart Agricultural System for Crop Recommendation, Yield Planning, and Crop Disease Detection is a web-based agricultural decision support system designed to help farmers and agricultural users make better crop, fertilizer, and disease-related decisions. The platform combines machine learning inference, deep learning disease detection, and AI-powered guidance into a single user-friendly web application.

The system supports:
- crop recommendation and yield planning
- fertilizer advisor recommendations
- crop disease detection from uploaded leaf images
- AI chat assistance for agricultural guidance
- prediction history and CSV export
- optional guest access and user authentication

## 2. Objectives
The main goals of the application are to:
1. Provide accurate crop and fertilizer recommendations based on soil and environmental conditions.
2. Help users detect crop diseases using image-based deep learning models.
3. Deliver practical treatment guidance, including fertilizer suggestions.
4. Offer an AI assistant that explains recommendations in simple, actionable language.
5. Store user predictions and enable easy review and export.

## 3. Literature Review
This section presents a more detailed review of the research, industry practices, and design principles that influenced the project architecture and implementation.

### 3.1 AI and Data Analytics in Agriculture
Modern agriculture is increasingly driven by data analytics and artificial intelligence. Research and commercial systems demonstrate that precision agriculture can improve crop productivity, resource efficiency, and risk management by integrating:
- soil chemistry and nutrient levels
- weather and microclimate data
- crop phenology and water balance
- historical yield and market information

Studies show that AI systems can support better fertilizer application, reduce nutrient runoff, and improve nutrient use efficiency. This project adopts that paradigm by combining field-level inputs with hybrid scoring models, market-value estimation, and adaptive recommendation logic.

### 3.2 Crop Recommendation and Yield Prediction
The literature on crop recommendation includes both rule-based and machine learning approaches. Rule-based systems use crop profiles and domain expertise to match field conditions to suitable crops, while supervised learning methods use labeled agronomic datasets to learn crop suitability patterns.

Yield prediction research emphasizes a set of core agronomic variables such as NPK balance, soil pH, temperature, humidity, rainfall, and plant moisture. Estimates are often modeled using regression, ensemble methods, or hybrid scoring functions. The project follows this guidance by applying profile similarity for crop ranking and a heuristic yield planning function that reflects local suitability, pH adjustment, moisture influence, and fertilizer impact.

### 3.3 Fertilizer Recommendation Systems
Fertilizer recommendation is a complex domain because it must balance crop nutrition, soil type, and environmental conditions. Agricultural research suggests that the best systems combine expert rules with data-driven insights. Key findings include:
- soil texture and crop species are primary determinants of fertilizer choice
- nutrient gaps should be identified relative to crop requirements
- climate and moisture influence the timing and form of fertilizer application

The project implements a hybrid fertilizer advisor that uses a curated dataset for direct matching, supplemented by optional machine learning predictions when local model artifacts are available. This reduces reliance on any single approach while maintaining agronomic relevance.

### 3.4 Disease Detection with Deep Learning
Plant disease detection has seen strong advances through deep learning, particularly with convolutional neural networks (CNNs). Current research shows that disease models benefit from crop-specific classifiers because each crop has distinct symptom patterns and disease classes.

The project uses crop-specific Keras models for leaf image classification. This approach is aligned with the literature on robust plant disease diagnosis, where preprocessing steps such as image resizing, normalization, and model-specific input shaping are essential to maintain prediction accuracy.

### 3.5 AI-driven Explanation and Chat Assistance
There is growing evidence that recommendation systems are more effective when they provide explanations alongside predictions. In agriculture, users are more likely to adopt advice when it is presented in practical, actionable terms rather than abstract scores.

Conversational AI further enhances adoption by allowing users to ask follow-up questions and receive contextual guidance. The project follows this trend by integrating Gemini and Groq for natural-language enrichment and by maintaining a local fallback so the system remains usable even without external AI access.

### 3.6 System Design Implications
The reviewed research and practices point to several important design principles for the project:
- use a hybrid system design that combines heuristics, ML, and AI explanations
- treat crop and fertilizer advising as agronomic tasks with clear domain constraints
- favor crop-specific disease detection models for higher diagnosis accuracy
- make predictions explainable and actionable for non-experts
- include persistent history and export capabilities to support ongoing decision tracking

These design principles are reflected in the system’s architecture, data flow, and module organization.

## 4. System Architecture
The application is built using Flask as the core web server. The backend handles route processing, user sessions, database operations, AI orchestration, and model inference. The frontend is rendered with Jinja2 templates and styled with custom CSS.

### 4.1 Main Components
- Frontend: HTML templates, CSS, and form-based interaction
- Backend: Flask application in app.py
- Data Layer: SQLite database for users, predictions, and chat history
- ML Layer: Scikit-learn-based crop and fertilizer recommendation inference
- DL Layer: TensorFlow/Keras-based crop disease image classification
- AI Layer: Gemini and Groq APIs for language-based assistance

### 4.2 Code Usage and Project Structure
The project organizes code into distinct functional layers and module types:
- Flask route handlers in `app.py` manage HTTP requests, form submission, page rendering, API endpoints, and authentication flows.
- Data validation and payload construction are implemented in helper functions such as `prediction_payload`, `parse_float`, and `connect_db`.
- Domain logic is separated into crop recommendation, fertilizer recommendation, yield planning, and disease diagnosis functions.
- Machine learning utilities live in `ml_models.py`, where local ML model loading, prediction wrappers, and fallback model-building logic are defined.
- Deep learning inference uses TensorFlow/Keras model loading in `ml_models.py` and image preprocessing with Pillow.
- AI integration code encapsulates Gemini and Groq API calls through `ai_completion`, `groq_completion`, and prompt construction helpers.
- Persistence logic uses SQLite CRUD operations and prediction history management to support saved results and exports.
- Frontend rendering uses Jinja2 templates in `templates/` combined with static CSS in `static/` to create user-facing pages.
- Utility code supports email-based password reset, OTP validation, session management, and guest access.

The report highlights how this mix of backend application code, ML model wrappers, deep learning inference, AI orchestration, and frontend templates creates a practical, full-stack decision support system.

## 5. Application Modules
This section describes the core software modules that implement the platform’s major functionality and how they interact with each other.

### 5.1 Authentication Module
Handles user registration, login, password reset, session validation, and access control. It uses Flask session cookies and secure password hashing.

### 5.2 Yield Planner Module
Accepts field inputs, computes crop suitability, estimates yield range, assesses risk, and produces market-value summaries. It is the primary module for crop planning and decision support.

### 5.3 Crop Advisor Module
Evaluates crop suitability using profile similarity and optional ML ranking. It produces ranked crop recommendations and can augment results with AI explanations.

### 5.4 Fertilizer Advisor Module
Performs fertilizer selection using soil, crop, climate, moisture, and NPK gap analysis. It supports both rule-based matching and optional ML predictions, then adds practical guidance.

### 5.5 Disease Detection Module
Handles image uploads, preprocessing, crop-specific deep learning model selection, disease prediction, and treatment mapping. It also associates fertilizer advice with disease diagnosis.

### 5.6 Chatbot Module
Builds conversational context, manages chat history, and routes user questions to Gemini, Groq, or local fallback logic. It enables conversational agricultural guidance.

### 5.7 History and Export Module
Manages saved predictions, retrieves prediction history, and generates CSV exports for offline review and analysis.

## 6. Functional Modules

### 4.1 Authentication and User Access
Users can register, log in, and reset passwords using OTP email flow. The system also supports guest access so the app can be used without creating an account.

### 4.2 Yield Planner
The yield planner allows users to estimate crop yields based on soil and environmental inputs. It stores predictions in the database and can display the results for further review.

### 4.3 Crop Advisor
The crop advisor provides recommendations based on machine learning and AI guidance. The ML output offers a ranked crop recommendation, while the AI layer explains the result in more natural language.

### 4.4 Fertilizer Advisor
The fertilizer advisor recommends suitable fertilizers based on the provided field conditions. The results include both ML-based fertilizer suggestions and AI-enhanced explanations. The output is formatted to clearly show the fertilizer name and supporting guidance.

### 4.5 Crop Disease Detection
Users can upload leaf images and receive disease predictions along with treatment advice and fertilizer suggestions. The inference uses trained deep learning models stored in the models folder.

### 4.6 AI Chatbot
The chatbot provides conversational agricultural support. It uses stored context from previous interactions and can answer questions about crop care, fertilizer use, disease management, and planning.

### 4.7 Prediction History and Export
The application records previous recommendations and predictions so users can revisit them later. Results can also be exported as CSV files.

## 6. Data and ML Module

### 5.1 Data Sources
Fertilizer Impact Prediction Using AI and Data Analytics: A Smart Agricultural System for Crop Recommendation, Yield Planning, and Crop Disease Detection uses two primary CSV datasets:
- `data/crop_recommendation.csv`
  - contains crop profiles for 22+ crops.
  - profiles include agronomic feature targets for N, P, K, temperature, humidity, pH, and rainfall.
  - this dataset is used to calculate crop fit scores and market-value estimates.
- `data/fertilizer_prediction.csv`
  - contains fertilizer examples for soil, crop, climate, and nutrient conditions.
  - rows include temperature, humidity, moisture, soil type, crop type, N, K, phosphorus, and fertilizer name.
  - this dataset powers rule-based fertilizer matching and can also be used to build local ML recommendations.

### 5.2 Data Flow in the App
- Input is collected from users via HTML forms or API requests.
- The Flask backend validates and normalizes the values.
- Based on the request type, the app executes one or more of:
  - crop suitability scoring
  - fertilizer matching
  - yield estimation
  - disease image inference
  - chatbot context assembly
- Inference results are assembled into structured responses and rendered in templates or returned as JSON.
- Results can be stored in SQLite when the user saves a prediction or continues a chat session.

### 5.3 ML Module Responsibilities
The `ml_models.py` module provides optional local machine learning utilities that enhance the rule-based logic.
- Crop recommendation:
  - loads `models/ML_models/crop_scaler.pkl` and `crop_model.pkl`
  - uses the features N, P, K, temperature, humidity, pH, and rainfall
  - predicts a crop label index and maps it to a crop name
- Fertilizer recommendation:
  - loads `models/ML_models/fertilizer_scaler.pkl` and `fertilizer_model.pkl` when available
  - inputs include numeric field values plus categorical soil and crop values
  - predicts one of several fertilizer classes such as Urea, DAP, Organic, and NPK blends
  - also supports building a local ensemble from `data/fertilizer_prediction.csv` if model artifacts are not present
- Disease detection helpers:
  - maps deep learning output indices to human-readable disease labels
  - provides treatment text and fertilizer advice for each prediction
  - loads crop-specific Keras `.h5` models for image-based inference

### 5.4 ML Module Dependencies
The `ml_models.py` module depends on the following Python libraries and application helpers:
- `os` — manages filesystem paths for model and dataset loading
- `pickle` — loads pre-trained model artifacts from `models/ML_models/`
- `numpy` — handles numeric arrays, reshaping, and preprocessing
- `csv` — reads `data/fertilizer_prediction.csv` for local fertilizer model training
- `sklearn` components:
  - `RandomForestClassifier` — builds a random forest for fertilizer prediction
  - `DecisionTreeClassifier` — builds a decision tree for fertilizer prediction
  - `OneHotEncoder` — encodes categorical features such as soil and crop types
  - `ColumnTransformer` — combines numeric and categorical preprocessing
  - `Pipeline` — sequences preprocessing and estimator steps
  - `SimpleImputer` — fills missing values in numeric and categorical inputs
- `tensorflow.keras.models.load_model` — loads crop-specific deep learning models from `models/DL_models/`
- `PIL.Image` — loads and preprocesses leaf images for disease inference

It also uses in-app helpers to:
- map disease prediction indices to readable disease labels and treatment guidance
- format model outputs into crop and fertilizer recommendation structures
- locate artifacts in `models/ML_models/` and `models/DL_models/`

### 5.5 Deep Learning Module Dependencies
The deep learning module relies on the following dependencies and design elements:
- `tensorflow` / `keras` — defines and loads crop-specific CNN models stored as `.h5` files in `models/DL_models/`
- `PIL.Image` or `Pillow` — opens, resizes, and converts uploaded leaf images for model input
- image preprocessing utilities:
  - resize images to `224x224`
  - normalize pixel values
  - convert images to NumPy arrays and expand dimensions for batch input
- model selection logic that routes an uploaded image to the correct crop-specific model based on user-selected crop
- prediction mapping helpers that translate model output indices into disease names and treatment recommendations
- application integration with Flask file upload handling and template rendering for disease results

## 7. Database Design
The application uses a SQLite database with the following main tables:
- users: stores account information
- predictions: stores crop/fertilizer/yield recommendations and metadata
- chat_messages: stores conversation history

This structure allows persistence across sessions and supports simple analysis and reporting.

## 8. Machine Learning and AI Integration

### 7.1 Rule-Based and ML Hybrid Logic
Fertilizer Impact Prediction Using AI and Data Analytics: A Smart Agricultural System for Crop Recommendation, Yield Planning, and Crop Disease Detection combines rule-based agronomy with optional local ML inference:
- Crop ranking uses profile similarity by default.
- Fertilizer selection uses weighted matches on soil, crop, weather, moisture, and nutrient gaps.
- Where available, local ML models provide alternate crop and fertilizer recommendations.
- AI language services are used to explain and contextualize those recommendations.

### 7.2 Local ML Model Usage
- `get_crop_recommendation_ml()` returns crop suggestions from a pre-trained ML model.
- `get_fertilizer_recommendation_models()` builds or loads local fertilizer models and returns ensemble predictions.
- `get_fertilizer_recommendation_ml()` can also use a saved numeric scaler and classifier to infer fertilizer labels from AgriGo-style inputs.
- These ML helpers are optional: the system falls back to heuristic scoring if the model files are missing or unavailable.

### 7.3 Disease Detection with Deep Learning
- Crop-specific Keras models are stored in `models/DL_models/`.
- Each model is loaded dynamically for the selected crop.
- Uploaded leaf images are resized to 224x224, normalized, and passed through the classifier.
- The numeric model output is mapped to a disease label and treatment guidance.

### 7.4 AI Services and Fallback
- The app uses Gemini as the primary AI text service.
- Groq serves as a fallback if Gemini is unavailable.
- When neither service is configured, the app returns local agronomic guidance rather than failing.

## 9. User Experience
The platform is designed to be accessible and practical for users with limited technical knowledge. It provides simple forms, clear recommendation outputs, and direct guidance for agricultural actions.

## 10. Deployment and Environment Notes
The application is intended to run as a Flask service with Python dependencies installed in a virtual environment. Configuration values such as API keys and mail credentials are loaded from environment variables.

## 11. Strengths
- Combines multiple agricultural intelligence methods in one tool
- Offers both automated prediction and explainable AI guidance
- Supports disease detection through image upload
- Includes prediction history and export support
- Works in both authenticated and guest modes

## 12. Future Enhancements
Potential improvements include:
- adding more crop disease models
- improving recommendation accuracy with larger and more diverse datasets
- integrating real-time weather data for dynamic advisory updates
- connecting IoT sensors for soil moisture, temperature, and environmental tracking
- incorporating satellite imagery and remote sensing for farm-scale monitoring
- adding multilingual support for broader accessibility
- supporting mobile-friendly interfaces for field use
- implementing explainable AI (XAI) to improve trust and transparency
- deploying the platform on cloud infrastructure for scalability and remote access

## 13. Conclusion
Fertilizer Impact Prediction Using AI and Data Analytics: A Smart Agricultural System for Crop Recommendation, Yield Planning, and Crop Disease Detection is a practical and scalable agricultural support platform that brings together machine learning, deep learning, and AI assistance to help users make smarter farming decisions.
