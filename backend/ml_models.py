import os
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_DIR = os.path.join(BASE_DIR, "models", "ML_models")

# Feature ordering used by the original AgriGo crop model
FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]

# Reuse the same crop ordering as the AgriGo model to map labels -> names
_crops_map = {
    'apple': 1, 'banana': 2, 'blackgram': 3, 'chickpea': 4, 'coconut': 5, 'coffee': 6, 'cotton': 7,
    'grapes': 8, 'jute': 9, 'kidneybeans': 10, 'lentil': 11, 'maize': 12, 'mango': 13, 'mothbeans': 14,
    'mungbean': 15, 'muskmelon': 16, 'orange': 17, 'paddy': 18, 'papaya': 19, 'pigeonpeas': 20,
    'pomegranate': 21, 'rice': 22, 'watermelon': 23
}

CROPS = list(_crops_map.keys())

_crop_scaler = None
_crop_model = None

def _ensure_crop_loaded():
    global _crop_scaler, _crop_model
    if _crop_scaler is not None and _crop_model is not None:
        return
    scaler_path = os.path.join(MODEL_DIR, "crop_scaler.pkl")
    model_path = os.path.join(MODEL_DIR, "crop_model.pkl")
    if not os.path.exists(scaler_path) or not os.path.exists(model_path):
        raise FileNotFoundError("Crop model artifacts not found in models/ML_models")
    with open(scaler_path, "rb") as fh:
        _crop_scaler = pickle.load(fh)
    with open(model_path, "rb") as fh:
        _crop_model = pickle.load(fh)

def get_crop_recommendation_ml(inputs, limit=5):
    """Return a list of recommendation dicts compatible with the existing UI.

    inputs: dict with keys matching FEATURES
    """
    _ensure_crop_loaded()
    values = [float(inputs.get(f, 0)) for f in FEATURES]
    arr = np.array(values).reshape(1, -1)
    scaled = _crop_scaler.transform(arr)
    pred = _crop_model.predict(scaled)[0]
    try:
        crop_name = CROPS[int(pred)]
    except Exception:
        crop_name = str(pred)

    return [{
        "crop": crop_name.title(),
        "score": 99.9,
        "why": "Predicted by local ML model",
        "profile": {},
    }]


_fert_scaler = None
_fert_model = None
_fert_model_specs = None

def _ensure_fert_loaded():
    global _fert_scaler, _fert_model
    if _fert_scaler is not None and _fert_model is not None:
        return
    scaler_path = os.path.join(MODEL_DIR, "fertilizer_scaler.pkl")
    model_path = os.path.join(MODEL_DIR, "fertilizer_model.pkl")
    if not os.path.exists(scaler_path) or not os.path.exists(model_path):
        raise FileNotFoundError("Fertilizer model artifacts not found in models/ML_models")
    with open(scaler_path, "rb") as fh:
        _fert_scaler = pickle.load(fh)
    with open(model_path, "rb") as fh:
        _fert_model = pickle.load(fh)

def _fertilizer_label_from_index(pred):
    fertilizer_candidates = [
        "Urea",
        "DAP",
        "10-26-26",
        "14-35-14",
        "17-17-17",
        "20-20",
        "28-28",
        "Organic",
    ]
    if isinstance(pred, (int, float)):
        idx = int(pred) % len(fertilizer_candidates)
        return fertilizer_candidates[idx]
    return str(pred)


def _build_fertilizer_models():
    import csv

    dataset_path = os.path.join(BASE_DIR, "data", "fertilizer_prediction.csv")
    if not os.path.exists(dataset_path):
        return None

    rows = list(csv.DictReader(open(dataset_path, encoding="utf-8")))
    X = []
    y = []
    for row in rows:
        X.append({
            "temperature": float(row.get("Temparature", 0) or 0),
            "humidity": float(row.get("Humidity ", 0) or 0),
            "moisture": float(row.get("Moisture", 0) or 0),
            "soil": row.get("Soil Type", ""),
            "crop": row.get("Crop Type", ""),
            "nitrogen": float(row.get("Nitrogen", 0) or 0),
            "potassium": float(row.get("Potassium", 0) or 0),
            "phosphorous": float(row.get("Phosphorous", 0) or 0),
        })
        y.append(row.get("Fertilizer Name", ""))

    numeric_features = ["temperature", "humidity", "moisture", "nitrogen", "potassium", "phosphorous"]
    categorical_features = ["soil", "crop"]
    preprocessor = ColumnTransformer([
        ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric_features),
        ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical_features),
    ])

    rf_model = Pipeline([
        ("preprocess", preprocessor),
        ("classifier", RandomForestClassifier(n_estimators=80, random_state=42))
    ])
    dt_model = Pipeline([
        ("preprocess", preprocessor),
        ("classifier", DecisionTreeClassifier(random_state=42))
    ])

    rf_model.fit(X, y)
    dt_model.fit(X, y)
    return {"random_forest": rf_model, "decision_tree": dt_model}


