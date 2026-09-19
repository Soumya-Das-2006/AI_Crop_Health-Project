"""
Plant Disease Prediction Engine
================================
Production-ready disease diagnosis system with:
- H5 model loading
- Image preprocessing
- Disease knowledge mapping
- 97% accuracy threshold enforcement
"""

import os
import json
import numpy as np
from PIL import Image
from io import BytesIO

# This model was serialized with Keras 2's H5 format.
os.environ.setdefault('TF_USE_LEGACY_KERAS', '1')

import tensorflow as tf
from tensorflow import keras
from .image_utils import ImageValidator


class PlantDiseasePredictor:
    """
    Main prediction engine for plant disease diagnosis.
    Enforces 97% minimum accuracy threshold.
    """
    
    # Model configuration
    MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'plant_disease_prediction_model.h5')
    CLASS_INDICES_PATH = os.path.join(os.path.dirname(__file__), 'dataset', 'class_indices.json')
    IMAGE_SIZE = (224, 224)  # Standard for most plant disease models
    ACCURACY_THRESHOLD = 97.0
    
    def __init__(self):
        """Initialize model and load class indices."""
        self.model = None
        self.class_indices = {}
        self.disease_knowledge = self._build_disease_knowledge()
        self.image_validator = ImageValidator()
        self._load_model()
        self._load_class_indices()
    
    def _load_model(self):
        """Load the H5 Keras model."""
        try:
            self.model = keras.models.load_model(self.MODEL_PATH)
            print(f"✓ Model loaded successfully from {self.MODEL_PATH}")
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {str(e)}")
    
    def _load_class_indices(self):
        """Load class indices mapping from JSON."""
        try:
            with open(self.CLASS_INDICES_PATH, 'r') as f:
                self.class_indices = json.load(f)
            print(f"✓ Loaded {len(self.class_indices)} disease classes")
        except Exception as e:
            raise RuntimeError(f"Failed to load class indices: {str(e)}")
    
    def _preprocess_image(self, image_file):
        """
        Preprocess uploaded image for model input.
        
        Args:
            image_file: Django UploadedFile object or file-like object
        
        Returns:
            Preprocessed numpy array ready for prediction
        """
        try:
            # Read image
            img = Image.open(image_file)
            
            # Convert to RGB (handle RGBA, grayscale, etc.)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize to model input size
            img = img.resize(self.IMAGE_SIZE)
            
            # Convert to numpy array
            img_array = np.array(img)
            
            # Normalize to [0, 1]
            img_array = img_array.astype('float32') / 255.0
            
            # Add batch dimension
            img_array = np.expand_dims(img_array, axis=0)
            
            return img_array
            
        except Exception as e:
            raise ValueError(f"Image preprocessing failed: {str(e)}")
    
    def _parse_class_name(self, class_name):
        """
        Parse class name into crop and disease components.
        
        Format: "Crop___Disease" or "Crop_(variant)___Disease"
        Example: "Tomato___Late_blight" → Crop: Tomato, Disease: Late blight
        
        Args:
            class_name: Raw class name from model
        
        Returns:
            Tuple of (crop_name, disease_name)
        """
        try:
            # Split by triple underscore
            parts = class_name.split('___')
            
            if len(parts) != 2:
                return "Unknown", "Unknown"
            
            # Extract crop name
            crop_raw = parts[0]
            # Clean crop name (remove parenthetical variants)
            crop_name = crop_raw.split('(')[0].strip()
            # Capitalize properly
            crop_name = crop_name.replace('_', ' ').title()
            
            # Extract disease name
            disease_raw = parts[1]
            # Handle "healthy" case
            if disease_raw.lower() == 'healthy':
                disease_name = "Healthy"
            else:
                # Replace underscores with spaces and capitalize
                disease_name = disease_raw.replace('_', ' ').title()
            
            return crop_name, disease_name
            
        except Exception:
            return "Unknown", "Unknown"
    
    def _get_diagnosis_status(self, confidence):
        """
        Determine diagnosis reliability status based on confidence.
        
        Args:
            confidence: Confidence percentage (0-100)
        
        Returns:
            String: "reliable", "caution", or "unreliable"
        """
        if confidence >= self.ACCURACY_THRESHOLD:
            return "reliable"
        elif confidence >= 90.0:
            return "caution"
        else:
            return "unreliable"
    
    def _get_disease_info(self, disease_name, crop_name):
        """
        Get detailed disease information from knowledge base.
        
        Args:
            disease_name: Name of the disease
            crop_name: Name of the crop
        
        Returns:
            Dictionary with cause, symptoms, solutions, prevention
        """
        # Handle healthy case
        if disease_name.lower() == "healthy":
            return {
                "cause": f"No disease detected. The {crop_name} plant appears healthy with no visible signs of infection or stress.",
                "symptoms": [
                    "Vibrant green leaves with no discoloration",
                    "No spots, lesions, or abnormal growth patterns",
                    "Normal leaf structure and plant vigor",
                    "No visible pest damage"
                ],
                "solutions": [
                    "Continue current care practices",
                    "Maintain regular monitoring schedule",
                    "Ensure adequate nutrition and water",
                    "Keep field hygiene standards high"
                ],
                "prevention": [
                    "Maintain balanced fertilization schedule",
                    "Ensure proper irrigation (avoid over/under watering)",
                    "Monitor regularly for early disease detection",
                    "Practice crop rotation annually",
                    "Remove plant debris and weeds promptly",
                    "Use disease-resistant varieties when available"
                ]
            }
        
        # Check knowledge base
        disease_key = disease_name.lower()
        
        # Search for disease in knowledge base
        for key, info in self.disease_knowledge.items():
            if key.lower() in disease_key or disease_key in key.lower():
                return info
        
        # Fallback for unknown diseases
        return {
            "cause": f"{disease_name} is a plant disease affecting {crop_name}. Environmental factors such as high humidity, poor air circulation, and temperature stress may contribute to disease development. Consult with a local agricultural expert for specific pathogen identification.",
            "symptoms": [
                "Abnormal leaf discoloration or spots",
                "Unusual growth patterns or deformities",
                "Possible lesions or damaged tissue",
                "Reduced plant vigor or wilting"
            ],
            "solutions": [
                "Remove and destroy infected plant material",
                "Improve air circulation around plants",
                "Reduce leaf wetness by adjusting irrigation",
                "Apply appropriate fungicide or bactericide as recommended",
                "Consult local agricultural extension service for treatment options"
            ],
            "prevention": [
                "Use certified disease-free seeds or transplants",
                "Practice crop rotation (3-4 year cycle)",
                "Maintain proper plant spacing for air circulation",
                "Avoid overhead irrigation during humid conditions",
                "Remove crop debris after harvest",
                "Scout fields regularly for early disease detection"
            ]
        }
    
    def predict(self, image_file):
        """
        Main prediction method - generates complete diagnosis report.
        
        Args:
            image_file: Uploaded image file
        
        Returns:
            Dictionary with complete diagnosis information
        """
        try:
            # Preprocess image
            img_array = self._preprocess_image(image_file)
            
            # Get prediction
            predictions = self.model.predict(img_array, verbose=0)
            
            # Get class with highest probability
            class_index = int(np.argmax(predictions[0]))
            confidence = float(predictions[0][class_index]) * 100
            
            # Get class name
            class_name = self.class_indices.get(str(class_index), "Unknown")
            
            # Parse crop and disease
            crop_name, disease_name = self._parse_class_name(class_name)
            
            # Get diagnosis status
            diagnosis_status = self._get_diagnosis_status(confidence)
            
            # Get disease information
            disease_info = self._get_disease_info(disease_name, crop_name)
            
            # Build complete response
            result = {
                # Core prediction
                "crop": crop_name,
                "disease": disease_name,
                "confidence": round(confidence, 2),
                "confidence_bar": int(confidence),
                "class_index": class_index,
                "class_name": class_name,

                # Accuracy enforcement
                "diagnosis_status": diagnosis_status,
                "accuracy_threshold": self.ACCURACY_THRESHOLD,
                "model_expected_accuracy": ">=97%",
                "meets_threshold": confidence >= self.ACCURACY_THRESHOLD,

                # Disease information
                "cause": disease_info["cause"],
                "symptoms": disease_info["symptoms"],
                "solutions": disease_info["solutions"],
                "prevention": disease_info["prevention"],

                # Status messages
                "status_message": self._get_status_message(diagnosis_status, confidence),
                "recommendation": self._get_recommendation(diagnosis_status),
                "status_badge": self._get_status_badge(diagnosis_status)
            }
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Prediction failed: {str(e)}")
    
    def _get_status_message(self, status, confidence):
        """Generate appropriate status message based on diagnosis status."""
        if status == "reliable":
            return f"High confidence diagnosis ({confidence:.1f}%). Results are reliable."
        elif status == "caution":
            return f"⚠️ Moderate confidence ({confidence:.1f}%). Results may need verification."
        else:
            return f"⚠️ Low confidence diagnosis ({confidence:.1f}%). Please capture a clearer image or consult an expert."
    
    def _get_recommendation(self, status):
        """Generate action recommendation based on diagnosis status."""
        if status == "reliable":
            return "Proceed with recommended treatment plan."
        elif status == "caution":
            return "Consider retaking the image with better lighting and focus for improved accuracy."
        else:
            return "Image quality insufficient for accurate diagnosis. Please provide a clearer, well-lit close-up image of affected plant parts."

    def _get_status_badge(self, status):
        """Get human-readable status badge text"""
        return {
            "reliable": "Reliable (≥97%)",
            "caution": "Caution (90-96%)",
            "unreliable": "Unreliable (<90%)",
        }.get(status, "Unknown")
    
    def _build_disease_knowledge(self):
        """
        Build comprehensive disease knowledge base.
        Maps diseases to their causes, symptoms, solutions, and prevention.
        """
        return {
            # ========== APPLE DISEASES ==========
            "Apple Scab": {
                "cause": "Fungal infection caused by Venturia inaequalis. Thrives in cool, wet spring weather (60-70°F). Spreads through airborne spores from infected leaf litter and bark lesions.",
                "symptoms": [
                    "Olive-green to brown spots on leaves and fruit",
                    "Velvety or powdery appearance on lesions",
                    "Premature leaf drop and fruit deformity",
                    "Corky, cracked patches on mature fruit"
                ],
                "solutions": [
                    "Remove and destroy fallen leaves and infected fruit",
                    "Apply fungicides (captan, myclobutanil) at green tip stage",
                    "Continue spray program through petal fall",
                    "Prune trees to improve air circulation",
                    "Use organic alternatives: sulfur or copper sprays"
                ],
                "prevention": [
                    "Plant scab-resistant varieties (Liberty, Enterprise, Freedom)",
                    "Maintain 12-15 feet spacing between trees",
                    "Remove leaf litter in fall to eliminate overwintering spores",
                    "Avoid overhead irrigation that wets foliage",
                    "Apply dormant lime-sulfur spray in early spring"
                ]
            },
            
            "Black Rot": {
                "cause": "Fungal pathogen Botryosphaeria obtusa. Favored by warm, humid conditions. Overwinters in infected fruit mummies and cankers on branches.",
                "symptoms": [
                    "Purple or red spots on leaves that enlarge with age",
                    "Concentric rings form in leaf spots ('frog-eye' pattern)",
                    "Fruit rot starts as small brown spot, spreads rapidly",
                    "Infected fruit becomes black, shriveled mummy",
                    "Branch cankers with rough, sunken bark"
                ],
                "solutions": [
                    "Prune out all dead and diseased wood during dormancy",
                    "Remove mummified fruit from tree and ground",
                    "Apply fungicides (captan, thiophanate-methyl) starting at pink bud",
                    "Continue applications through summer",
                    "Destroy pruned material; do not compost"
                ],
                "prevention": [
                    "Remove fruit mummies during winter pruning",
                    "Prune to maintain open canopy structure",
                    "Avoid wounding bark during cultivation",
                    "Control insects that create entry wounds",
                    "Apply preventive fungicide program in early season"
                ]
            },
            
            "Cedar Apple Rust": {
                "cause": "Fungal disease caused by Gymnosporangium juniperi-virginianae. Requires two hosts: apple trees and eastern red cedar (juniper). Wet spring weather promotes spore release.",
                "symptoms": [
                    "Bright yellow-orange spots on upper leaf surface",
                    "Small tube-like structures on lower leaf surface",
                    "Premature leaf drop in severe infections",
                    "Orange spots on fruit surface",
                    "Fruit may become misshapen or drop early"
                ],
                "solutions": [
                    "Remove nearby juniper hosts within 2-mile radius if possible",
                    "Apply fungicides (myclobutanil, propiconazole) at pink bud stage",
                    "Repeat applications every 7-10 days during wet spring weather",
                    "Remove galls from nearby junipers in late winter",
                    "Plant rust-resistant apple varieties"
                ],
                "prevention": [
                    "Choose rust-resistant cultivars (Liberty, Freedom, Enterprise)",
                    "Avoid planting apples near eastern red cedar",
                    "Remove volunteer cedar seedlings from area",
                    "Begin protective fungicide program early in season",
                    "Maintain good air circulation through proper pruning"
                ]
            },
            
            # ========== CHERRY DISEASES ==========
            "Powdery Mildew": {
                "cause": "Fungal disease caused by Podosphaera clandestina. Thrives in warm days (70-80°F) and cool nights. Does not require water on leaves to germinate, unlike most fungi.",
                "symptoms": [
                    "White powdery coating on leaves, shoots, and fruit",
                    "Distorted or stunted new growth",
                    "Leaves may curl upward",
                    "Premature leaf drop in severe cases",
                    "Reduced fruit quality and tree vigor"
                ],
                "solutions": [
                    "Prune infected shoots and remove from orchard",
                    "Apply sulfur-based fungicides every 7-14 days",
                    "Use systemic fungicides (myclobutanil, tebuconazole)",
                    "Spray neem oil for organic management",
                    "Improve air circulation by thinning dense canopy"
                ],
                "prevention": [
                    "Plant resistant cherry varieties when available",
                    "Space trees properly for air movement (15-20 feet)",
                    "Avoid excessive nitrogen fertilization",
                    "Remove and destroy infected plant material",
                    "Apply preventive sulfur sprays in early season",
                    "Water at base of plant, not overhead"
                ]
            },
            
            # ========== CORN DISEASES ==========
            "Cercospora Leaf Spot": {
                "cause": "Fungal pathogen Cercospora zeae-maydis. Favored by warm, humid weather (75-85°F) and heavy dews. Spreads via wind and rain splash.",
                "symptoms": [
                    "Rectangular gray to tan lesions on leaves",
                    "Lesions bounded by leaf veins creating 'brick-like' pattern",
                    "Yellowing of leaf tissue around spots",
                    "Premature leaf death in severe infections",
                    "Reduced photosynthesis and yield potential"
                ],
                "solutions": [
                    "Plant resistant hybrid varieties",
                    "Apply foliar fungicides (strobilurin, triazole) at first symptom",
                    "Time applications during tasseling to silking stage",
                    "Rotate fungicide classes to prevent resistance",
                    "Remove crop residue after harvest"
                ],
                "prevention": [
                    "Use certified disease-free seed",
                    "Practice 2-3 year crop rotation with non-host crops",
                    "Till under crop residue to reduce overwintering inoculum",
                    "Avoid continuous corn in same field",
                    "Plant hybrids with tolerance to gray leaf spot",
                    "Monitor fields during warm, humid weather"
                ]
            },
            
            "Common Rust": {
                "cause": "Fungal disease Puccinia sorghi. Requires cool, moist conditions (60-75°F). Spores spread by wind from southern regions. Cannot overwinter in northern climates.",
                "symptoms": [
                    "Small, circular to elongate reddish-brown pustules on leaves",
                    "Pustules appear on both upper and lower leaf surfaces",
                    "As disease progresses, pustules darken to black",
                    "Heavy infection causes premature leaf death",
                    "Yield loss primarily from reduced photosynthesis"
                ],
                "solutions": [
                    "Plant resistant corn hybrids (most effective control)",
                    "Apply fungicides if detected before tasseling on susceptible hybrids",
                    "Use triazole or strobilurin fungicides",
                    "Scout fields regularly during cool, wet periods",
                    "Early planting may avoid peak infection period"
                ],
                "prevention": [
                    "Select rust-resistant hybrid varieties",
                    "Plant early to mature before peak rust season",
                    "Monitor regional rust movement reports",
                    "Maintain balanced fertility (avoid excess nitrogen)",
                    "Consider fungicide at tasseling for high-value seed corn"
                ]
            },
            
            "Northern Leaf Blight": {
                "cause": "Fungal pathogen Exserohilum turcicum. Favored by moderate temperatures (65-80°F) and high humidity. Overwinters in corn residue.",
                "symptoms": [
                    "Long, elliptical gray-green to tan lesions on leaves",
                    "Lesions may be 1-6 inches long",
                    "Blights typically start on lower leaves and move upward",
                    "Severe infection causes complete leaf death",
                    "Significant yield reduction if upper leaves affected"
                ],
                "solutions": [
                    "Plant hybrids with resistance genes (Ht genes)",
                    "Apply fungicides at early symptom development",
                    "Use strobilurin or triazole fungicides at V5-V8 stage",
                    "Repeat application at tasseling if disease pressure high",
                    "Bury crop residue through deep tillage"
                ],
                "prevention": [
                    "Choose resistant hybrids with Ht1, Ht2, or Ht3 genes",
                    "Practice minimum 1-year rotation away from corn",
                    "Till under corn residue to reduce inoculum",
                    "Avoid continuous corn production",
                    "Monitor lower leaves during vegetative growth",
                    "Maintain field scouting program"
                ]
            },
            
            # ========== GRAPE DISEASES ==========
            "Grape Black Rot": {
                "cause": "Fungal disease Guignardia bidwellii. Requires warm, wet weather (70-90°F). Overwinters in mummified fruit and infected canes.",
                "symptoms": [
                    "Small reddish-brown spots on leaves with dark borders",
                    "Fruit infection causes brown, rotted appearance",
                    "Infected berries shrivel into hard, black mummies",
                    "Cane lesions are elongated and sunken",
                    "Complete crop loss possible in untreated vineyards"
                ],
                "solutions": [
                    "Remove and destroy mummified fruit",
                    "Prune out infected canes during dormancy",
                    "Apply fungicides (mancozeb, captan) from bud break",
                    "Continue applications through bloom and berry development",
                    "Improve air circulation through canopy management"
                ],
                "prevention": [
                    "Remove all mummies during winter pruning",
                    "Practice proper canopy management for air flow",
                    "Apply dormant copper spray before bud break",
                    "Maintain preventive fungicide program during wet weather",
                    "Remove wild grape hosts near vineyard"
                ]
            },
            
            "Esca (Black Measles)": {
                "cause": "Complex of fungal pathogens including Phaeoacremonium and Phaeomoniella. Wood-degrading fungi enter through pruning wounds. Stress factors (drought, heat) trigger symptom expression.",
                "symptoms": [
                    "Tiger-stripe pattern on leaves (yellow and green bands)",
                    "Interveinal necrosis and leaf scorch",
                    "Dark streaking in wood when cane is cut",
                    "Sudden vine collapse (apoplexy) in summer",
                    "Berries show black spots ('black measles')",
                    "Progressive decline over multiple years"
                ],
                "solutions": [
                    "No curative treatment available",
                    "Remove severely infected vines",
                    "Prune out symptomatic wood during dormancy",
                    "Apply wound protectants after pruning cuts",
                    "Reduce vine stress through irrigation and nutrition",
                    "Delay pruning until late winter to allow wound healing"
                ],
                "prevention": [
                    "Use clean, disease-free planting material",
                    "Sterilize pruning tools between vines (10% bleach solution)",
                    "Apply wound sealants immediately after pruning",
                    "Avoid pruning during wet weather",
                    "Maintain vine vigor through proper irrigation and nutrition",
                    "Remove infected wood from vineyard"
                ]
            },
            
            "Leaf Blight (Isariopsis)": {
                "cause": "Fungal pathogen Isariopsis clavispora (Pseudocercospora vitis). Thrives in warm, humid conditions. Spreads through rain splash and wind.",
                "symptoms": [
                    "Angular brown spots on leaves",
                    "Spots often surrounded by yellow halo",
                    "Dark fungal growth on underside of lesions",
                    "Premature defoliation in severe cases",
                    "Reduced photosynthesis and vine vigor"
                ],
                "solutions": [
                    "Apply copper-based fungicides at first symptom",
                    "Use mancozeb or captan for disease control",
                    "Improve air circulation through canopy thinning",
                    "Remove heavily infected leaves",
                    "Adjust irrigation to reduce leaf wetness duration"
                ],
                "prevention": [
                    "Practice proper canopy management",
                    "Ensure adequate spacing between vines",
                    "Avoid overhead irrigation",
                    "Remove fallen leaves from vineyard",
                    "Apply preventive fungicides during wet weather",
                    "Monitor for early disease development"
                ]
            },
            
            # ========== ORANGE DISEASES ==========
            "Huanglongbing (Citrus Greening)": {
                "cause": "Bacterial disease caused by Candidatus Liberibacter species. Transmitted by Asian citrus psyllid insect. No cure exists. Considered most destructive citrus disease worldwide.",
                "symptoms": [
                    "Yellow shoots and blotchy, mottled leaves",
                    "Asymmetrical leaf yellowing across midvein",
                    "Small, lopsided fruit with green coloration",
                    "Bitter, unusable fruit",
                    "Premature fruit drop",
                    "Progressive tree decline and death within 5-8 years"
                ],
                "solutions": [
                    "Remove and destroy infected trees immediately",
                    "Control psyllid vectors with systemic insecticides",
                    "Apply foliar nutritional sprays to slow decline",
                    "Use imidacloprid or thiamethoxam for psyllid control",
                    "No chemical cure for bacterial infection",
                    "Replant only with certified disease-free trees"
                ],
                "prevention": [
                    "Use certified HLB-free nursery stock",
                    "Implement aggressive psyllid management program",
                    "Scout regularly for psyllids and disease symptoms",
                    "Apply systemic insecticides preventively",
                    "Remove symptomatic trees to reduce inoculum",
                    "Avoid moving plant material from infected areas",
                    "Plant barrier crops or reflective mulches to deter psyllids"
                ]
            },
            
            # ========== PEACH DISEASES ==========
            "Peach Bacterial Spot": {
                "cause": "Bacterial pathogen Xanthomonas arboricola. Spread by wind-driven rain and overhead irrigation. Warm, wet weather (75-85°F) favors infection.",
                "symptoms": [
                    "Small, dark purple spots on leaves",
                    "Spots may have yellow halos",
                    "Shot-hole appearance as leaf tissue falls out",
                    "Fruit lesions are dark, sunken, and rough",
                    "Premature leaf drop and reduced fruit quality",
                    "Twig cankers on current season's growth"
                ],
                "solutions": [
                    "Apply copper-based bactericides during dormancy",
                    "Use oxytetracycline (antibiotic) during bloom",
                    "Prune out infected twigs during dry weather",
                    "Improve air circulation through canopy thinning",
                    "Reduce overhead irrigation and leaf wetness",
                    "Destroy pruned material"
                ],
                "prevention": [
                    "Plant resistant peach varieties when available",
                    "Apply copper sprays at leaf fall and before bud swell",
                    "Maintain tree vigor through proper nutrition",
                    "Prune for open canopy and good air movement",
                    "Avoid excessive nitrogen that promotes succulent growth",
                    "Use drip irrigation instead of overhead sprinklers",
                    "Minimize handling of wet foliage"
                ]
            },
            
            # ========== PEPPER DISEASES ==========
            "Pepper Bacterial Spot": {
                "cause": "Bacterial pathogens Xanthomonas spp. Spread by water splash, tools, and handling. Warm (75-86°F), humid conditions favor disease. Can be seedborne.",
                "symptoms": [
                    "Small, dark brown to black spots on leaves",
                    "Spots often have yellow halos",
                    "Raised, scab-like lesions on fruit",
                    "Fruit spots may have white halo",
                    "Severe defoliation reduces yield and fruit quality",
                    "Lower leaves affected first"
                ],
                "solutions": [
                    "Remove and destroy infected plants",
                    "Apply copper-based bactericides (fixed copper)",
                    "Use biological control agents (Bacillus subtilis)",
                    "Improve air circulation by proper spacing and pruning",
                    "Avoid overhead irrigation",
                    "Sanitize tools with 10% bleach solution"
                ],
                "prevention": [
                    "Use certified disease-free seeds and transplants",
                    "Rotate crops (3-4 years away from solanaceous crops)",
                    "Avoid working with plants when wet",
                    "Space plants adequately for air circulation",
                    "Mulch to prevent soil splash onto foliage",
                    "Apply preventive copper sprays in transplant beds",
                    "Practice strict field sanitation"
                ]
            },
            
            # ========== POTATO DISEASES ==========
            "Potato Early Blight": {
                "cause": "Fungal pathogen Alternaria solani. Favored by warm temperatures (75-85°F) and high humidity. Overwinters in infected plant debris and soil.",
                "symptoms": [
                    "Dark brown lesions with concentric rings ('target' pattern)",
                    "Lesions start on older, lower leaves",
                    "Yellow halo may surround lesions",
                    "Stem lesions are dark and sunken",
                    "Tuber infection shows dark, sunken areas",
                    "Premature defoliation reduces yield"
                ],
                "solutions": [
                    "Remove and destroy infected plant material",
                    "Apply fungicides (chlorothalonil, mancozeb) at first symptom",
                    "Repeat applications every 7-10 days",
                    "Use alternating fungicide modes of action",
                    "Maintain adequate plant nutrition (especially nitrogen)",
                    "Hill soil to protect developing tubers"
                ],
                "prevention": [
                    "Use certified disease-free seed potatoes",
                    "Practice 3-4 year crop rotation",
                    "Remove volunteer potatoes and nightshade weeds",
                    "Maintain balanced fertility (avoid low nitrogen stress)",
                    "Apply mulch to reduce soil splash",
                    "Destroy crop residue after harvest",
                    "Begin preventive fungicide program early"
                ]
            },
            
            "Potato Late Blight": {
                "cause": "Oomycete pathogen Phytophthora infestans (same organism that caused Irish Potato Famine). Requires cool (50-70°F), wet conditions. Spreads rapidly during wet weather.",
                "symptoms": [
                    "Water-soaked, grayish-green lesions on leaves",
                    "White fungal growth on underside of lesions",
                    "Rapid expansion of lesions during humid weather",
                    "Dark brown to black stems",
                    "Complete plant collapse within days in severe cases",
                    "Tuber infection shows reddish-brown rot"
                ],
                "solutions": [
                    "Apply fungicides immediately at first symptom",
                    "Use chlorothalonil, mancozeb, or systemic fungicides",
                    "Apply every 5-7 days during wet weather",
                    "Destroy infected plants immediately (bag and remove)",
                    "Do NOT compost infected material",
                    "Kill vines 2-3 weeks before harvest to protect tubers"
                ],
                "prevention": [
                    "Plant certified seed from disease-free sources",
                    "Use resistant varieties when available",
                    "Monitor weather for late blight conditions",
                    "Apply preventive fungicides before disease appears",
                    "Eliminate cull piles and volunteer potatoes",
                    "Ensure good field drainage",
                    "Hill rows adequately to protect tubers",
                    "Remove and destroy infected tomato plants nearby"
                ]
            },
            
            # ========== SQUASH DISEASES ==========
            "Squash Powdery Mildew": {
                "cause": "Fungal pathogens (multiple species: Podosphaera, Erysiphe). Thrives in warm days (70-80°F) and cool nights. Does not require leaf wetness.",
                "symptoms": [
                    "White, powdery spots on upper leaf surfaces",
                    "Spots coalesce to cover entire leaf",
                    "Lower leaves affected first",
                    "Yellowing and death of infected leaves",
                    "Reduced photosynthesis and fruit quality",
                    "Premature fruit ripening"
                ],
                "solutions": [
                    "Apply sulfur-based fungicides at first symptom",
                    "Use potassium bicarbonate for organic control",
                    "Apply systemic fungicides (myclobutanil) for severe cases",
                    "Remove heavily infected leaves",
                    "Improve air circulation around plants",
                    "Apply neem oil weekly"
                ],
                "prevention": [
                    "Plant resistant varieties (most effective control)",
                    "Provide adequate plant spacing (3-4 feet)",
                    "Avoid overhead irrigation",
                    "Remove crop debris after harvest",
                    "Apply preventive sulfur or neem oil sprays",
                    "Ensure good air circulation",
                    "Avoid excessive nitrogen fertilization"
                ]
            },
            
            # ========== STRAWBERRY DISEASES ==========
            "Strawberry Leaf Scorch": {
                "cause": "Fungal pathogen Diplocarpon earlianum. Favored by warm (70-80°F), wet conditions. Spreads via splashing water and wind.",
                "symptoms": [
                    "Numerous small purple to brown spots on leaves",
                    "Spots enlarge and may have purplish borders",
                    "Centers of lesions turn grayish to white",
                    "Severely infected leaves appear scorched",
                    "Premature leaf death and plant weakening",
                    "Reduced fruit production in subsequent year"
                ],
                "solutions": [
                    "Remove and destroy infected leaves",
                    "Apply fungicides (captan, thiram) at first symptom",
                    "Repeat applications every 7-10 days",
                    "Improve air circulation by thinning plants",
                    "Renovate strawberry beds after harvest",
                    "Mow and remove old foliage"
                ],
                "prevention": [
                    "Plant resistant cultivars when available",
                    "Use certified disease-free planting stock",
                    "Space plants properly for air flow",
                    "Use drip irrigation to keep foliage dry",
                    "Remove and destroy crop debris",
                    "Apply preventive fungicides during wet weather",
                    "Renovate beds promptly after harvest"
                ]
            },
            
            # ========== TOMATO DISEASES ==========
            "Tomato Bacterial Spot": {
                "cause": "Bacterial pathogens Xanthomonas spp. Seedborne and spread by water, tools, and workers. Warm (75-86°F), wet conditions favor disease.",
                "symptoms": [
                    "Small, dark brown to black spots on leaves",
                    "Spots may have yellow halos",
                    "Raised, scab-like lesions on fruit",
                    "Fruit spots may crack and provide entry for rot",
                    "Severe defoliation in susceptible varieties",
                    "Reduced fruit quality and marketability"
                ],
                "solutions": [
                    "Remove and destroy infected plants",
                    "Apply copper-based bactericides",
                    "Use biological controls (Bacillus pumilus, B. subtilis)",
                    "Improve air circulation through staking and pruning",
                    "Avoid overhead irrigation and working with wet plants",
                    "Rotate to non-host crops for 3-4 years"
                ],
                "prevention": [
                    "Use certified disease-free seeds and transplants",
                    "Practice crop rotation with non-solanaceous crops",
                    "Space plants for adequate air circulation",
                    "Stake or cage plants to keep foliage off ground",
                    "Mulch to prevent soil splash",
                    "Avoid working in wet fields",
                    "Disinfect tools and equipment regularly"
                ]
            },
            
            "Tomato Early Blight": {
                "cause": "Fungal pathogen Alternaria solani. Favored by warm temperatures (75-85°F), high humidity, and leaf wetness. Overwinters in plant debris.",
                "symptoms": [
                    "Dark brown lesions with concentric rings on older leaves",
                    "Target-spot appearance",
                    "Yellowing around lesions",
                    "Stem and fruit lesions are dark and sunken",
                    "Collar rot at soil line in seedlings",
                    "Progressive defoliation from bottom upward"
                ],
                "solutions": [
                    "Remove lower infected leaves",
                    "Apply fungicides (chlorothalonil, mancozeb) at first symptom",
                    "Repeat applications every 7-10 days",
                    "Stake plants to improve air circulation",
                    "Mulch to prevent soil splash onto lower leaves",
                    "Maintain adequate plant nutrition"
                ],
                "prevention": [
                    "Use certified disease-free transplants",
                    "Practice 3-4 year crop rotation",
                    "Space plants adequately for air flow",
                    "Stake or cage plants to keep foliage dry",
                    "Apply mulch to reduce soil splash",
                    "Remove and destroy plant debris after harvest",
                    "Begin preventive fungicide program early"
                ]
            },
            
            "Tomato Late Blight": {
                "cause": "Oomycete Phytophthora infestans. Requires cool (50-70°F), wet conditions. Can spread rapidly over large areas. Devastating under favorable conditions.",
                "symptoms": [
                    "Large, irregular, water-soaked lesions on leaves",
                    "White fuzzy growth on underside during humid weather",
                    "Greasy appearance on stems",
                    "Rapid plant collapse during wet weather",
                    "Firm, brown lesions on green fruit",
                    "Entire field can be destroyed within days"
                ],
                "solutions": [
                    "Apply fungicides immediately (chlorothalonil, mancozeb)",
                    "Use systemic fungicides for curative action",
                    "Apply every 5-7 days during wet weather",
                    "Remove and destroy infected plants promptly",
                    "Do NOT compost infected material",
                    "Scout neighboring fields for disease"
                ],
                "prevention": [
                    "Plant resistant varieties when available",
                    "Use certified disease-free transplants",
                    "Monitor late blight forecasting systems",
                    "Apply preventive fungicides before disease appears",
                    "Space plants for rapid foliage drying",
                    "Remove volunteer tomatoes and potatoes",
                    "Destroy cull piles",
                    "Ensure good field drainage"
                ]
            },
            
            "Tomato Leaf Mold": {
                "cause": "Fungal pathogen Passalora fulva (Fulvia fulva). Greenhouse and high tunnel disease. Requires high humidity (>85%) and moderate temperatures (70-75°F).",
                "symptoms": [
                    "Yellow spots on upper leaf surface",
                    "Velvety olive-green to brown growth on lower surface",
                    "Older leaves affected first",
                    "Leaves curl, wither, and drop prematurely",
                    "Rarely affects fruit directly",
                    "Reduced yield due to defoliation"
                ],
                "solutions": [
                    "Improve greenhouse ventilation immediately",
                    "Reduce humidity below 85%",
                    "Remove infected leaves",
                    "Apply fungicides (chlorothalonil, mancozeb)",
                    "Increase plant spacing for air flow",
                    "Heat greenhouse to reduce humidity"
                ],
                "prevention": [
                    "Plant resistant varieties with Cf genes",
                    "Maintain greenhouse humidity below 85%",
                    "Ensure adequate ventilation and air circulation",
                    "Space plants properly",
                    "Avoid overhead irrigation",
                    "Remove crop debris promptly",
                    "Sterilize greenhouse between crops"
                ]
            },
            
            "Tomato Septoria Leaf Spot": {
                "cause": "Fungal pathogen Septoria lycopersici. Favored by warm (68-77°F), wet weather. Spreads via rain splash. Overwinters in plant debris.",
                "symptoms": [
                    "Small, circular spots with gray centers on older leaves",
                    "Dark brown borders around spots",
                    "Tiny black dots (pycnidia) visible in spot centers",
                    "Spots may coalesce, causing leaf yellowing",
                    "Progressive defoliation from bottom up",
                    "Reduced fruit size and quality"
                ],
                "solutions": [
                    "Remove and destroy lower infected leaves",
                    "Apply fungicides (chlorothalonil, mancozeb) at first symptom",
                    "Repeat applications every 7-10 days",
                    "Mulch heavily to prevent soil splash",
                    "Stake plants to lift foliage off ground",
                    "Improve air circulation"
                ],
                "prevention": [
                    "Use pathogen-free seeds and transplants",
                    "Practice 3-year crop rotation",
                    "Space plants for adequate air circulation",
                    "Mulch to reduce soil splash",
                    "Avoid overhead irrigation",
                    "Remove volunteer tomatoes",
                    "Destroy plant debris after harvest",
                    "Begin preventive fungicide program"
                ]
            },
            
            "Spider Mites (Two-Spotted)": {
                "cause": "Arachnid pest Tetranychus urticae. Not a disease but a common damaging pest. Favored by hot (>80°F), dry conditions. Reproduces rapidly.",
                "symptoms": [
                    "Tiny yellow or white stippling on leaves",
                    "Fine webbing on undersides of leaves",
                    "Bronzing or silvering of foliage",
                    "Leaf curling and wilting in severe infestations",
                    "Premature leaf drop",
                    "Reduced plant vigor and fruit production"
                ],
                "solutions": [
                    "Spray plants forcefully with water to dislodge mites",
                    "Apply insecticidal soap or horticultural oil",
                    "Use miticides (abamectin, spiromesifen) for severe infestations",
                    "Release predatory mites (Phytoseiulus persimilis)",
                    "Remove heavily infested plants",
                    "Rotate miticide classes to prevent resistance"
                ],
                "prevention": [
                    "Monitor regularly with hand lens or shake test",
                    "Maintain adequate soil moisture (mites prefer dry conditions)",
                    "Encourage beneficial insects (lady beetles, lacewings)",
                    "Avoid dusty conditions (dust favors mites)",
                    "Remove weeds that harbor mites",
                    "Use reflective mulches to deter mites",
                    "Avoid broad-spectrum insecticides that kill predators"
                ]
            },
            
            "Tomato Target Spot": {
                "cause": "Fungal pathogen Corynespora cassiicola. Thrives in warm (70-85°F), humid conditions. Spreads via wind and rain splash.",
                "symptoms": [
                    "Small brown spots with concentric rings (target pattern)",
                    "Spots enlarge to 1/4 inch diameter",
                    "Lesions may have lighter centers",
                    "Affects leaves, stems, and fruit",
                    "Fruit lesions are dark, sunken, and leathery",
                    "Severe defoliation in humid climates"
                ],
                "solutions": [
                    "Apply fungicides (chlorothalonil, azoxystrobin) at first symptom",
                    "Repeat applications every 7-10 days",
                    "Remove lower infected leaves",
                    "Improve air circulation through staking and pruning",
                    "Reduce leaf wetness duration",
                    "Mulch to prevent soil splash"
                ],
                "prevention": [
                    "Use disease-free seeds and transplants",
                    "Space plants adequately for air circulation",
                    "Stake plants to keep foliage off ground",
                    "Apply mulch to reduce soil splash",
                    "Avoid overhead irrigation",
                    "Remove crop debris after harvest",
                    "Practice crop rotation",
                    "Begin preventive fungicide program in humid climates"
                ]
            },
            
            "Tomato Yellow Leaf Curl Virus": {
                "cause": "Virus transmitted by whitefly (Bemisia tabaci). No cure exists. Warm weather favors whitefly populations. Can devastate unprotected crops.",
                "symptoms": [
                    "Upward curling of leaf margins",
                    "Yellowing of leaf edges",
                    "Severe stunting of plants",
                    "Reduced fruit set or no fruit",
                    "Small, misshapen fruit on infected plants",
                    "Interveinal chlorosis (yellowing between veins)"
                ],
                "solutions": [
                    "Remove and destroy infected plants immediately",
                    "Control whiteflies with systemic insecticides (imidacloprid)",
                    "Use insecticidal soap or horticultural oil",
                    "Apply reflective mulches to deter whiteflies",
                    "Use sticky traps for monitoring and mass trapping",
                    "No chemical cure for virus once infected"
                ],
                "prevention": [
                    "Plant resistant varieties (Ty-1, Ty-2, Ty-3 genes)",
                    "Use insect-proof screens in greenhouses",
                    "Apply systemic insecticides at transplanting",
                    "Use reflective silver mulches",
                    "Remove infected plants promptly to reduce virus source",
                    "Control weeds that harbor whiteflies",
                    "Avoid planting near cucurbits (whitefly hosts)",
                    "Start with virus-free transplants"
                ]
            },
            
            "Tomato Mosaic Virus": {
                "cause": "Virus transmitted mechanically through infected tools, hands, and contaminated seed. Very stable virus that persists in plant debris and on surfaces.",
                "symptoms": [
                    "Mottled light and dark green pattern on leaves",
                    "Distorted, fern-like leaf appearance",
                    "Stunted plant growth",
                    "Reduced fruit set and size",
                    "Uneven fruit ripening and yellow blotches",
                    "Internal browning of fruit"
                ],
                "solutions": [
                    "Remove and destroy infected plants immediately",
                    "Sanitize all tools with 10% bleach solution",
                    "Wash hands thoroughly before handling plants",
                    "Do not smoke or use tobacco products near plants (TMV source)",
                    "No chemical treatment available",
                    "Replace with resistant varieties"
                ],
                "prevention": [
                    "Plant resistant varieties with Tm-2 or Tm-22 genes",
                    "Use certified virus-free seeds and transplants",
                    "Disinfect tools between plants (10% bleach or milk)",
                    "Avoid smoking or tobacco use near tomatoes",
                    "Wash hands with soap before working with plants",
                    "Remove and destroy crop debris",
                    "Control aphids that may spread virus",
                    "Start seeds in sterile potting mix"
                ]
            }
        }


# Create singleton instance
plant_disease_predictor = PlantDiseasePredictor()