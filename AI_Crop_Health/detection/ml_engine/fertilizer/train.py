import pandas as pd
import joblib
import os

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, classification_report

# =========================================================
# PATH SETUP
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_PATH = os.path.join(
    BASE_DIR,
    "..",
    "dataset",
    "Fertilizer_Prediction.csv"
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "fertilizer_model_py312.pkl"
)

# =========================================================
# LOAD DATA
# =========================================================
df = pd.read_csv(DATASET_PATH)

# =========================================================
# ENCODE CATEGORICAL FEATURES
# =========================================================
le_soil = LabelEncoder()
le_crop = LabelEncoder()
le_fertilizer = LabelEncoder()

df["Soil Type"] = le_soil.fit_transform(df["Soil Type"])
df["Crop Type"] = le_crop.fit_transform(df["Crop Type"])
df["Fertilizer Name"] = le_fertilizer.fit_transform(df["Fertilizer Name"])

# =========================================================
# FEATURES & TARGET
# =========================================================
X = df.drop("Fertilizer Name", axis=1)
y = df["Fertilizer Name"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# =========================================================
# BASE MODEL (STRONG BUT STABLE)
# =========================================================
rf = RandomForestClassifier(
    n_estimators=1000,
    max_depth=12,
    min_samples_split=4,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)

# =========================================================
# CALIBRATED MODEL 
# =========================================================
model = CalibratedClassifierCV(
    rf,
    method="sigmoid",   # BEST for small datasets
    cv=5
)

model.fit(X_train, y_train)

# =========================================================
# EVALUATION
# =========================================================
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("\n🧪 Fertilizer Recommendation Model (Calibrated)")
print("Accuracy:", round(accuracy * 100, 2), "%")
print("\nClassification Report:\n")
print(classification_report(y_test, y_pred))

# =========================================================
# SAVE MODEL + ENCODERS
# =========================================================
joblib.dump(
    {
        "model": model,
        "soil_encoder": le_soil,
        "crop_encoder": le_crop,
        "fertilizer_encoder": le_fertilizer
    },
    MODEL_PATH
)

print("\n✅ Calibrated model saved successfully")
print("📦 Path:", MODEL_PATH)