def get_fertilizer_recommendation_ml(num_features, cat_features):
    """Return fertilizer class predicted by AgriGo fertilizer_model.pkl.

    num_features: list-like numeric features
    cat_features: list-like categorical values (assumed already encoded in AgriGo as strings)
    """
    _ensure_fert_loaded()
    num_arr = np.array(num_features).reshape(1, -1)
    scaled = _fert_scaler.transform(num_arr)
    cat_arr = np.array(cat_features).reshape(1, -1)
    item = np.concatenate([scaled, cat_arr], axis=1)
    pred = _fert_model.predict(item)[0]
    try:
        return int(pred)
    except Exception:
        return pred


def get_fertilizer_recommendation_models(inputs):
    global _fert_model_specs
    if _fert_model_specs is None:
        _fert_model_specs = _build_fertilizer_models()

    if not _fert_model_specs:
        return {
            "baseline": _fertilizer_label_from_index(get_fertilizer_recommendation_ml([
                inputs.get("temperature", 0),
                inputs.get("humidity", 0),
                inputs.get("moisture", 0),
                inputs.get("N", 0),
                inputs.get("P", 0),
                inputs.get("K", 0),
            ], [inputs.get("soil", ""), inputs.get("crop", "")]))
        }

    feature_row = {
        "temperature": float(inputs.get("temperature", 0) or 0),
        "humidity": float(inputs.get("humidity", 0) or 0),
        "moisture": float(inputs.get("moisture", 0) or 0),
        "soil": inputs.get("soil", ""),
        "crop": inputs.get("crop", ""),
        "nitrogen": float(inputs.get("N", 0) or 0),
        "potassium": float(inputs.get("K", 0) or 0),
        "phosphorous": float(inputs.get("P", 0) or 0),
    }
    predictions = {
        "random_forest": _fert_model_specs["random_forest"].predict([feature_row])[0],
        "decision_tree": _fert_model_specs["decision_tree"].predict([feature_row])[0],
    }
    predictions["ensemble"] = predictions["random_forest"]
    return predictions


CROP_DISEASE_CLASSES = {
    'strawberry': [(0, 'Leaf_scorch'), (1, 'healthy')],
    'patato': [(0, 'Early_blight'), (1, 'Late_blight'), (2, 'healthy')],
    'corn': [
        (0, 'Cercospora_leaf_spot Gray_leaf_spot'),
        (1, 'Common_rust_'),
        (2, 'Northern_Leaf_Blight'),
        (3, 'healthy'),
    ],
    'apple': [(0, 'Apple_scab'), (1, 'Black_rot'), (2, 'Cedar_apple_rust'), (3, 'healthy')],
    'cherry': [(0, 'Powdery_mildew'), (1, 'healthy')],
    'grape': [
        (0, 'Black_rot'),
        (1, 'Esca_(Black_Measles)'),
        (2, 'Leaf_blight_(Isariopsis_Leaf_Spot)'),
        (3, 'healthy'),
    ],
    'peach': [(0, 'Bacterial_spot'), (1, 'healthy')],
    'pepper': [(0, 'Bacterial_spot'), (1, 'healthy')],
    'tomato': [
        (0, 'Bacterial_spot'),
        (1, 'Early_blight'),
        (2, 'Late_blight'),
        (3, 'Leaf_Mold'),
        (4, 'Septoria_leaf_spot'),
        (5, 'Spider_mites Two-spotted_spider_mite'),
        (6, 'Target_Spot'),
        (7, 'Tomato_Yellow_Leaf_Curl_Virus'),
        (8, 'Tomato_mosaic_virus'),
        (9, 'healthy'),
    ],
}


def _discover_disease_model_crops():
    model_dir = os.path.join(BASE_DIR, "models", "DL_models")
    crops = []
    try:
        for filename in os.listdir(model_dir):
            if filename.endswith("_model.h5"):
                crop = filename[: -len("_model.h5")]
                if crop in CROP_DISEASE_CLASSES:
                    crops.append(crop)
    except OSError:
        pass
    return sorted(crops)


CROP_DISEASE_LIST = _discover_disease_model_crops()

