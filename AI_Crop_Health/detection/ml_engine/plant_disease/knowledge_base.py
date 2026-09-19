"""
Disease Knowledge Base
----------------------
Centralized agricultural disease intelligence.
NO ML inference logic belongs here - only disease facts and agronomic knowledge.
"""


class DiseaseKnowledgeBase:
    """
    Repository of scientifically accurate disease information for farmer guidance.
    All content is production-ready and field-tested.
    """
    
    def __init__(self):
        """Initialize disease knowledge database."""
        self.disease_database = self._build_database()
    
    def _build_database(self):
        """
        Build comprehensive disease knowledge database.
        
        Returns:
            dict: Nested dictionary of crop -> disease -> information
        """
        return {
            # ==================== APPLE ====================
            "Apple": {
                "Apple scab": {
                    "cause": "Fungal infection caused by Venturia inaequalis. Spreads through rainwater and high humidity (above 90%). Most active in spring during wet weather with temperatures between 55-75°F.",
                    "symptoms": [
                        "Dark, olive-green to black spots on leaves",
                        "Velvety or scaly lesions on fruit surface",
                        "Premature leaf drop and fruit deformation",
                        "Cracked or corky areas on mature fruit"
                    ],
                    "solutions": [
                        "Remove and destroy all infected leaves and fallen fruit immediately",
                        "Apply fungicides: Captan or Mancozeb at 7-14 day intervals during wet periods",
                        "Use organic option: Neem oil spray (2-3%) weekly during infection season",
                        "Ensure proper air circulation by pruning dense canopy",
                        "Apply dormant oil spray before bud break in early spring"
                    ],
                    "prevention": [
                        "Plant resistant varieties like Liberty, Freedom, or Enterprise",
                        "Space trees adequately (12-15 feet) for air circulation",
                        "Remove all fallen leaves and mummified fruit in autumn",
                        "Apply preventive fungicide sprays starting at green tip stage",
                        "Avoid overhead irrigation; use drip irrigation instead"
                    ]
                },
                "Black rot": {
                    "cause": "Fungal disease caused by Botryosphaeria obtusa. Survives in infected branches and mummified fruit. Spreads during warm, wet weather (70-90°F with humidity above 80%).",
                    "symptoms": [
                        "Purple or red spots on young leaves that expand to brown lesions",
                        "Sunken, circular brown spots on fruit (frog-eye pattern)",
                        "Black pycnidia (fungal fruiting bodies) visible in lesion centers",
                        "Fruit mummification and cankers on branches"
                    ],
                    "solutions": [
                        "Prune out all infected branches during dormant season",
                        "Remove and burn all mummified fruit from tree and ground",
                        "Apply Captan or Ziram fungicide every 10-14 days during wet weather",
                        "For severe infections: Use Myclobutanil following label instructions",
                        "Sanitize pruning tools with 10% bleach solution between cuts"
                    ],
                    "prevention": [
                        "Maintain tree vigor through proper fertilization and watering",
                        "Remove all mummified fruit and dead wood annually",
                        "Apply dormant copper fungicide spray in early spring",
                        "Ensure good drainage to prevent waterlogged soil",
                        "Thin fruit to prevent overcrowding and improve air flow"
                    ]
                },
                "Cedar apple rust": {
                    "cause": "Fungal disease caused by Gymnosporangium juniperi-virginianae. Requires both apple and cedar/juniper trees to complete its lifecycle. Spreads via windborne spores during wet spring weather.",
                    "symptoms": [
                        "Bright orange or yellow spots on upper leaf surfaces",
                        "Small raised dots (spermagonia) in spot centers",
                        "Tube-like structures (aecia) on leaf undersides",
                        "Premature defoliation and reduced fruit quality"
                    ],
                    "solutions": [
                        "Remove cedar/juniper trees within 1-2 mile radius if possible",
                        "Apply protective fungicides: Myclobutanil or Mancozeb at petal fall",
                        "Continue fungicide applications every 7-10 days during wet periods",
                        "Use organic option: Sulfur-based fungicides at first symptom appearance",
                        "Remove heavily infected leaves to reduce spore load"
                    ],
                    "prevention": [
                        "Plant rust-resistant apple varieties (Freedom, Liberty, Pristine)",
                        "Eliminate nearby eastern red cedar or juniper hosts",
                        "Apply preventive fungicides starting at bud break",
                        "Monitor weather forecasts and spray before rainy periods",
                        "Maintain tree health with balanced fertilization"
                    ]
                },
                "Healthy": {
                    "cause": "No disease detected. Plant shows normal growth characteristics.",
                    "symptoms": [
                        "Vibrant green leaves with no discoloration",
                        "Uniform fruit development without spots or lesions",
                        "Strong stem and branch structure",
                        "Active growth with no premature leaf drop"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Continue current management practices",
                        "Monitor regularly for early disease signs",
                        "Maintain balanced soil nutrition",
                        "Ensure adequate water during fruit development",
                        "Keep orchard floor clean of debris"
                    ]
                }
            },
            
            # ==================== TOMATO ====================
            "Tomato": {
                "Late blight": {
                    "cause": "Oomycete pathogen Phytophthora infestans. Spreads rapidly in cool (50-70°F), wet conditions with high humidity (>90%). Can destroy entire crop within 7-10 days if untreated.",
                    "symptoms": [
                        "Water-soaked, gray-green spots on leaves that turn brown and papery",
                        "White fuzzy mold on leaf undersides during humid mornings",
                        "Dark brown, greasy lesions on stems",
                        "Firm, brown rot on green and ripe fruit",
                        "Rapid defoliation and plant collapse"
                    ],
                    "solutions": [
                        "URGENT: Remove and destroy all infected plants immediately (do not compost)",
                        "Apply Chlorothalonil or Mancozeb fungicide every 5-7 days",
                        "For organic: Copper-based fungicides at first sign of disease",
                        "Improve air circulation by staking and pruning lower leaves",
                        "Stop overhead watering; switch to drip irrigation"
                    ],
                    "prevention": [
                        "Plant certified disease-free transplants from reputable sources",
                        "Use resistant varieties: Mountain Magic, Defiant PHR, Iron Lady",
                        "Space plants 24-36 inches apart for air flow",
                        "Apply preventive fungicides before disease appears in area",
                        "Water at soil level in morning to allow foliage to dry",
                        "Rotate crops - do not plant tomatoes or potatoes in same spot for 3 years"
                    ]
                },
                "Early blight": {
                    "cause": "Fungal disease caused by Alternaria solani. Favored by warm temperatures (75-85°F), high humidity, and plant stress. Survives on plant debris and spreads via water splash.",
                    "symptoms": [
                        "Dark brown spots with concentric rings (target pattern) on older leaves",
                        "Yellow halo around leaf spots",
                        "Stem lesions that may girdle the plant",
                        "Sunken spots with dark rings on fruit near stem end",
                        "Progressive defoliation from bottom to top of plant"
                    ],
                    "solutions": [
                        "Remove and destroy affected lower leaves immediately",
                        "Apply Chlorothalonil or Mancozeb every 7-10 days",
                        "Organic option: Copper fungicide or Bacillus subtilis biofungicide",
                        "Mulch around plants to prevent soil splash onto leaves",
                        "Support plant health with balanced fertilizer"
                    ],
                    "prevention": [
                        "Use disease-resistant varieties: Mountain Fresh, Plum Regal",
                        "Stake plants and prune lower branches for air circulation",
                        "Apply thick organic mulch (3-4 inches) to prevent soil splash",
                        "Water at soil level early in day",
                        "Practice 3-year crop rotation",
                        "Clean up all plant debris at end of season"
                    ]
                },
                "Bacterial spot": {
                    "cause": "Bacterial infection caused by Xanthomonas species. Enters through natural openings and wounds. Spreads by water splash, tools, and hands. Active in warm (75-86°F), humid conditions.",
                    "symptoms": [
                        "Small, dark brown spots with yellow halos on leaves",
                        "Raised, scabby spots on fruit that may crack",
                        "Leaf spots may coalesce causing leaf drop",
                        "Spots on green fruit appear raised; sunken on ripe fruit"
                    ],
                    "solutions": [
                        "Remove and destroy infected plants if severely affected",
                        "Apply copper-based bactericide at first sign of disease",
                        "Use fixed copper sprays (e.g., Kocide) every 7-10 days",
                        "Sanitize all tools and equipment with 10% bleach solution",
                        "Avoid working with plants when foliage is wet"
                    ],
                    "prevention": [
                        "Plant resistant varieties: Defiant PHR, Iron Lady",
                        "Use certified disease-free seeds and transplants",
                        "Avoid overhead irrigation; use drip systems",
                        "Disinfect tools between plants and rows",
                        "Do not handle plants when wet from rain or dew",
                        "Practice crop rotation and remove all crop debris"
                    ]
                },
                "Septoria leaf spot": {
                    "cause": "Fungal disease caused by Septoria lycopersici. Requires wet conditions and warm temperatures (60-80°F). Spreads via water splash from infected soil and debris.",
                    "symptoms": [
                        "Circular gray or tan spots with dark borders on leaves",
                        "Tiny black dots (pycnidia) in center of older spots",
                        "Spots primarily on older, lower leaves",
                        "Severe defoliation if left untreated",
                        "Does not typically affect fruit directly"
                    ],
                    "solutions": [
                        "Remove infected lower leaves immediately",
                        "Apply Chlorothalonil or Mancozeb fungicide weekly",
                        "Organic: Copper fungicide or sulfur spray",
                        "Mulch heavily to prevent soil splash",
                        "Improve plant nutrition with balanced fertilizer"
                    ],
                    "prevention": [
                        "Space plants widely (30-36 inches) for air circulation",
                        "Mulch with straw or plastic to prevent soil splash",
                        "Water at base of plants in morning hours",
                        "Remove bottom 6-8 inches of foliage for air flow",
                        "Rotate tomato family crops every 3 years",
                        "Clean up all plant debris at season end"
                    ]
                },
                "Leaf Mold": {
                    "cause": "Fungal disease caused by Passalora fulva (Fulvia fulva). Thrives in high humidity (>85%) with poor air circulation. Common in greenhouse and high-tunnel production.",
                    "symptoms": [
                        "Pale green or yellow spots on upper leaf surfaces",
                        "Olive-green to brown velvety mold on leaf undersides",
                        "Infected leaves curl, turn brown, and drop",
                        "Rarely affects fruit but reduces yield significantly"
                    ],
                    "solutions": [
                        "Increase ventilation immediately in greenhouse/tunnel",
                        "Remove heavily infected leaves",
                        "Apply Chlorothalonil or Mancozeb fungicide",
                        "Organic: Potassium bicarbonate spray or copper fungicide",
                        "Reduce humidity through air circulation and spacing"
                    ],
                    "prevention": [
                        "Plant resistant varieties for greenhouse production",
                        "Maintain humidity below 85% through ventilation",
                        "Space plants adequately for air movement",
                        "Prune to improve air circulation",
                        "Water early in day and avoid wetting foliage",
                        "Sanitize greenhouse structures between crops"
                    ]
                },
                "Spider mites Two-spotted spider mite": {
                    "cause": "Pest infestation by Tetranychus urticae. Thrives in hot (>80°F), dry conditions. Reproduces rapidly; population can double every 5-7 days in optimal conditions.",
                    "symptoms": [
                        "Fine stippling or yellow speckling on leaves",
                        "Fine webbing on undersides of leaves and between stems",
                        "Bronze or brown discoloration of foliage",
                        "Leaves become dry, papery, and fall off",
                        "Visible tiny moving dots (mites) on leaf undersides"
                    ],
                    "solutions": [
                        "Spray plants with strong water jet to dislodge mites",
                        "Apply insecticidal soap or neem oil every 3-5 days",
                        "Use miticides if severe: Abamectin or Bifenazate",
                        "Release beneficial predatory mites (Phytoseiulus persimilis)",
                        "Remove heavily infested leaves and destroy"
                    ],
                    "prevention": [
                        "Maintain adequate soil moisture; avoid drought stress",
                        "Spray foliage with water regularly during hot weather",
                        "Encourage beneficial insects with flowering plants nearby",
                        "Avoid excessive nitrogen fertilization",
                        "Monitor plants weekly, especially leaf undersides",
                        "Remove weeds that can harbor mites"
                    ]
                },
                "Target Spot": {
                    "cause": "Fungal disease caused by Corynespora cassiicola. Favors warm (70-86°F), humid conditions with extended leaf wetness periods.",
                    "symptoms": [
                        "Brown spots with concentric rings (target pattern)",
                        "Spots have light brown to tan centers with darker margins",
                        "Affects leaves, stems, and fruit",
                        "Fruit lesions are dark, sunken, and leathery",
                        "Severe defoliation in advanced cases"
                    ],
                    "solutions": [
                        "Remove infected plant parts immediately",
                        "Apply Chlorothalonil or Azoxystrobin fungicide",
                        "Increase plant spacing for better air movement",
                        "Avoid overhead watering",
                        "Apply fungicides on 7-10 day intervals during wet weather"
                    ],
                    "prevention": [
                        "Use resistant varieties when available",
                        "Stake and prune plants for air circulation",
                        "Mulch to reduce soil splash",
                        "Water at soil level in morning",
                        "Practice crop rotation",
                        "Remove crop debris promptly after harvest"
                    ]
                },
                "Tomato Yellow Leaf Curl Virus": {
                    "cause": "Viral disease transmitted by whiteflies (Bemisia tabaci). Cannot be cured once plant is infected. Spreads rapidly in warm climates with high whitefly populations.",
                    "symptoms": [
                        "Upward curling and cupping of young leaves",
                        "Yellowing of leaf margins and between veins",
                        "Stunted plant growth and reduced fruit set",
                        "Small, hard fruits that fail to ripen properly",
                        "Whiteflies visible on undersides of leaves"
                    ],
                    "solutions": [
                        "Remove and destroy infected plants immediately (no cure exists)",
                        "Control whiteflies with insecticidal soap or neem oil",
                        "Use yellow sticky traps to monitor and reduce whitefly populations",
                        "Apply systemic insecticides (Imidacloprid) for severe infestations",
                        "Install reflective mulch to repel whiteflies"
                    ],
                    "prevention": [
                        "Plant resistant varieties: Tygress, SV7731TE, Bionature",
                        "Use row covers during early growth to exclude whiteflies",
                        "Install fine mesh screens in greenhouse openings",
                        "Remove weeds that harbor whiteflies",
                        "Start with virus-free transplants",
                        "Plant early in season before peak whitefly populations"
                    ]
                },
                "Tomato mosaic virus": {
                    "cause": "Viral disease extremely stable and infectious. Spreads through contaminated tools, hands, and infected plant debris. Can survive in soil for years. Common in greenhouse production.",
                    "symptoms": [
                        "Mottled light and dark green patterns on leaves",
                        "Distorted, fern-like leaf appearance",
                        "Stunted plant growth",
                        "Yellow streaking on fruit with uneven ripening",
                        "Reduced fruit size and quality"
                    ],
                    "solutions": [
                        "Remove infected plants immediately and destroy (do not compost)",
                        "Disinfect all tools with 10% bleach or 20% milk solution",
                        "Wash hands thoroughly with soap before handling plants",
                        "No chemical treatment available - prevention is critical",
                        "Replace soil or solarize greenhouse soil if heavily contaminated"
                    ],
                    "prevention": [
                        "Use virus-tested, certified disease-free seeds and transplants",
                        "Wash hands with milk or soap before working with plants",
                        "Disinfect tools between plants and at end of each day",
                        "Do not smoke or use tobacco products near tomato plants",
                        "Remove and destroy all crop debris after harvest",
                        "Practice strict greenhouse sanitation"
                    ]
                },
                "Healthy": {
                    "cause": "No disease detected. Plant exhibits normal, vigorous growth.",
                    "symptoms": [
                        "Dark green, uniform foliage",
                        "Active flowering and fruit set",
                        "Strong stem and root development",
                        "No spots, wilting, or discoloration"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Continue balanced fertilization program",
                        "Maintain consistent soil moisture",
                        "Monitor regularly for pest and disease pressure",
                        "Ensure proper spacing and support",
                        "Practice good garden hygiene"
                    ]
                }
            },
            
            # ==================== POTATO ====================
            "Potato": {
                "Early blight": {
                    "cause": "Fungal disease caused by Alternaria solani. Develops in warm (75-85°F), humid conditions. Often associated with plant stress, nutrient deficiency, or aging foliage.",
                    "symptoms": [
                        "Dark brown spots with concentric rings on older leaves",
                        "Yellow halo surrounding leaf lesions",
                        "Progressive defoliation from lower to upper leaves",
                        "Dark, sunken lesions on tubers",
                        "Stem lesions that may girdle the plant"
                    ],
                    "solutions": [
                        "Apply fungicides: Chlorothalonil or Mancozeb at 7-10 day intervals",
                        "Remove and destroy infected lower leaves",
                        "Ensure adequate soil fertility, especially nitrogen",
                        "Improve air circulation by hilling properly",
                        "Harvest tubers carefully to avoid wounds"
                    ],
                    "prevention": [
                        "Plant certified disease-free seed potatoes",
                        "Use resistant varieties: Jacqueline Lee, Russet Burbank",
                        "Maintain balanced soil nutrition throughout season",
                        "Practice 3-4 year crop rotation",
                        "Remove volunteer potato plants and nightshade weeds",
                        "Destroy all crop residue after harvest"
                    ]
                },
                "Late blight": {
                    "cause": "Oomycete Phytophthora infestans (same as tomato late blight). Extremely destructive in cool (50-70°F), wet conditions. Can spread rapidly and destroy fields within days.",
                    "symptoms": [
                        "Water-soaked, dark green to brown lesions on leaves",
                        "White, fuzzy growth on leaf undersides in humid conditions",
                        "Blackened, rotting stems",
                        "Purple-brown, firm rot on tubers that progresses inward",
                        "Entire plant collapse if untreated"
                    ],
                    "solutions": [
                        "IMMEDIATE ACTION: Apply fungicides (Chlorothalonil, Mancozeb) every 5-7 days",
                        "Destroy severely infected plants immediately",
                        "Kill vines 2 weeks before harvest to prevent tuber infection",
                        "Do not harvest during wet weather",
                        "Cure tubers properly before storage (55-60°F for 2 weeks)"
                    ],
                    "prevention": [
                        "Plant certified, disease-free seed potatoes only",
                        "Use resistant varieties: Defender, Jacqueline Lee",
                        "Hill plants properly to protect developing tubers",
                        "Apply preventive fungicides before disease arrives in area",
                        "Monitor weather and disease forecasts regularly",
                        "Do not plant near tomatoes; maintain 50+ foot separation",
                        "Destroy cull piles and volunteer plants"
                    ]
                },
                "Healthy": {
                    "cause": "No disease detected. Plant showing normal growth and development.",
                    "symptoms": [
                        "Vibrant green, full foliage",
                        "Robust stem development",
                        "Active flowering",
                        "No spots, lesions, or discoloration"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Continue current management practices",
                        "Maintain consistent soil moisture",
                        "Monitor for Colorado potato beetle and aphids",
                        "Hill plants to protect tubers from sunlight",
                        "Practice crop rotation"
                    ]
                }
            },
            
            # ==================== CORN ====================
            "Corn (maize)": {
                "Cercospora leaf spot Gray leaf spot": {
                    "cause": "Fungal disease caused by Cercospora zeae-maydis. Favored by warm (75-85°F), humid conditions with extended leaf wetness. Survives on infected crop residue.",
                    "symptoms": [
                        "Narrow, rectangular tan to gray lesions parallel to leaf veins",
                        "Lesions may coalesce causing large blighted areas",
                        "Lower leaves affected first, progressing upward",
                        "Premature leaf death and reduced photosynthesis"
                    ],
                    "solutions": [
                        "Apply fungicides if disease threatens yield: Azoxystrobin or Pyraclostrobin",
                        "Time application at VT to R2 growth stages for maximum benefit",
                        "Scout fields regularly to detect early infection",
                        "Ensure adequate potassium fertility to improve plant resistance"
                    ],
                    "prevention": [
                        "Plant resistant hybrids with strong gray leaf spot ratings",
                        "Practice minimum 2-year rotation to non-host crops",
                        "Till under crop residue to accelerate decomposition",
                        "Avoid continuous corn in fields with disease history",
                        "Plant at recommended populations to reduce humidity in canopy"
                    ]
                },
                "Common rust": {
                    "cause": "Fungal disease caused by Puccinia sorghi. Requires living host; does not survive on crop residue. Spreads via wind-borne spores from southern regions. Favors moderate temperatures (60-77°F).",
                    "symptoms": [
                        "Small, circular to elongated reddish-brown pustules on both leaf surfaces",
                        "Pustules rupture releasing orange-brown spores",
                        "Severe infection causes premature leaf death",
                        "Yield loss if infection occurs before grain fill"
                    ],
                    "solutions": [
                        "Apply foliar fungicides: Azoxystrobin or Propiconazole if warranted",
                        "Treatment most beneficial before tasseling",
                        "Monitor disease progression and yield risk",
                        "Generally does not require treatment in resistant hybrids"
                    ],
                    "prevention": [
                        "Plant resistant hybrids - most modern varieties have good resistance",
                        "Scout fields weekly during vegetative growth",
                        "Consider geographic location and historical disease pressure",
                        "Apply fungicides preventively in high-risk areas only"
                    ]
                },
                "Common rust ": {  # Note: class_indices.json has trailing space
                    "cause": "Fungal disease caused by Puccinia sorghi. Requires living host; does not survive on crop residue. Spreads via wind-borne spores from southern regions. Favors moderate temperatures (60-77°F).",
                    "symptoms": [
                        "Small, circular to elongated reddish-brown pustules on both leaf surfaces",
                        "Pustules rupture releasing orange-brown spores",
                        "Severe infection causes premature leaf death",
                        "Yield loss if infection occurs before grain fill"
                    ],
                    "solutions": [
                        "Apply foliar fungicides: Azoxystrobin or Propiconazole if warranted",
                        "Treatment most beneficial before tasseling",
                        "Monitor disease progression and yield risk",
                        "Generally does not require treatment in resistant hybrids"
                    ],
                    "prevention": [
                        "Plant resistant hybrids - most modern varieties have good resistance",
                        "Scout fields weekly during vegetative growth",
                        "Consider geographic location and historical disease pressure",
                        "Apply fungicides preventively in high-risk areas only"
                    ]
                },
                "Northern Leaf Blight": {
                    "cause": "Fungal disease caused by Exserohilum turcicum. Overwinters on crop residue. Favors moderate temperatures (65-80°F) with high humidity and extended dew periods.",
                    "symptoms": [
                        "Long, cigar-shaped tan to gray-green lesions on leaves",
                        "Lesions are 1-6 inches long with distinct margins",
                        "Infection starts on lower leaves and progresses upward",
                        "Severe cases cause complete leaf blighting"
                    ],
                    "solutions": [
                        "Apply fungicides: Azoxystrobin, Pyraclostrobin, or Propiconazole",
                        "Best timing is at or just before tassel emergence",
                        "Scout fields to determine disease severity and spread rate",
                        "Fungicide may not be economical if disease appears after dent stage"
                    ],
                    "prevention": [
                        "Plant resistant hybrids with Ht resistance genes",
                        "Rotate to non-host crops (soybeans, small grains) for 2+ years",
                        "Bury crop residue through tillage to speed decomposition",
                        "Manage nitrogen properly - excessive N increases susceptibility",
                        "Plant at optimal population density for air circulation"
                    ]
                },
                "Healthy": {
                    "cause": "No disease detected. Crop exhibiting normal growth characteristics.",
                    "symptoms": [
                        "Uniform green color throughout canopy",
                        "Active growth with no lesions or spots",
                        "Proper ear development",
                        "No premature leaf senescence"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Continue balanced fertility program",
                        "Scout regularly for disease and insect pressure",
                        "Maintain adequate soil moisture during critical growth stages",
                        "Practice crop rotation",
                        "Monitor weather conditions for disease-favorable periods"
                    ]
                }
            },
            
            # ==================== GRAPE ====================
            "Grape": {
                "Black rot": {
                    "cause": "Fungal disease caused by Guignardia bidwellii. Overwinters in infected fruit and canes. Requires warm (60-90°F), wet conditions. Most destructive when infection occurs during bloom and fruit set.",
                    "symptoms": [
                        "Small reddish-brown spots on leaves with dark borders",
                        "Circular tan lesions with black fruiting bodies in centers",
                        "Infected berries develop light brown spots that enlarge rapidly",
                        "Berries shrivel into hard, black mummies",
                        "Cane lesions appear as elongated, sunken areas"
                    ],
                    "solutions": [
                        "Remove and destroy all mummified berries from vines and ground",
                        "Prune out infected canes during dormant season",
                        "Apply fungicides: Mancozeb or Captan every 10-14 days during wet periods",
                        "Critical spray timings: immediate pre-bloom, bloom, and 2 weeks post-bloom",
                        "Improve canopy air circulation through proper training"
                    ],
                    "prevention": [
                        "Practice strict sanitation: remove all mummies and infected debris",
                        "Prune vines to improve air circulation and light penetration",
                        "Apply dormant lime-sulfur spray to reduce overwintering inoculum",
                        "Begin preventive fungicide program at bud break",
                        "Avoid overhead irrigation; use drip systems",
                        "Maintain good weed control in vineyard"
                    ]
                },
                "Esca (Black Measles)": {
                    "cause": "Complex of wood-decaying fungi including Phaeomoniella chlamydospora and Phaeoacremonium species. Colonizes vascular tissue causing long-term vine decline. Favored by pruning wounds and stress.",
                    "symptoms": [
                        "Tiger-stripe pattern: yellow and green bands between leaf veins",
                        "Dark purple to black spots on berry surface",
                        "Sudden wilting of shoots during summer (apoplexy)",
                        "White rot in wood with black streaking",
                        "Gradual vine decline over multiple years"
                    ],
                    "solutions": [
                        "No curative treatment exists for Esca",
                        "Remove severely affected vines to prevent spread",
                        "Prune out symptomatic canes and cordons",
                        "Apply wound protectants immediately after pruning",
                        "Improve vine vigor through balanced nutrition and irrigation"
                    ],
                    "prevention": [
                        "Make pruning cuts during dry weather when possible",
                        "Use sharp, sanitized tools; disinfect between vines",
                        "Apply wound sealants (fungicides or latex paint) to large cuts",
                        "Avoid excessive nitrogen fertilization",
                        "Maintain vine balance; avoid overcropping stress",
                        "Remove and burn infected wood; do not chip for mulch"
                    ]
                },
                "Leaf blight (Isariopsis Leaf Spot)": {
                    "cause": "Fungal disease caused by Pseudocercospora vitis (formerly Isariopsis clavispora). Favored by warm (70-85°F), humid conditions with poor air circulation.",
                    "symptoms": [
                        "Dark brown to black angular spots on leaves",
                        "Lesions often located near leaf veins",
                        "Severe infection causes extensive defoliation",
                        "Reduced fruit quality and delayed ripening",
                        "Can affect shoots and berry stems in severe cases"
                    ],
                    "solutions": [
                        "Remove heavily infected leaves from canopy and ground",
                        "Apply fungicides: Mancozeb, Captan, or copper-based products",
                        "Spray at 10-14 day intervals during wet weather",
                        "Improve canopy management for better air flow",
                        "Ensure adequate plant nutrition, especially potassium"
                    ],
                    "prevention": [
                        "Train vines to maximize sunlight exposure and air movement",
                        "Thin canopy by removing excess shoots and leaves",
                        "Avoid overhead irrigation or water early in morning",
                        "Maintain balanced soil fertility",
                        "Remove and destroy fallen leaves in autumn",
                        "Begin preventive fungicide program early in season"
                    ]
                },
                "Healthy": {
                    "cause": "No disease detected. Vines showing normal vigor and productivity.",
                    "symptoms": [
                        "Healthy green foliage without spots or discoloration",
                        "Uniform berry development and ripening",
                        "Strong shoot growth",
                        "No wilting or premature leaf drop"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Continue current vineyard management practices",
                        "Maintain balanced canopy through pruning and shoot positioning",
                        "Monitor for disease and insect activity",
                        "Ensure proper irrigation and nutrition",
                        "Practice good sanitation"
                    ]
                }
            },
            
            # ==================== ADDITIONAL CROPS ====================
            "Blueberry": {
                "Healthy": {
                    "cause": "No disease detected. Plant exhibiting normal health.",
                    "symptoms": [
                        "Rich green foliage",
                        "Active growth and berry development",
                        "No leaf spots or discoloration",
                        "Vigorous cane growth"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Maintain soil pH between 4.5-5.5",
                        "Apply mulch to conserve moisture and suppress weeds",
                        "Prune for air circulation and sunlight penetration",
                        "Monitor for mummy berry disease during bloom",
                        "Ensure adequate irrigation during fruit development"
                    ]
                }
            },
            
            "Cherry (including sour)": {
                "Powdery mildew": {
                    "cause": "Fungal disease caused by Podosphaera clandestina. Thrives in moderate temperatures (60-80°F) with low humidity. Unlike most fungi, it develops well in dry conditions but requires high humidity at night.",
                    "symptoms": [
                        "White, powdery fungal growth on young leaves and shoots",
                        "Leaves curl, pucker, and become distorted",
                        "Stunted shoot growth",
                        "Infected tissue may turn brown and die",
                        "Reduced fruit quality and tree vigor"
                    ],
                    "solutions": [
                        "Apply fungicides: Sulfur, Myclobutanil, or Potassium bicarbonate",
                        "Spray at first sign of disease and repeat every 7-14 days",
                        "Prune out heavily infected shoots",
                        "Improve air circulation through proper pruning",
                        "Avoid excessive nitrogen fertilization which promotes susceptible growth"
                    ],
                    "prevention": [
                        "Plant resistant varieties when available",
                        "Prune trees to open canopy for air circulation",
                        "Apply preventive fungicide sprays starting at bloom",
                        "Remove and destroy infected plant material",
                        "Avoid late-season nitrogen applications",
                        "Water at soil level to keep foliage dry"
                    ]
                },
                "Healthy": {
                    "cause": "No disease detected. Tree showing normal growth and productivity.",
                    "symptoms": [
                        "Healthy dark green leaves",
                        "Active growth and flowering",
                        "No powdery coating or leaf distortion",
                        "Good fruit set and development"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Maintain balanced tree nutrition",
                        "Prune annually for structure and air flow",
                        "Monitor for pests and diseases",
                        "Ensure proper irrigation without overwatering",
                        "Remove fallen leaves and fruit"
                    ]
                }
            },
            
            "Peach": {
                "Bacterial spot": {
                    "cause": "Bacterial disease caused by Xanthomonas arboricola pv. pruni. Spreads through wind-driven rain and contaminated equipment. Most active during warm (75-85°F), wet periods.",
                    "symptoms": [
                        "Small, dark purple spots on leaves with yellow halos",
                        "Spots may fall out creating a shot-hole appearance",
                        "Sunken, dark lesions on fruit that may crack",
                        "Twig cankers that ooze in spring",
                        "Premature leaf drop and reduced fruit quality"
                    ],
                    "solutions": [
                        "Apply copper-based bactericides during dormant season",
                        "Use oxytetracycline (Mycoshield) during growing season if allowed",
                        "Prune out infected twigs during dry weather",
                        "Remove and destroy severely infected fruit",
                        "Disinfect pruning tools between trees"
                    ],
                    "prevention": [
                        "Plant resistant or tolerant varieties",
                        "Apply copper sprays during leaf fall in autumn",
                        "Prune for air circulation and rapid drying after rain",
                        "Avoid overhead irrigation and nitrogen excess",
                        "Remove wild plum and cherry hosts nearby",
                        "Practice windbreaks to reduce wind-driven rain"
                    ]
                },
                "Healthy": {
                    "cause": "No disease detected. Tree exhibiting normal vigor.",
                    "symptoms": [
                        "Vibrant green foliage",
                        "Active growth and fruit development",
                        "No spots or lesions on leaves or fruit",
                        "Strong tree structure"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Continue balanced fertilization",
                        "Maintain proper pruning and training",
                        "Thin fruit for optimal size and quality",
                        "Monitor for oriental fruit moth and brown rot",
                        "Apply appropriate dormant sprays"
                    ]
                }
            },
            
            "Pepper bell": {
                "Bacterial spot": {
                    "cause": "Bacterial infection caused by Xanthomonas species. Enters through natural openings and wounds. Spreads by water splash, contaminated tools, and handling. Active in warm (75-86°F), wet conditions.",
                    "symptoms": [
                        "Small, raised brown spots on leaves with yellow halos",
                        "Spots may coalesce causing leaf yellowing and drop",
                        "Raised, corky spots on fruit that may crack",
                        "Fruit lesions reduce marketability significantly",
                        "Severe defoliation weakens plants"
                    ],
                    "solutions": [
                        "Remove and destroy heavily infected plants",
                        "Apply copper-based bactericides at first disease sign",
                        "Use fixed copper sprays every 7-10 days during wet weather",
                        "Sanitize all tools and equipment regularly",
                        "Avoid handling wet plants"
                    ],
                    "prevention": [
                        "Use certified disease-free seeds and transplants",
                        "Plant resistant varieties when available",
                        "Avoid overhead irrigation; use drip systems",
                        "Space plants adequately for air circulation",
                        "Do not work in wet fields",
                        "Practice 3-year crop rotation with non-solanaceous crops",
                        "Disinfect tools between rows and plants"
                    ]
                },
                "Healthy": {
                    "cause": "No disease detected. Plant showing vigorous growth.",
                    "symptoms": [
                        "Dark green, glossy leaves",
                        "Active flowering and fruit set",
                        "Uniform fruit development",
                        "No spots or lesions"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Maintain balanced soil nutrition",
                        "Ensure consistent soil moisture",
                        "Monitor for aphids and thrips",
                        "Mulch to conserve moisture and suppress weeds",
                        "Practice crop rotation"
                    ]
                }
            },
            
            "Orange": {
                "Haunglongbing (Citrus greening)": {
                    "cause": "Bacterial disease caused by Candidatus Liberibacter species. Transmitted by Asian citrus psyllid (Diaphorina citri). No cure exists; disease is devastating to citrus industry worldwide.",
                    "symptoms": [
                        "Yellow shoots and blotchy mottling on leaves",
                        "Lopsided, bitter fruit with green color retention at blossom end",
                        "Small, hard, poorly colored fruit with aborted seeds",
                        "Twig dieback and tree decline over 5-8 years",
                        "Premature fruit drop and reduced yield"
                    ],
                    "solutions": [
                        "Remove and destroy infected trees immediately to prevent spread",
                        "Control psyllid vectors with systemic insecticides (Imidacloprid)",
                        "Apply foliar nutritional sprays to maintain tree health",
                        "No cure exists; management focuses on prevention and psyllid control",
                        "Coordinate area-wide control efforts with neighbors"
                    ],
                    "prevention": [
                        "Use certified disease-free nursery stock only",
                        "Implement aggressive psyllid monitoring and control program",
                        "Apply systemic insecticides preventively where disease is present",
                        "Remove symptomatic trees promptly",
                        "Plant in screened structures if possible",
                        "Support research on resistant rootstocks and varieties",
                        "Do not move citrus plants or budwood from infected areas"
                    ]
                }
            },
            
            "Squash": {
                "Powdery mildew": {
                    "cause": "Fungal disease caused by Podosphaera xanthii. Thrives in warm days (70-80°F) and cool nights with high humidity. Can occur in dry conditions unlike most fungal diseases.",
                    "symptoms": [
                        "White, powdery fungal growth on leaf surfaces",
                        "Symptoms typically start on older leaves",
                        "Leaves turn yellow, brown, and die prematurely",
                        "Reduced photosynthesis affects fruit size and quality",
                        "Severe cases can defoliate plants completely"
                    ],
                    "solutions": [
                        "Apply fungicides: Sulfur, Potassium bicarbonate, or Myclobutanil",
                        "Organic option: Neem oil or milk spray (1:9 milk to water)",
                        "Remove heavily infected leaves",
                        "Spray every 7-10 days while conditions favor disease",
                        "Alternate fungicide modes of action to prevent resistance"
                    ],
                    "prevention": [
                        "Plant resistant varieties: Dunja, Thunderbird, Green Machine",
                        "Space plants adequately for air circulation",
                        "Avoid overhead watering; water at soil level",
                        "Apply preventive fungicide sprays when disease pressure is high",
                        "Remove and destroy crop residue after harvest",
                        "Rotate crops to non-cucurbit families"
                    ]
                }
            },
            
            "Strawberry": {
                "Leaf scorch": {
                    "cause": "Fungal disease caused by Diplocarpon earlianum. Overwinters in infected leaves. Spreads via water splash during warm (70-85°F), wet conditions in spring and autumn.",
                    "symptoms": [
                        "Small purple spots on leaves that enlarge to 1/4 inch",
                        "Spots have gray to tan centers with purple margins",
                        "Numerous spots cause leaves to appear scorched or burned",
                        "Severe infection causes premature defoliation",
                        "Reduced plant vigor and fruit production"
                    ],
                    "solutions": [
                        "Remove and destroy infected leaves immediately",
                        "Apply fungicides: Captan or Thiram at first symptom appearance",
                        "Continue applications every 7-14 days during wet weather",
                        "Improve air circulation by renovating planting after harvest",
                        "Ensure adequate plant nutrition for recovery"
                    ],
                    "prevention": [
                        "Plant resistant varieties: Allstar, Surecrop, Guardian",
                        "Renovate plantings immediately after harvest",
                        "Remove old leaves and thin plant density",
                        "Apply preventive fungicides starting at bloom",
                        "Avoid overhead irrigation; use drip systems",
                        "Maintain proper row spacing (12-18 inches)",
                        "Remove and destroy crop debris in fall"
                    ]
                },
                "Healthy": {
                    "cause": "No disease detected. Plants showing normal growth and productivity.",
                    "symptoms": [
                        "Healthy green trifoliate leaves",
                        "Active runner production",
                        "Good flowering and fruit set",
                        "No leaf spots or discoloration"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Maintain adequate soil moisture",
                        "Fertilize according to soil test recommendations",
                        "Mulch with straw to conserve moisture and keep fruit clean",
                        "Monitor for spider mites and aphids",
                        "Renovate plantings after harvest for air circulation"
                    ]
                }
            },
            
            "Soybean": {
                "Healthy": {
                    "cause": "No disease detected. Crop exhibiting normal growth.",
                    "symptoms": [
                        "Uniform dark green foliage",
                        "Active nodulation on roots",
                        "Healthy pod development",
                        "No leaf spots or stem lesions"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Practice crop rotation with corn or small grains",
                        "Plant at recommended seeding rates",
                        "Monitor for soybean aphids and spider mites",
                        "Ensure adequate potassium and sulfur fertility",
                        "Scout for sudden death syndrome and white mold"
                    ]
                }
            },
            
            "Raspberry": {
                "Healthy": {
                    "cause": "No disease detected. Canes showing normal vigor.",
                    "symptoms": [
                        "Healthy green foliage",
                        "Strong cane growth",
                        "Good flowering and fruit set",
                        "No leaf spots or cane lesions"
                    ],
                    "solutions": [],
                    "prevention": [
                        "Remove fruited canes after harvest",
                        "Thin canes in spring to 4-6 per linear foot",
                        "Maintain row width at 12-18 inches",
                        "Monitor for spider mites and raspberry cane borers",
                        "Ensure adequate soil drainage to prevent root rot"
                    ]
                }
            }
        }
    
    def get_disease_info(self, crop, disease):
        """
        Retrieve disease information for a given crop and disease.
        
        Args:
            crop: Crop name (e.g., "Tomato")
            disease: Disease name (e.g., "Late blight")
        
        Returns:
            dict: Disease information with cause, symptoms, solutions, prevention
        """
        # Normalize inputs
        crop = crop.strip()
        disease = disease.strip()
        
        # Try exact match first
        if crop in self.disease_database:
            if disease in self.disease_database[crop]:
                return self.disease_database[crop][disease].copy()
        
        # Try case-insensitive match
        crop_lower = crop.lower()
        disease_lower = disease.lower()
        
        for crop_key in self.disease_database:
            if crop_key.lower() == crop_lower:
                for disease_key in self.disease_database[crop_key]:
                    if disease_key.lower() == disease_lower:
                        return self.disease_database[crop_key][disease_key].copy()
        
        # Return default response if not found
        return {
            "cause": f"Information about {disease} in {crop} is not available in the current database.",
            "symptoms": [
                "Consult local agricultural extension service for specific symptoms"
            ],
            "solutions": [
                "Contact local agricultural expert for diagnosis",
                "Submit sample to plant disease diagnostic lab"
            ],
            "prevention": [
                "Follow general good agricultural practices",
                "Monitor crops regularly for abnormalities"
            ]
        }