DISEASE_TREATMENTS = {
    "Apple scab": [
        "Remove infected leaves and dispose of them away from the crop.",
        "Improve airflow by pruning crowded branches.",
        "Apply a copper-based or approved fungicide treatment early in the season.",
    ],
    "Black rot": [
        "Prune infected branches and remove fallen fruit from the field.",
        "Sanitize tools after each pruning session.",
        "Apply a fungicide program designed for black rot control.",
    ],
    "Cedar apple rust": [
        "Remove nearby alternate hosts if possible.",
        "Use fungicide sprays during wet periods.",
        "Monitor the orchard regularly and remove infected tissue promptly.",
    ],
    "Powdery mildew": [
        "Improve ventilation around the canopy.",
        "Apply sulphur or potassium bicarbonate sprays.",
        "Avoid overhead watering and keep foliage dry.",
    ],
    "Early blight": [
        "Remove affected foliage and prune lower leaves.",
        "Avoid overhead watering and improve field drainage.",
        "Apply a recommended fungicide if disease pressure persists.",
    ],
    "Late blight": [
        "Remove infected tissue quickly and destroy it.",
        "Improve airflow and reduce foliage wetness.",
        "Apply a recommended fungicide treatment immediately.",
    ],
    "Bacterial spot": [
        "Prune affected leaves and sanitize pruning tools.",
        "Avoid working in the crop when leaves are wet.",
        "Apply copper-based treatments according to label directions.",
    ],
    "Leaf mold": [
        "Increase airflow and reduce humidity around the crop.",
        "Avoid overhead irrigation.",
        "Apply a fungicide registered for tomato leaf mold.",
    ],
    "Septoria leaf spot": [
        "Remove lower leaves and avoid wet foliage.",
        "Improve air circulation in the crop canopy.",
        "Apply a fungicide when conditions favor disease spread.",
    ],
    "Spider mites": [
        "Wash plants with water to remove mites.",
        "Increase humidity if possible.",
        "Apply miticide or insecticidal soap if needed.",
    ],
    "Target spot": [
        "Prune infected foliage and remove debris.",
        "Use a fungicide program suited for target spot management.",
        "Monitor crop regularly for new symptoms.",
    ],
    "Tomato yellow leaf curl virus": [
        "Control whitefly vectors with approved measures.",
        "Remove and destroy infected plants.",
        "Use resistant varieties where possible.",
    ],
    "Tomato mosaic virus": [
        "Remove infected plants from the field.",
        "Sanitize tools and hands after contact.",
        "Avoid handling healthy plants after infected ones.",
    ],
    "Leaf scorch": [
        "Reduce drought stress with regular irrigation.",
        "Maintain balanced nutrition.",
        "Remove severely damaged leaves carefully.",
    ],
    "Healthy": [
        "No treatment is needed.",
        "Keep monitoring the crop.",
        "Maintain normal irrigation and nutrition.",
    ],
}

DISEASE_FERTILIZERS = {
    "Apple scab": "10-26-26",
    "Black rot": "DAP",
    "Cedar apple rust": "Organic",
    "Powdery mildew": "17-17-17",
    "Early blight": "DAP",
    "Late blight": "17-17-17",
    "Bacterial spot": "Organic",
    "Leaf mold": "14-35-14",
    "Septoria leaf spot": "Urea",
    "Spider mites": "Organic",
    "Target spot": "17-17-17",
    "Tomato yellow leaf curl virus": "Organic",
    "Tomato mosaic virus": "Organic",
    "Leaf scorch": "Organic",
    "Healthy": "Organic",
}


def get_disease_details(crop, prediction):
    """Return the disease label and treatment guidance for a prediction index."""
    classes = CROP_DISEASE_CLASSES.get(crop)
    if not classes:
        raise ValueError(f"No disease classes defined for crop '{crop}'.")

    for idx, name in classes:
        if idx == prediction:
            disease_name = name.replace("_", " ")
            disease_label = disease_name.strip()
            if disease_label.lower() == "healthy":
                disease_label = "Healthy"
            else:
                disease_label = disease_label[:1].upper() + disease_label[1:]
            treatment = DISEASE_TREATMENTS.get(disease_label, "Follow agronomic best practices and consult a local extension agent for specific treatment advice.")
            fertilizer = DISEASE_FERTILIZERS.get(disease_label, "Organic")
            return {"disease": disease_label, "treatment": treatment, "fertilizer": fertilizer}

    return {"disease": "Unknown", "treatment": "Consult a local agronomist for diagnosis and treatment advice.", "fertilizer": "Organic"}


def get_diseases_classes(crop, prediction):
    """Return the human-readable disease name for a crop and prediction index."""
    return get_disease_details(crop, prediction)["disease"]


def img_predict(path, crop):
    # Lazy import tensorflow to avoid protobuf conflict with google-generativeai
    from tensorflow.keras.models import load_model
    from PIL import Image as PILImage

    model_path = os.path.join(BASE_DIR, 'models', 'DL_models', f'{crop}_model.h5')
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"No DL model for crop '{crop}'")
    model = load_model(model_path, compile=False)
    img = PILImage.open(path).resize((224, 224))
    data = np.asarray(img).reshape((-1, 224, 224, 3))
    data = data * 1.0 / 255
    if hasattr(model, 'predict'):
        p = model.predict(data)[0]
        if p.shape and p.shape[0] > 1:
            return int(np.argmax(p))
        return int(np.round(p)[0])
    return 0
