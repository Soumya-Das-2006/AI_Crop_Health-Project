import os
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db.models import F, Q
from PIL import Image
import base64
import io

from core.imaging import compress_image
from .forms import PlantDiseaseUploadForm, InsectUploadForm
from .models import (
    DiagnosisLog,
    QualityRejectionLog,
    AgricultureSuggestion,
    AgricultureAlert,
    UserReaction,
    APIAccessLog,
    DetectionHistory,
    DiagnosisConversation,
    DiagnosisMessage,
    InsectIdentificationLog,
    ChatSession,
    ChatMessage,
)

logger = logging.getLogger(__name__)

# ======================================================
# ML ENGINES IMPORT (WITH ERROR HANDLING)
# ======================================================
try:
    # Import the module-level singleton rather than constructing a second
    # predictor: each instance loads its own copy of the ~20MB H5 model and
    # builds its own TF graph, so constructing one here doubled memory use.
    from .ml_engine.plant_disease.predictor import plant_disease_predictor
    PLANT_DISEASE_AVAILABLE = True
except Exception as e:
    plant_disease_predictor = None
    PLANT_DISEASE_AVAILABLE = False
    logger.error(f"Plant disease model import failed: {type(e).__name__}: {str(e)}")

# Diagnosis routing (crop.health primary, bundled .h5 offline fallback) and the
# single abstention policy both tiers answer to.
from .ml_engine.plant_disease import abstention
from .ml_engine.plant_disease import service as diagnosis_service
from .ml_engine.insect import service as insect_service
from . import ask_ai
from . import answer_format
from . import chatbot_engine

# The quality validator needs only PIL/numpy/cv2, never TensorFlow. Importing
# it directly keeps Stage 1 alive when the H5 model cannot load - which is the
# normal case on a host without TF, and the case where crop.health answers.
try:
    from .ml_engine.plant_disease.image_utils import ImageValidator
    image_validator = ImageValidator()
except Exception as e:
    image_validator = None
    logger.error(f"Image validator import failed: {type(e).__name__}: {str(e)}")

try:
    from .ml_engine.crop.predictor import predict_crop, is_model_available
    if not callable(predict_crop):
        raise ImportError("predict_crop is not callable after import")
    CROP_RECOMMENDATION_AVAILABLE = True
    logger.info("Crop recommendation model imported successfully")
except Exception as e:
    predict_crop = None
    CROP_RECOMMENDATION_AVAILABLE = False
    logger.error(f"Crop recommendation model import failed: {type(e).__name__}: {str(e)}")
    import traceback
    logger.debug(traceback.format_exc())

try:
    from .ml_engine.fertilizer.predictor import (
        predict_fertilizer,
        get_dropdown_data
    )
    FERTILIZER_RECOMMENDATION_AVAILABLE = True
except Exception as e:
    predict_fertilizer = None
    get_dropdown_data = None
    FERTILIZER_RECOMMENDATION_AVAILABLE = False
    logger.error(f"Fertilizer recommendation model import failed: {type(e).__name__}: {str(e)}")

# ======================================================
# GEMINI AI CONFIGURATION (UPDATED FOR NEW PACKAGE)
# ======================================================
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False
    print("Warning: google-genai package not installed")

# Initialize Gemini client
gemini_model = None
gemini_vision_model = None
GEMINI_NEW_API = False

if GEMINI_AVAILABLE and genai:
    try:
        gemini_api_key = getattr(settings, 'GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY'))
        
        if gemini_api_key:
            # Check if using new API structure
            if hasattr(genai, 'Client'):
                # ✅ NEW SDK: Create client instead of configure()
                gemini_client = genai.Client(api_key=gemini_api_key)
                gemini_model = gemini_client
                gemini_vision_model = gemini_client
                GEMINI_NEW_API = True
                print("Gemini AI client initialized successfully (NEW SDK)")
            else:
                # Old API structure
                genai.configure(api_key=gemini_api_key)
                gemini_model = genai.GenerativeModel('gemini-pro')
                gemini_vision_model = genai.GenerativeModel('gemini-pro-vision')
                print("Gemini AI client initialized successfully (OLD SDK)")
        else:
            print("Warning: GEMINI_API_KEY not configured")
    except Exception as e:
        gemini_model = None
        gemini_vision_model = None
        print(f"Warning: Gemini AI initialization failed: {e}")
else:
    print("Warning: Gemini AI not available")

def call_gemini_ai(prompt, use_vision=False):
    """
    Call Gemini API using appropriate SDK pattern
    
    Args:
        prompt: Text prompt or list of content parts
        use_vision: Whether to use vision model (for images)
    
    Returns:
        Response text or None on error
    """
    if not gemini_model:
        return None
    
    try:
        if GEMINI_NEW_API:
            # google-genai exposes generation under client.models, not on the
            # Client itself. Calling it on the client raised AttributeError,
            # which the except below swallowed into a None return - so every
            # Gemini call in this app silently did nothing.
            response = gemini_model.models.generate_content(
                model=getattr(settings, "GEMINI_CHAT_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': 500,
                }
            )
            return response.text.strip()
        else:
            # Old API structure
            if use_vision and gemini_vision_model:
                # For vision requests, prompt should be a list [text, image]
                response = gemini_vision_model.generate_content(prompt)
            else:
                response = gemini_model.generate_content(prompt)
            return response.text.strip()
    
    except Exception as e:
        print(f"Gemini API call failed: {e}")
        return None


# ======================================================
# STATE-BASED CHATBOT SYSTEM PROMPT
# ======================================================
CHATBOT_STATE_SYSTEM = """You are AgriBot, a professional agricultural assistant for Indian farmers.

════════════════════════════════════════
🎯 CORE BEHAVIOR RULES
════════════════════════════════════════
1. NEVER repeat the menu after intent is detected
2. NEVER ask what the user wants after they already told you
3. ALWAYS move forward in the conversation
4. RESPOND in the SAME language as user (Hindi→Hindi, English→English, Bengali→Bengali)
5. Keep responses SHORT (max 150 words) and ACTIONABLE

════════════════════════════════════════
🧭 CONVERSATION FLOW (STRICT SEQUENTIAL)
════════════════════════════════════════

STEP 1: CROP IDENTIFICATION
- If crop unknown: Ask "Which crop are you growing?" in user's language
- If crop known: Move to Step 2

STEP 2: INTENT DETECTION
- Crop is known, intent is not
- Show friendly menu with 4 options:
  • Diseases and treatment
  • Fertilizers
  • Cropping tips
  • Government schemes
- Ask: "What would you like to know?"
- After user selects → IMMEDIATELY move to Step 3

STEP 3: PROVIDE ADVICE (for non-problem intents)
- If intent = CROPPING_TIPS: Give farming tips
- If intent = FERTILIZER: Give fertilizer recommendations
- If intent = SCHEME: Explain government schemes
- DO NOT ask "what would you like to know" again
- DO NOT show menu again
- Just provide the requested information

STEP 4: SYMPTOM COLLECTION (only if intent = PROBLEM)
- Ask: "Where is the problem? Leaves, fruit, or whole plant?"

STEP 5: DIAGNOSIS
- Provide diagnosis with medicine, prevention, safety

════════════════════════════════════════
📋 RESPONSE FORMAT FOR ADVICE
════════════════════════════════════════

When giving CROPPING TIPS, FERTILIZER, or SCHEME advice, use:

Title: [Short title - 3-5 words]

Key Points:
• [Point 1 - specific and actionable]
• [Point 2 - specific and actionable]
• [Point 3 - specific and actionable]

Season/Timing:
• [When to do this]

Important:
• [Safety or critical note]

Follow-up: [Ask ONE relevant question]

════════════════════════════════════════
💊 MEDICINE FORMAT (for disease problems)
════════════════════════════════════════

Problem: [Issue name]

Reason: [Why it happened - 1-2 sentences]

Medicine:
• Main: [Generic name] - [Dosage per liter]
• Alternative: [Generic name] - [Dosage per liter]

Safety: [Warning - waiting period, protective gear]

Prevention:
• [Prevention tip 1]
• [Prevention tip 2]
• [Prevention tip 3]

════════════════════════════════════════
🌐 LANGUAGE RULES
════════════════════════════════════════
- Hindi text: Use Devanagari script (आ, ई, etc.)
- Bengali text: Use Bengali script (আ, ই, etc.)
- English text: Simple farmer-friendly words
- NO mixing languages in same response
- Detect from user's message automatically

════════════════════════════════════════
🚫 ABSOLUTE PROHIBITIONS
════════════════════════════════════════
❌ NEVER repeat "What would you like to know?" after intent is detected
❌ NEVER show the menu options again after user selected one
❌ NEVER ask the same question twice
❌ NEVER ignore the current step from state context
❌ NEVER provide medical guarantees ("100% cure")
❌ NEVER use brand names (only generic chemical names)
❌ NEVER exceed 150 words per response

════════════════════════════════════════
✅ SUCCESS CHECKLIST
════════════════════════════════════════
Your response is CORRECT only if:
✓ It matches the current step exactly
✓ It does NOT repeat questions already answered
✓ It provides specific, actionable information
✓ It is in the correct language
✓ It asks maximum ONE follow-up question
✓ It follows the exact format specified

Remember: You are helping REAL farmers. Be helpful, be safe, be concise!
"""


# ======================================================
# STATE MANAGEMENT FUNCTIONS
# ======================================================

def _get_conversation_state(session):
    """Get current conversation state from session"""
    return session.get('chatbot_state', {
        'crop': None,
        'intent': None,
        'symptoms': None,
        'current_step': 'CROP_IDENTIFICATION',
        'language': None,
        'history': []
    })


def _save_conversation_state(session, state):
    """Save conversation state to session"""
    session['chatbot_state'] = state
    session.modified = True


def _detect_crop_from_message(message):
    """Extract crop name from user message"""
    message_lower = message.lower()

    # Common crops (multilingual)
    crops = {
        # English
        'tomato': 'Tomato', 'potato': 'Potato', 'wheat': 'Wheat',
        'rice': 'Rice', 'maize': 'Maize', 'corn': 'Corn',
        'cotton': 'Cotton', 'soybean': 'Soybean', 'chilli': 'Chilli',
        'onion': 'Onion', 'cabbage': 'Cabbage', 'brinjal': 'Brinjal',
        'eggplant': 'Brinjal', 'capsicum': 'Capsicum', 'pepper': 'Pepper',

        # Hindi
        'टमाटर': 'Tomato', 'आलू': 'Potato', 'गेहूं': 'Wheat',
        'धान': 'Rice', 'मक्का': 'Maize', 'कपास': 'Cotton',
        'सोयाबीन': 'Soybean', 'मिर्च': 'Chilli', 'प्याज': 'Onion',
        'बैंगन': 'Brinjal', 'शिमला मिर्च': 'Capsicum',

        # Bengali
        'টমেটো': 'Tomato', 'আলু': 'Potato', 'গম': 'Wheat',
        'ধান': 'Rice', 'ভুট্টা': 'Maize', 'তুলা': 'Cotton',
        'মরিচ': 'Chilli', 'পেঁয়াজ': 'Onion', 'বেগুন': 'Brinjal',
    }

    for keyword, crop_name in crops.items():
        if keyword in message_lower:
            return crop_name

    return None


def _detect_intent_from_message(message):
    """
    Detect user intent from message
    
    FIXED: Added missing keywords for cropping tips, advice, etc.
    """
    message_lower = message.lower()

    # Problem/Disease keywords (HIGHEST PRIORITY)
    problem_keywords = [
        # English
        'problem', 'issue', 'disease', 'sick', 'dying', 'infected',
        'yellow', 'spot', 'spots', 'curl', 'curling', 'wilting', 'wilt',
        'rot', 'rotting', 'damage', 'damaged', 'pest', 'bug', 'insect',
        'leaf', 'leaves', 'stem', 'fruit', 'root',
        
        # Hindi
        'समस्या', 'बीमारी', 'पीला', 'धब्बा', 'मुड़', 'मुरझा', 'सड़',
        'पत्ता', 'पत्ते', 'पत्तियाँ',
        
        # Bengali
        'সমস্যা', 'রোগ', 'হলুদ', 'দাগ', 'কুঁচকে', 'শুকিয়ে', 'পচে',
        'পাতা', 'পাতার'
    ]
    
    # Fertilizer keywords (MEDIUM-HIGH PRIORITY)
    fertilizer_keywords = [
        # English
        'fertilizer', 'fertiliser', 'nutrient', 'nutrients', 'npk',
        'nitrogen', 'phosphorus', 'potassium', 'manure', 'compost',
        'urea', 'dap',
        
        # Hindi
        'खाद', 'उर्वरक', 'पोषक', 'नाइट्रोजन', 'फॉस्फोरस',
        'पोटैशियम', 'यूरिया',
        
        # Bengali
        'সার', 'পুষ্টি', 'নাইট্রোজেন', 'ফসফরাস', 'পটাসিয়াম'
    ]
    
    # Cropping/Growing/Tips keywords (MEDIUM PRIORITY) - THIS WAS MISSING!
    cropping_keywords = [
        # English
        'crop', 'cropping', 'grow', 'growing', 'plant', 'planting',
        'tip', 'tips', 'advice', 'suggest', 'suggestion', 'suggestions',
        'cultivation', 'farming', 'sowing', 'harvest', 'care',
        'season', 'best time', 'when to', 'how to',
        
        # Hindi
        'उगा', 'लगा', 'खेती', 'सुझाव', 'सलाह', 'बताओ', 'बताइए',
        'कैसे', 'कब', 'क्या', 'समय', 'मौसम',
        
        # Bengali
        'চাষ', 'রোপণ', 'পরামর্শ', 'বলুন', 'কিভাবে', 'কখন', 'কি'
    ]
    
    # Government scheme keywords
    scheme_keywords = [
        # English
        'scheme', 'schemes', 'government', 'subsidy', 'loan',
        'pm-kisan', 'pmfby', 'kcc', 'credit',
        
        # Hindi
        'योजना', 'सरकार', 'सब्सिडी', 'ऋण', 'कर्ज',
        
        # Bengali
        'পরিকল্পনা', 'সরকার', 'ভর্তুকি', 'ঋণ'
    ]
    
    # Check for problem intent (HIGHEST PRIORITY)
    if any(keyword in message_lower for keyword in problem_keywords):
        return 'PROBLEM'
    
    # Check for fertilizer intent
    if any(keyword in message_lower for keyword in fertilizer_keywords):
        return 'FERTILIZER'
    
    # Check for scheme intent
    if any(keyword in message_lower for keyword in scheme_keywords):
        return 'SCHEME'
    
    # Check for cropping/tips/advice intent
    if any(keyword in message_lower for keyword in cropping_keywords):
        return 'CROPPING_TIPS'
    
    return 'UNCLEAR'


def _detect_language(message):
    """Detect message language"""
    # Check for Hindi characters
    if any('\u0900' <= char <= '\u097F' for char in message):
        return 'HINDI'
    
    # Check for Bengali characters
    if any('\u0980' <= char <= '\u09FF' for char in message):
        return 'BENGALI'
    
    # Default to English
    return 'ENGLISH'


def _format_history(history):
    """Format conversation history"""
    if not history:
        return "(No previous messages)"
    
    formatted = []
    for exchange in history:
        formatted.append(f"User: {exchange.get('user', '')}")
        formatted.append(f"Bot: {exchange.get('bot', '')[:100]}...")
    
    return "\n".join(formatted)


def _update_state_from_user_message(user_message, state):
    """
    Update state based on user message BEFORE bot responds
    
    FIXED: Properly handles all intent types including CROPPING_TIPS
    """
    # Detect crop if not known
    if not state['crop']:
        detected_crop = _detect_crop_from_message(user_message)
        if detected_crop:
            state['crop'] = detected_crop
            state['current_step'] = 'INTENT_DETECTION'
            logger.info("Crop detected: %s, moving to INTENT_DETECTION", detected_crop)
    
    # Detect intent if crop known but intent not set
    elif state['crop'] and not state['intent']:
        detected_intent = _detect_intent_from_message(user_message)
        if detected_intent != 'UNCLEAR':
            state['intent'] = detected_intent
            logger.info("Intent detected: %s", detected_intent)
            
            # Update step based on intent
            if detected_intent == 'PROBLEM':
                state['current_step'] = 'SYMPTOM_COLLECTION'
                logger.info("Moving to SYMPTOM_COLLECTION")
            elif detected_intent in ['CROPPING_TIPS', 'FERTILIZER', 'SCHEME']:
                state['current_step'] = 'PROVIDE_ADVICE'
                logger.info("Moving to PROVIDE_ADVICE")
    
    # Collect symptoms if intent is PROBLEM
    elif state['intent'] == 'PROBLEM' and not state['symptoms']:
        # Check if user described symptoms
        symptom_keywords = ['leaf', 'leaves', 'patte', 'পাতা', 'fruit', 'phal', 
                           'ফল', 'whole', 'poora', 'পুরো', 'plant', 'पौधा']
        if any(keyword in user_message.lower() for keyword in symptom_keywords):
            state['symptoms'] = user_message
            state['current_step'] = 'DIAGNOSIS'
            logger.info("Symptoms collected: %s, moving to DIAGNOSIS", user_message[:50])
    
    # Detect language
    if not state['language']:
        state['language'] = _detect_language(user_message)
    
    return state


def _update_state_from_bot_response(bot_response, state):
    """Update state based on bot response"""
    # Add to history
    if 'history' not in state:
        state['history'] = []
    
    # Update state based on bot's response
    if 'Which crop' in bot_response or 'कौन सी फसल' in bot_response or 'কোন ফসল' in bot_response:
        state['current_step'] = 'CROP_IDENTIFICATION'
    elif 'What would you like to know' in bot_response or 'क्या जानना चाहते हैं' in bot_response:
        state['current_step'] = 'INTENT_DETECTION'
    elif 'Where is the problem' in bot_response or 'समस्या कहाँ है' in bot_response:
        state['current_step'] = 'SYMPTOM_COLLECTION'
    elif 'Problem:' in bot_response or 'समस्या:' in bot_response or 'সমস্যা:' in bot_response:
        state['current_step'] = 'DIAGNOSIS'
    
    # Keep only last 10 exchanges
    if len(state['history']) > 10:
        state['history'] = state['history'][-10:]
    
    return state


def _build_state_aware_prompt(user_message, state):
    """
    Build prompt based on current state
    
    FIXED: Handles CROPPING_TIPS, FERTILIZER, SCHEME intents properly
    """
    
    # Add state context to system prompt
    state_context = f"""
CURRENT CONVERSATION STATE:
- Crop Known: {state['crop'] or 'NO'}
- Intent: {state['intent'] or 'UNKNOWN'}
- Symptoms Known: {state['symptoms'] or 'NO'}
- Current Step: {state['current_step']}
- Language: {state['language'] or 'AUTO-DETECT'}

CONVERSATION HISTORY (Last 3 exchanges):
{_format_history(state['history'][-3:])}

CRITICAL INSTRUCTIONS FOR CURRENT STEP "{state['current_step']}":
"""
    
    # Step-specific instructions
    if state['current_step'] == 'CROP_IDENTIFICATION' and not state['crop']:
        state_context += """
- Ask ONLY for crop name in user's language
- Do NOT provide any menu or options
- Keep it simple: "Which crop are you growing?"
"""
    
    elif state['current_step'] == 'INTENT_DETECTION' and state['crop'] and not state['intent']:
        state_context += f"""
- Crop is: {state['crop']}
- Greet and show menu options for {state['crop']}
- Ask: "What would you like to know?"
- Options: Diseases, Fertilizers, Cropping tips, Government schemes
- DO NOT ask about crop again - crop is already known
"""
    
    elif state['current_step'] == 'PROVIDE_ADVICE' and state['intent'] in ['CROPPING_TIPS', 'FERTILIZER', 'SCHEME']:
        state_context += f"""
- Crop: {state['crop']}
- Intent: {state['intent']}
- Provide DETAILED advice for {state['crop']} regarding {state['intent']}
- Use the structured format from system prompt
- DO NOT repeat the menu
- DO NOT ask what they want to know - they already said "{state['intent']}"
- Provide actionable, specific advice
"""
    
    elif state['current_step'] == 'SYMPTOM_COLLECTION' and state['intent'] == 'PROBLEM' and not state['symptoms']:
        state_context += f"""
- Crop: {state['crop']}
- User has a problem/disease
- Ask about problem location: leaves, fruit, whole plant
- Ask in user's language
"""
    
    elif state['current_step'] == 'DIAGNOSIS' and state['crop'] and state['symptoms']:
        state_context += f"""
- Crop: {state['crop']}
- Symptoms: {state['symptoms']}
- Provide COMPLETE diagnosis using the exact format:
  
  Problem: [Name]
  
  Reason: [Why it happened]
  
  Medicine:
  • Main: [Generic name] - [Dosage]
  • Alternative: [Generic name] - [Dosage]
  
  Safety: [Warning]
  
  Prevention:
  • [Tip 1]
  • [Tip 2]
  • [Tip 3]

- DO NOT ask more questions
- DO NOT repeat menu
"""
    
    full_prompt = f"""{CHATBOT_STATE_SYSTEM}

{state_context}

User Message: {user_message}

AgriBot Response (follow instructions exactly):"""
    
    return full_prompt


def _get_state_aware_fallback_response(user_message, state):
    """State-aware fallback response"""
    
    # Step 1: No crop known yet
    if not state['crop']:
        return """Hello! I'm AgriBot, your farming assistant.

नमस्ते! मैं एग्रीबॉट हूं।
হ্যালো! আমি এগ্রিবট।

Which crop are you growing?
Kaun si fasal uga rahe ho?
কোন ফসল চাষ করছেন?"""
    
    # Step 2: Crop known, no intent
    if state['crop'] and not state['intent']:
        return f"""I can help you with {state['crop']}!

मैं {state['crop']} के बारे में मदद कर सकता हूं!

Ask me about:
• Diseases and treatment
• Fertilizers
• Cropping tips
• Government schemes

What would you like to know?"""
    
    # Step 3: Problem intent, no symptoms
    if state['intent'] == 'PROBLEM' and not state['symptoms']:
        return f"""I understand you have a problem with {state['crop']}.

Where is the problem?
समस्या कहाँ है?
সমস্যা কোথায়?

• Leaves (पत्ते / পাতা)
• Fruit (फल / ফল)
• Whole plant (पूरा पौधा / পুরো গাছ)

Please describe what you see."""
    
    # Step 4: Ready for diagnosis
    if state['intent'] == 'PROBLEM' and state['symptoms']:
        return f"""Based on your description of {state['symptoms'].lower()[:50]}...

For {state['crop']}, possible issues:

**Early Blight (शुरुआती झुलसा / প্রারম্ভিক পোড়া):**
- Brown spots with concentric rings
- Yellow leaves falling early

**Treatment:**
• Mancozeb 2g per liter water
• Apply weekly for 3 weeks

**Safety:** Wear gloves and mask

**Prevention:**
• Remove infected leaves
• Improve air circulation
• Avoid overhead watering

Is this helpful?"""
    
    # Default response
    return f"""I can help you with {state['crop']}!

For specific advice, please:
1. Describe your problem clearly
2. Mention symptoms
3. Ask specific questions

मैं मदद कर सकता हूं!
আমি সাহায্য করতে পারি!"""


# ======================================================
# CHATBOT VIEWS
# ======================================================

def chatbot(request):
    """Render the chatbot page"""
    return render(request, "detection/chatbot.html")


def _chatbot_owner_sessions(request):
    if not request.session.session_key:
        request.session.create()
    return ChatSession.objects.filter(
        session_key=request.session.session_key,
        user=request.user if request.user.is_authenticated else None,
    )


def _chatbot_conversation_list(sessions):
    conversations = []
    for chat_session in sessions.prefetch_related("messages"):
        messages = list(chat_session.messages.all())
        first_message = next(
            (message for message in messages
             if message.role == ChatMessage.ROLE_USER and message.content),
            None,
        )
        conversations.append({
            "id": chat_session.pk,
            "title": (
                first_message.content[:60]
                if first_message else "New conversation"
            ),
            "message_count": len(messages),
            "last_active_at": chat_session.last_active_at.isoformat(),
        })
    return conversations


@require_POST
def chatbot_new(request):
    """Create a separate conversation for the current visitor."""
    _chatbot_owner_sessions(request)
    chat_session = ChatSession.objects.create(
        session_key=request.session.session_key,
        user=request.user if request.user.is_authenticated else None,
        user_ip=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({"session_id": chat_session.pk})


@require_POST
def chatbot_reset(request):
    """Delete all conversations belonging to the current visitor."""
    sessions = _chatbot_owner_sessions(request)
    session_key = request.session.session_key
    sessions.delete()
    chat_session = ChatSession.objects.create(
        session_key=session_key,
        user=request.user if request.user.is_authenticated else None,
        user_ip=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({"session_id": chat_session.pk})


@require_POST
def chatbot_api(request):
    """
    Open agriculture chatbot.

    Answers any farming question in the farmer's own language, backed by Groq
    with Gemini as a second provider, and stores every turn in the database.

    This replaced a state machine that interrogated the farmer for a crop and
    an intent before answering anything, and which never actually reached a
    model - it called a method the Gemini client does not have, swallowed the
    AttributeError, and served canned text for every conversation.
    """
    try:
        data = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse(
            {"error": "Invalid JSON",
             "response": "Sorry, I could not read that. Please try again."},
            status=400,
        )

    user_message = (data.get("message") or "").strip()
    if not user_message:
        return JsonResponse(
            {"error": "Message cannot be empty",
             "response": "Please type your farming question."},
            status=400,
        )

    if not request.session.session_key:
        request.session.create()

    sessions = _chatbot_owner_sessions(request)
    conversation_id = data.get("conversation_id")
    if conversation_id is not None:
        if not str(conversation_id).isdigit():
            return JsonResponse({"error": "Invalid conversation"}, status=400)
        chat_session = sessions.filter(pk=conversation_id).first()
        if chat_session is None:
            return JsonResponse({"error": "Conversation not found"}, status=404)
    else:
        chat_session = sessions.first()
        if chat_session is None:
            chat_session = ChatSession.objects.create(
                session_key=request.session.session_key,
                user=request.user if request.user.is_authenticated else None,
                user_ip=request.META.get("REMOTE_ADDR"),
            )

    if chat_session.messages.count() >= chatbot_engine.MAX_MESSAGES_PER_SESSION:
        return JsonResponse(
            {"error": "Conversation limit reached",
             "response": "This conversation is very long. Please start a new one."},
            status=429,
        )

    history = [
        (m.role, m.content)
        for m in chat_session.messages.order_by("created_at", "id")
        if m.content
    ]

    try:
        text, html, meta = chatbot_engine.answer(user_message, history=history)
    except ValueError as exc:
        return JsonResponse({"error": str(exc), "response": str(exc)}, status=400)
    except chatbot_engine.ChatbotUnavailable as exc:
        # Record the failed turn: a run of these is the signal that both
        # providers are down, and dropping it hides that from the admin.
        ChatMessage.objects.create(
            session=chat_session, role=ChatMessage.ROLE_USER, content=user_message
        )
        ChatMessage.objects.create(
            session=chat_session, role=ChatMessage.ROLE_ASSISTANT,
            content="", error=str(exc),
        )
        logger.error("Chatbot unavailable: %s", exc)
        payload = {
            "error": "assistant_unavailable",
            "response": "The assistant is unavailable right now. Please try again shortly.",
        }
        if settings.DEBUG:
            payload["detail"] = str(exc)
        return JsonResponse(payload, status=503)

    ChatMessage.objects.create(
        session=chat_session,
        role=ChatMessage.ROLE_USER,
        content=user_message,
        language=meta["language"],
    )
    ChatMessage.objects.create(
        session=chat_session,
        role=ChatMessage.ROLE_ASSISTANT,
        content=text,
        language=meta["language"],
        provider=meta["provider"],
        model_name=meta["model_name"],
        latency_ms=meta["latency_ms"],
        used_fallback=meta["used_fallback"],
    )

    if chat_session.language != meta["language"]:
        chat_session.language = meta["language"]
    chat_session.save(update_fields=["language", "last_active_at"])

    return JsonResponse({
        "response": text,
        "response_html": html,
        "status": "success",
        "language": meta["language"],
        "provider": meta["provider"],
        "used_fallback": meta["used_fallback"],
        "session_id": chat_session.id,
    })


@require_GET
def chatbot_history(request):
    """Prior turns for this browser session, so a reload keeps the thread."""
    sessions = _chatbot_owner_sessions(request)
    conversation_id = request.GET.get("conversation_id")
    if conversation_id:
        if not conversation_id.isdigit():
            return JsonResponse({"error": "Invalid conversation"}, status=400)
        chat_session = sessions.filter(pk=conversation_id).first()
        if chat_session is None:
            return JsonResponse({"error": "Conversation not found"}, status=404)
    else:
        chat_session = sessions.first()

    if chat_session is None:
        chat_session = ChatSession.objects.create(
            session_key=request.session.session_key,
            user=request.user if request.user.is_authenticated else None,
            user_ip=request.META.get("REMOTE_ADDR"),
        )

    return JsonResponse({
        "session_id": chat_session.id,
        "conversations": _chatbot_conversation_list(sessions),
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "content_html": (
                    answer_format.render_markdown(m.content)
                    if m.role == ChatMessage.ROLE_ASSISTANT else ""
                ),
                "error": bool(m.error),
            }
            for m in chat_session.messages.order_by("created_at", "id")
            if m.content
        ],
    })


# ======================================================
# PLANT DISEASE DIAGNOSIS (CRITICAL SYSTEM)
# ======================================================

def plant_disease_diagnosis(request):
    """
    Production-grade plant disease diagnosis with:
    - Mobile camera capture support
    - Image preview in results
    - Reset functionality (clears session)
    - Complete audit logging
    """
    result = None
    error = None
    image_quality_details = None
    diagnosis_log_id = None

    # ========== HANDLE RESET REQUEST ==========
    if request.method == "POST" and request.POST.get('reset_diagnosis'):
        # Clear session data
        if 'diagnosis_result' in request.session:
            del request.session['diagnosis_result']
        if 'uploaded_image_url' in request.session:
            del request.session['uploaded_image_url']
        request.session.modified = True
        
        # Redirect to clean page
        return redirect('detection:diagnosis')
    
    # ========== LOAD EXISTING RESULT FROM SESSION ==========
    # If user just navigates back, show previous result until explicit reset
    if request.method == "GET" and 'diagnosis_result' in request.session:
        result = request.session['diagnosis_result']
        image_quality_details = request.session.get('image_quality_details')
        
        return render(
            request,
            "detection/diagnosis.html",
            {
                "form": PlantDiseaseUploadForm(),
                "result": result,
                "error": None,
                "image_quality": image_quality_details,
                "ask_ai_presets": ask_ai.preset_choices(),
            }
        )

    if request.method == "POST":
        form = PlantDiseaseUploadForm(request.POST, request.FILES)

        if form.is_valid():
            image = request.FILES["image"]
            
            # Check if plant disease model is available
            if not PLANT_DISEASE_AVAILABLE:
                error = {
                    "message": "Plant disease diagnosis service is currently unavailable.",
                    "recommendations": ["Please try again later or contact support."],
                }
                return render(request, "detection/diagnosis.html", {"form": form, "error": error})
            
            # Get client IP for logging
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                user_ip = x_forwarded_for.split(',')[0]
            else:
                user_ip = request.META.get('REMOTE_ADDR')
            
            # Get session ID
            session_id = request.session.session_key
            if not session_id:
                request.session.create()
                session_id = request.session.session_key

            try:
                # ========== STAGE 1: IMAGE QUALITY VALIDATION ==========
                validation_result = image_validator.validate(image)

                # Get image metadata
                image.seek(0)
                img_pil = Image.open(image)
                img_resolution = f"{img_pil.width}x{img_pil.height}"
                img_size_kb = image.size // 1024
                
                if not validation_result['is_valid']:
                    # Log rejection
                    image.seek(0)
                    QualityRejectionLog.objects.create(
                        uploaded_image=image,
                        rejection_reasons=validation_result.get('details', {}),
                        image_resolution=img_resolution,
                        sharpness_score=validation_result.get('metrics', {}).get('sharpness', 0),
                        brightness_score=validation_result.get('metrics', {}).get('brightness', 0),
                        quality_score=0,
                        user_ip=user_ip
                    )

                    # Return error to user
                    recommendations = image_validator.get_quality_recommendations(validation_result)
                    error_message = validation_result.get('reason', 'Image validation failed')
                    raise ValueError(f"{error_message}", recommendations)

                # ========== STAGE 2: ML INFERENCE ==========
                # Routed: crop.health when configured and reachable, otherwise
                # the bundled 38-class model. Both return the same contract.
                image.seek(0)
                prediction = diagnosis_service.diagnose(image)

                # ========== STAGE 3: GEMINI CROSS-VALIDATION (OPTIONAL) ==========
                used_gemini = False
                gemini_result = None
                
                # Trigger on the verdict, not on a raw number: crop.health
                # probabilities live in a different range to a PlantVillage
                # softmax, so a hardcoded 90-98 window fires for one provider
                # and never for the other. "caution" means borderline in both.
                if gemini_vision_model and prediction.get('diagnosis_status') == abstention.CAUTION:
                    try:
                        image.seek(0)
                        gemini_result = _validate_with_gemini_vision(
                            image,
                            prediction.get('crop', 'Unknown'),
                            prediction.get('disease', 'Unknown'),
                            prediction.get('confidence', 0)
                        )
                        
                        # Apply Gemini's recommendation
                        if gemini_result.get('recommendation') == 'reject':
                            prediction['confidence'] = min(prediction.get('confidence', 0), 50.0)
                            prediction['warning'] = f"Expert validation failed: {', '.join(gemini_result.get('concerns', []))}"
                            prediction['diagnosis_status'] = 'unreliable'
                        elif gemini_result.get('recommendation') == 'uncertain':
                            prediction['confidence'] = min(prediction.get('confidence', 0), gemini_result.get('gemini_confidence', 50))
                        
                        # Gemini is a second opinion, never a promotion: it can
                        # only move a verdict downwards. Re-deriving the status
                        # from raw confidence here is what previously invented
                        # the 'highly_reliable'/'moderate_confidence' labels
                        # that nothing else in the codebase understands.
                        if gemini_result.get('recommendation') == 'reject':
                            prediction['diagnosis_status'] = abstention.UNRELIABLE
                        elif gemini_result.get('recommendation') == 'uncertain':
                            prediction['diagnosis_status'] = abstention.CAUTION

                        # One gate, same as every other path. Prevention advice
                        # stays: it is generic good practice and carries no
                        # risk of sending someone to buy the wrong chemical.
                        if not abstention.may_show_treatment(prediction.get('diagnosis_status')):
                            prediction['solutions'] = []
                            prediction['treatment_withheld'] = True
                        prediction['recommendation'] = abstention.referral_message(
                            prediction.get('diagnosis_status'), prediction.get('crop')
                        )

                        used_gemini = True
                    except Exception as gemini_error:
                        print(f"Gemini validation error: {gemini_error}")
                
                # ========== STAGE 4: SAVE IMAGE & CREATE AUDIT LOG ==========
                image.seek(0)
                # Store a compressed copy. Phone photos arrive at 2-5MB; the
                # model only ever sees 224x224, so the full-resolution original
                # costs disk and page weight for no diagnostic benefit.
                # Re-encoding also strips EXIF, including embedded GPS.
                diagnosis_log = DiagnosisLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    session_id=session_id,
                    user_ip=user_ip,
                    uploaded_image=compress_image(image),
                    image_resolution=img_resolution,
                    image_size_kb=img_size_kb,
                    quality_score=validation_result.get('quality_score', 0),
                    sharpness_score=validation_result.get('details', {}).get('sharpness', {}).get('score'),
                    brightness_score=validation_result.get('details', {}).get('brightness', {}).get('score'),
                    passed_quality_check=True,
                    predicted_crop=prediction.get('crop', 'Unknown'),
                    predicted_disease=prediction.get('disease', 'Unknown'),
                    class_index=prediction.get('class_index', 0),
                    class_label=prediction.get('class_label', 'Unknown'),
                    raw_confidence=prediction.get('raw_confidence', prediction.get('confidence', 0)),
                    calibrated_confidence=prediction.get('confidence', 0),
                    entropy_score=prediction.get('entropy_score'),
                    diagnosis_status=prediction.get('diagnosis_status', 'unreliable'),
                    provider=prediction.get('provider', 'local'),
                    fallback_reason=prediction.get('fallback_reason'),
                    used_gemini_validation=used_gemini,
                    gemini_confidence=gemini_result.get('gemini_confidence') if gemini_result else None,
                    gemini_recommendation=gemini_result.get('recommendation') if gemini_result else None,
                    gemini_concerns=gemini_result.get('concerns') if gemini_result else None,
                    solutions_shown=len(prediction.get('solutions', [])) > 0,
                    warning_message=prediction.get('warning')
                )
                
                diagnosis_log_id = diagnosis_log.id
                
                # Get uploaded image URL for display
                image_url = diagnosis_log.uploaded_image.url if diagnosis_log.uploaded_image else None
                
                # ========== STAGE 5: BUILD USER RESPONSE ==========
                result = {
                    "crop": str(prediction.get("crop", "Unknown")),
                    "disease": str(prediction.get("disease", "Unknown")),
                    "confidence": float(prediction.get("confidence", 0)),
                    "confidence_bar": int(prediction.get("confidence", 0)),
                    "diagnosis_status": str(prediction.get("diagnosis_status", "unreliable")),
                    "cause": str(prediction.get("cause")) if prediction.get("cause") else None,
                    "symptoms": list(prediction.get("symptoms", [])),
                    "solutions": list(prediction.get("solutions", [])),
                    "prevention": list(prediction.get("prevention", [])),
                    "warning": str(prediction.get("warning")) if prediction.get("warning") else None,
                    "ui_color": str(_get_ui_color(prediction.get("diagnosis_status", "unreliable"))),
                    "status_badge": str(_get_status_badge(prediction.get("diagnosis_status", "unreliable"))),
                    "diagnosis_log_id": int(diagnosis_log_id),
                    "used_gemini": bool(used_gemini),
                    "image_url": image_url,

                    # Top-3 is the single largest accuracy gain available here:
                    # for crop.health, the right answer is on screen 66% of the
                    # time against 48% for top-1 alone on in-the-wild photos.
                    # Stage 5 used to drop this, so the UI never saw it.
                    "top_predictions": list(prediction.get("top_predictions", [])),

                    # What the farmer needs to know about trusting this answer.
                    "treatment_withheld": bool(prediction.get("treatment_withheld", False)),
                    "recommendation": str(prediction.get("recommendation", "")),
                    "provider": str(prediction.get("provider", "unknown")),
                    "limited_coverage": bool(prediction.get("limited_coverage", False)),
                    "supported_crops": list(prediction.get("supported_crops", [])),
                    "scientific_name": str(prediction.get("scientific_name", "")),
                }

                image_quality_details = {
                    "score": validation_result.get('quality_score', 0),
                    "status": _get_quality_status(validation_result.get('quality_score', 0)),
                }
                
                # ========== STAGE 6: SAVE TO SESSION FOR PERSISTENCE ==========
                request.session['diagnosis_result'] = result
                request.session['image_quality_details'] = image_quality_details
                request.session.modified = True

            except ValueError as ve:
                # Image quality validation failed
                error_message = str(ve.args[0]) if ve.args else str(ve)

                # Get quality recommendations from validator
                image.seek(0)
                validation_result = plant_disease_predictor.image_validator.validate(image)
                recommendations = plant_disease_predictor.image_validator.get_quality_recommendations(validation_result)

                error = {
                    "message": error_message,
                    "recommendations": recommendations,
                }
                
            except Exception as e:
                # Unexpected errors
                print(f"Diagnosis error: {e}")
                import traceback
                traceback.print_exc()
                
                error = {
                    "message": f"System error: {str(e)}",
                    "recommendations": [
                        "Try uploading a different image",
                        "Ensure image is JPG, JPEG, or PNG",
                        "Contact support if problem persists",
                    ],
                }
        else:
            error = {
                "message": "Invalid image file.",
                "recommendations": ["Upload JPG, JPEG, or PNG (max 10MB)"],
            }
    else:
        form = PlantDiseaseUploadForm()

    return render(
        request,
        "detection/diagnosis.html",
        {
            "form": form,
            "result": result,
            "error": error,
            "image_quality": image_quality_details,
            "ask_ai_presets": ask_ai.preset_choices(),
        }
    )


def _validate_with_gemini_vision(image_file, crop, disease, model_confidence):
    """
    Cross-validate the CNN prediction using Gemini Vision.
    Gemini can only DOWNGRADE confidence, never upgrade.
    
    Returns dict with recommendation and concerns.
    """
    prompt = f"""You are an agricultural pathology expert. Analyze this plant image.

CRITICAL RULES:
1. Focus ONLY on visible symptoms
2. DO NOT diagnose if image quality is poor
3. DO NOT confirm if symptoms are unclear
4. Your job is to VALIDATE or REJECT the AI's prediction

AI Prediction: {crop} - {disease}
AI Confidence: {model_confidence:.1f}%

Your Task:
1. Describe what you see (leaf color, spots, patterns, texture)
2. Do these symptoms match {disease}?
3. What confidence level (0-100%) do you assign?
4. List any contradictions or concerns

Respond ONLY in this JSON format:
{{
  "symptoms_observed": ["symptom1", "symptom2"],
  "matches_prediction": true/false,
  "gemini_confidence": 0-100,
  "concerns": ["concern1", "concern2"],
  "recommendation": "confirm" | "reject" | "uncertain"
}}

If image is too blurry/dark/unclear, respond:
{{
  "recommendation": "image_quality_insufficient",
  "concerns": ["Image too blurry to diagnose reliably"]
}}
"""
    
    # Prepare image
    image_file.seek(0)
    img = Image.open(image_file)
    
    # Call Gemini Vision
    try:
        if GEMINI_NEW_API:
            response = gemini_vision_model.generate_content(
                model="gemini-1.5-flash-8b",
                contents=[prompt, img]
            )
        else:
            response = gemini_vision_model.generate_content([prompt, img])
        
        # Parse JSON response
        response_text = response.text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        result = json.loads(response_text)
        
        # Validate structure
        if 'recommendation' not in result:
            result['recommendation'] = 'uncertain'
        if 'gemini_confidence' not in result:
            result['gemini_confidence'] = 50.0
        if 'concerns' not in result:
            result['concerns'] = []
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"Gemini JSON parse error: {e}")
        return {
            'recommendation': 'uncertain',
            'gemini_confidence': 50.0,
            'concerns': ['Unable to parse Gemini response']
        }
    except Exception as e:
        print(f"Gemini Vision error: {e}")
        return {
            'recommendation': 'uncertain',
            'gemini_confidence': 50.0,
            'concerns': ['Gemini validation failed']
        }


# ======================================================
# UI HELPER FUNCTIONS
# ======================================================

def _get_ui_color(status):
    """
    Map diagnosis status to a Bootstrap colour class.

    Keyed on the abstention vocabulary (reliable/caution/unreliable), which is
    what every provider actually emits. The old highly_reliable /
    moderate_confidence keys are kept as aliases only so historic rows read
    back sensibly - nothing emits them any more, which is why every live badge
    used to fall through to "secondary".
    """
    return {
        abstention.RELIABLE: "success",
        abstention.CAUTION: "warning",
        abstention.UNRELIABLE: "danger",
        abstention.NOT_A_PLANT: "secondary",
        "highly_reliable": "success",
        "moderate_confidence": "warning",
    }.get(status, "secondary")


def _get_status_badge(status):
    """
    Human-readable badge text.

    No percentages: the thresholds differ per provider, so a fixed "≥98%"
    label was wrong for crop.health and unverified for the local model.
    """
    return {
        abstention.RELIABLE: "Confident",
        abstention.CAUTION: "Needs confirmation",
        abstention.UNRELIABLE: "Not confident",
        abstention.NOT_A_PLANT: "No plant detected",
        "highly_reliable": "Confident",
        "moderate_confidence": "Needs confirmation",
    }.get(status, "Unknown")


def _get_quality_status(score):
    """Convert numeric quality score to text status"""
    if score >= 80:
        return "Excellent"
    elif score >= 65:
        return "Good"
    elif score >= 50:
        return "Acceptable"
    return "Poor"


# ======================================================
# CROP RECOMMENDATION VIEW
# ======================================================

def _latest_sensor_prefill(user):
    """
    Return the newest sensor reading for a field this user can see, shaped for
    the crop-recommendation form, or None.

    Audit gap C: the farmer's nodes already measure N, P, K, pH, temperature and
    humidity, but the form still made them type those numbers in by hand.
    iot_sensor is optional, so a missing app must not break this page.
    """
    if not user or not user.is_authenticated:
        return None
    try:
        from iot_sensor.access import visible_fields
        from iot_sensor.models import SensorReading
    except Exception:
        return None

    try:
        reading = (
            SensorReading.objects
            .filter(field__in=visible_fields(user), is_valid=True)
            .select_related('field')
            .order_by('-recorded_at')
            .first()
        )
    except Exception:
        logger.exception('Could not load sensor prefill')
        return None
    if reading is None:
        return None

    values = {
        'N': reading.nitrogen_ppm,
        'P': reading.phosphorus_ppm,
        'K': reading.potassium_ppm,
        'temperature': reading.temperature_c,
        'humidity': reading.humidity_pct,
        'ph': reading.soil_ph,
        'rainfall': reading.rainfall_mm,
    }
    def _tidy(value):
        """
        Render 142.0 as 142 but leave 6.8 as 6.8.

        The N/P/K inputs are step=1 number fields, so a value of "142.0" fails
        browser validation. Done here rather than with the floatformat filter,
        which forces a fixed number of decimals and would round 6.85 to 6.9.
        """
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    present = {k: _tidy(v) for k, v in values.items() if v is not None}
    if not present:
        return None

    return {
        'values': present,
        'missing': sorted(set(values) - set(present)),
        'field_name': reading.field.name,
        'recorded_at': reading.recorded_at,
        'node_count': reading.field.nodes.count(),
    }


def crop_recommendation_view(request):
    result = None
    confidence = None
    suitability = None
    feature_importance = None
    error = None

    if request.method == "POST":
        try:
            logger.debug("Received POST request for crop recommendation.")
            # Extract and validate form input
            fields = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
            data = []
            for field in fields:
                value = request.POST.get(field)
                logger.debug(f"Received {field}: {value}")
                if value is None:
                    logger.error(f"Missing input: {field}")
                    raise ValueError(f"Missing input: {field}")
                try:
                    data.append(float(value))
                except ValueError:
                    logger.error(f"Invalid numeric value for {field}: {value}")
                    raise ValueError(f"Invalid numeric value for {field}: {value}")

            N, P, K, temperature, humidity, ph, rainfall = data

            # Range validation
            if not (0 <= N <= 150):
                logger.error(f"Nitrogen (N) out of range: {N}")
                raise ValueError("Nitrogen (N) must be between 0 and 150")
            if not (0 <= P <= 150):
                logger.error(f"Phosphorus (P) out of range: {P}")
                raise ValueError("Phosphorus (P) must be between 0 and 150")
            if not (0 <= K <= 210):
                logger.error(f"Potassium (K) out of range: {K}")
                raise ValueError("Potassium (K) must be between 0 and 210")
            if not (5 <= temperature <= 45):
                logger.error(f"Temperature out of range: {temperature}")
                raise ValueError("Temperature must be between 5 and 45°C")
            if not (10 <= humidity <= 100):
                logger.error(f"Humidity out of range: {humidity}")
                raise ValueError("Humidity must be between 10 and 100%")
            if not (3.5 <= ph <= 9):
                logger.error(f"Soil pH out of range: {ph}")
                raise ValueError("Soil pH must be between 3.5 and 9")
            if not (20 <= rainfall <= 400):
                logger.error(f"Rainfall out of range: {rainfall}")
                raise ValueError("Rainfall must be between 20 and 400 mm")

            # Check model availability
            if not CROP_RECOMMENDATION_AVAILABLE or not callable(predict_crop):
                logger.error("Crop recommendation model is not available or not callable.")
                raise RuntimeError("Crop recommendation model is not available. Please contact admin.")

            # Prediction
            try:
                logger.debug(f"Calling predict_crop with data: {data}")
                result, confidence, suitability, feature_importance = predict_crop(data)
                logger.info(f"Crop recommendation: {result} ({confidence}%)")
            except Exception as e:
                logger.error(f"Prediction error: {str(e)}")
                raise RuntimeError(f"Prediction failed: {str(e)}")

        except Exception as e:
            error = str(e)
            logger.error(f"Crop recommendation error: {error}")

    # Pre-fill from the farmer's own live sensor readings when we have them, so
    # they are not retyping numbers their hardware already measured.
    sensor_prefill = None
    if request.method != "POST":
        sensor_prefill = _latest_sensor_prefill(request.user)

    return render(
        request,
        "detection/crop.html",
        {
            "result": result,
            "confidence": confidence,
            "suitability": suitability,
            "feature_importance": feature_importance,
            "error": error,
            "sensor_prefill": sensor_prefill,
        }
    )


# ======================================================
# FERTILIZER RECOMMENDATION VIEW
# ======================================================

def fertilizer_recommendation_view(request):
    # FIX: Check if get_dropdown_data is available before calling
    # This prevents TypeError: 'NoneType' object is not callable
    if get_dropdown_data is None:
        logger.warning("get_dropdown_data is None - using fallback data")
        # Fallback data - these are default choices
        soil_types = [
            (0, 'Sandy'), (1, 'Loamy'), (2, 'Clay'), 
            (3, 'Black'), (4, 'Red'), (5, 'Mixed')
        ]
        crop_types = [
            (0, 'Rice'), (1, 'Wheat'), (2, 'Maize'), 
            (3, 'Cotton'), (4, 'Soybean'), (5, 'Sugarcane'),
            (6, 'Tomato'), (7, 'Potato'), (8, 'Onion'), (9, 'Pulses')
        ]
    else:
        try:
            soil_types, crop_types = get_dropdown_data()
        except Exception as e:
            logger.error(f"Error getting dropdown data: {e}")
            # Fallback on any error
            soil_types = [
                (0, 'Sandy'), (1, 'Loamy'), (2, 'Clay'), 
                (3, 'Black'), (4, 'Red'), (5, 'Mixed')
            ]
            crop_types = [
                (0, 'Rice'), (1, 'Wheat'), (2, 'Maize'), 
                (3, 'Cotton'), (4, 'Soybean'), (5, 'Sugarcane'),
                (6, 'Tomato'), (7, 'Potato'), (8, 'Onion'), (9, 'Pulses')
            ]

    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        # FIX: Check if predict_fertilizer is available
        if predict_fertilizer is None:
            return JsonResponse({
                "error": "Fertilizer prediction service is currently unavailable. Please contact admin."
            }, status=503)
        
        try:
            data = [
                float(request.POST["temperature"]),
                float(request.POST["humidity"]),
                float(request.POST["moisture"]),
                int(request.POST["soil"]),
                int(request.POST["crop"]),
                float(request.POST["N"]),
                float(request.POST["K"]),
                float(request.POST["P"]),
            ]

            result = predict_fertilizer(data)

            return JsonResponse(result)

        except Exception as e:
            logger.error(f"Fertilizer prediction error: {e}")
            return JsonResponse({"error": str(e)}, status=400)

    return render(
        request,
        "detection/fertilizer.html",
        {
            "soil_types": soil_types,
            "crop_types": crop_types,
        }
    )


# ======================================================
# SUGGESTION VIEW
# ======================================================

def suggestion(request):
    """Render suggestion page"""
    return render(request, "detection/suggestion.html")


# Alias for backwards compatibility
diagnosis = plant_disease_diagnosis


# ======================================================
# AGRICULTURE ADVISORY BOARD - API VIEWS
# ======================================================

def validate_api_key(request):
    """
    Validate API key from request headers.
    
    Args:
        request: Django request object
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # Get API key from environment
    expected_key = os.environ.get('AGRICULTURE_API_KEY', 
                                  getattr(settings, 'AGRICULTURE_API_KEY', None))
    
    if not expected_key:
        logger.error("AGRICULTURE_API_KEY not configured in environment")
        return False, "API configuration error"
    
    # Get key from request header
    provided_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
    
    if not provided_key:
        return False, "API key missing"
    
    if provided_key != expected_key:
        return False, "Invalid API key"
    
    return True, None


def validate_request_parameters(request):
    """
    Validate required parameters for context filtering.
    
    Args:
        request: Django request object
    
    Returns:
        tuple: (is_valid, params_dict or error_message)
    """
    # Extract parameters
    location = request.GET.get('location', '').strip()
    soil_type = request.GET.get('soil_type', '').strip()
    season = request.GET.get('season', '').strip()
    
    # Validate required fields
    errors = []
    if not location:
        errors.append("location is required")
    if not soil_type:
        errors.append("soil_type is required")
    if not season:
        errors.append("season is required")
    
    if errors:
        return False, {"error": "Missing parameters", "details": errors}
    
    # Validate soil type
    valid_soil_types = ['loamy', 'sandy', 'clay', 'silt', 'peaty', 'chalky', 'mixed']
    if soil_type.lower() not in valid_soil_types:
        return False, {"error": f"Invalid soil_type. Must be one of: {', '.join(valid_soil_types)}"}
    
    # Validate season
    valid_seasons = ['monsoon', 'summer', 'winter', 'spring', 'autumn']
    if season.lower() not in valid_seasons:
        return False, {"error": f"Invalid season. Must be one of: {', '.join(valid_seasons)}"}
    
    return True, {
        'location': location,
        'soil_type': soil_type.lower(),
        'season': season.lower()
    }


def log_api_access(request, is_valid_key, params, http_status, suggestions_count=0, alerts_count=0, error_message=''):
    """
    Log API access for security monitoring.
    
    Args:
        request: Django request object
        is_valid_key: Whether API key was valid
        params: Request parameters dict
        http_status: HTTP status code
        suggestions_count: Number of suggestions returned
        alerts_count: Number of alerts returned
        error_message: Error message if any
    """
    try:
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            user_ip = x_forwarded_for.split(',')[0]
        else:
            user_ip = request.META.get('REMOTE_ADDR')
        
        # Create log entry
        APIAccessLog.objects.create(
            api_key_provided=request.headers.get('X-API-Key', '')[:100],
            is_valid_key=is_valid_key,
            location=params.get('location', '')[:100],
            soil_type=params.get('soil_type', '')[:50],
            season=params.get('season', '')[:50],
            http_status=http_status,
            suggestions_count=suggestions_count,
            alerts_count=alerts_count,
            user_ip=user_ip,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            error_message=error_message
        )
    except Exception as e:
        logger.error(f"Failed to log API access: {e}")


@csrf_exempt
@require_http_methods(["GET"])
def agriculture_advisory_api(request):
    """
    Main API endpoint for agriculture advisory board.
    Returns context-filtered suggestions and alerts.
    
    Required Headers:
        X-API-Key: API authentication key
    
    Required Query Parameters:
        location: User's location (e.g., "Maharashtra", "Punjab")
        soil_type: User's soil type (loamy, sandy, clay, silt, peaty, chalky, mixed)
        season: Current season (monsoon, summer, winter, spring, autumn)
    
    Returns:
        JSON with alerts and suggestions
    """
    
    # Step 1: Validate API key
    is_valid_key, error = validate_api_key(request)
    if not is_valid_key:
        log_api_access(request, False, {}, 403, error_message=error)
        return JsonResponse({
            'success': False,
            'error': error
        }, status=403)
    
    # Step 2: Validate parameters
    params_valid, params_or_error = validate_request_parameters(request)
    if not params_valid:
        log_api_access(request, True, {}, 400, error_message=str(params_or_error))
        return JsonResponse({
            'success': False,
            **params_or_error
        }, status=400)
    
    params = params_or_error
    
    # Step 3: Check cache
    cache_key = f"advisory_{params['location']}_{params['soil_type']}_{params['season']}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        log_api_access(request, True, params, 200, 
                      cached_data['suggestions_count'], 
                      cached_data['alerts_count'])
        return JsonResponse(cached_data)
    
    # Step 4: Get filtered alerts
    alerts = AgricultureAlert.get_filtered_alerts(
        location=params['location'],
        soil_type=params['soil_type'],
        season=params['season']
    )
    
    # Step 5: Get filtered suggestions
    suggestions = AgricultureSuggestion.get_filtered_suggestions(
        location=params['location'],
        soil_type=params['soil_type'],
        season=params['season']
    )
    
    # Step 6: Format response
    response_data = {
        'success': True,
        'context': params,
        'timestamp': timezone.now().isoformat(),
        'alerts': [
            {
                'id': alert.id,
                'type': alert.alert_type,
                'severity': alert.severity,
                'title': alert.title,
                'message': alert.message,
                'affected_crops': alert.get_affected_crops_list(),
                'valid_until': alert.valid_until.isoformat(),
                'is_pinned': alert.is_pinned,
                'color': alert.severity_color,
                'icon': alert.severity_icon,
            }
            for alert in alerts[:10]  # Limit to 10 alerts
        ],
        'suggestions': [
            {
                'id': suggestion.id,
                'category': suggestion.category,
                'title': suggestion.title,
                'description': suggestion.description,
                'priority': suggestion.priority,
            }
            for suggestion in suggestions[:20]  # Limit to 20 suggestions
        ],
        'alerts_count': alerts.count(),
        'suggestions_count': suggestions.count(),
    }
    
    # Add fallback message if no results
    if not alerts and not suggestions:
        response_data['fallback_message'] = "No region-specific advisories found. Showing general recommendations."
        # Get global suggestions
        global_suggestions = AgricultureSuggestion.objects.filter(
            is_global=True, 
            is_active=True,
            publish_date__lte=timezone.now()
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gt=timezone.now())
        )[:5]
        
        if global_suggestions:
            response_data['global_suggestions'] = [
                {
                    'id': suggestion.id,
                    'category': suggestion.category,
                    'title': suggestion.title,
                    'description': suggestion.description[:100] + '...',
                }
                for suggestion in global_suggestions
            ]
    
    # Step 7: Cache response (5 minutes)
    cache.set(cache_key, response_data, 300)
    
    # Step 8: Log access
    log_api_access(request, True, params, 200, 
                  len(response_data.get('suggestions', [])), 
                  len(response_data.get('alerts', [])))
    
    return JsonResponse(response_data)


@csrf_exempt
@require_http_methods(["POST"])
def record_reaction_api(request):
    """
    Record user reaction to suggestion or alert.
    
    Required Headers:
        X-API-Key: API authentication key
    
    Required POST Parameters:
        content_type: "suggestion" or "alert"
        content_id: ID of the suggestion or alert
        reaction: "helpful", "not_helpful", or "viewed"
        location: User's location
        soil_type: User's soil type
        season: Current season
    
    Returns:
        JSON success/error response
    """
    
    # Validate API key
    is_valid_key, error = validate_api_key(request)
    if not is_valid_key:
        return JsonResponse({
            'success': False,
            'error': error
        }, status=403)
    
    # Get parameters
    content_type = request.POST.get('content_type', '').strip().lower()
    content_id = request.POST.get('content_id', '').strip()
    reaction = request.POST.get('reaction', '').strip().lower()
    location = request.POST.get('location', '').strip()
    soil_type = request.POST.get('soil_type', '').strip().lower()
    season = request.POST.get('season', '').strip().lower()
    
    # Validate required fields
    if not all([content_type, content_id, reaction, location, soil_type, season]):
        return JsonResponse({
            'success': False,
            'error': 'Missing required parameters'
        }, status=400)
    
    # Validate content type
    if content_type not in ['suggestion', 'alert']:
        return JsonResponse({
            'success': False,
            'error': 'content_type must be "suggestion" or "alert"'
        }, status=400)
    
    # Validate reaction
    if reaction not in ['helpful', 'not_helpful', 'viewed']:
        return JsonResponse({
            'success': False,
            'error': 'reaction must be "helpful", "not_helpful", or "viewed"'
        }, status=400)
    
    try:
        content_id = int(content_id)
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'content_id must be an integer'
        }, status=400)
    
    # Get session ID
    session_id = request.session.session_key
    if not session_id:
        request.session.create()
        session_id = request.session.session_key
    
    # Get client IP
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        user_ip = x_forwarded_for.split(',')[0]
    else:
        user_ip = request.META.get('REMOTE_ADDR')
    
    try:
        # Get content object
        if content_type == 'suggestion':
            try:
                content_obj = AgricultureSuggestion.objects.get(id=content_id, is_active=True)
            except AgricultureSuggestion.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Suggestion not found'
                }, status=404)
            
            # Create or update reaction
            user_reaction, created = UserReaction.objects.get_or_create(
                suggestion=content_obj,
                session_id=session_id,
                reaction_type=reaction,
                defaults={
                    'user_ip': user_ip,
                    'user_location': location,
                    'user_soil_type': soil_type,
                    'user_season': season,
                }
            )
            
            # Update suggestion counters
            if reaction == 'helpful':
                AgricultureSuggestion.objects.filter(id=content_id).update(
                    helpful_count=F('helpful_count') + 1,
                    view_count=F('view_count') + 1 if created else F('view_count')
                )
            elif reaction == 'not_helpful':
                AgricultureSuggestion.objects.filter(id=content_id).update(
                    not_helpful_count=F('not_helpful_count') + 1,
                    view_count=F('view_count') + 1 if created else F('view_count')
                )
            elif reaction == 'viewed' and created:
                AgricultureSuggestion.objects.filter(id=content_id).update(
                    view_count=F('view_count') + 1
                )
        
        else:  # alert
            try:
                content_obj = AgricultureAlert.objects.get(id=content_id, is_active=True)
            except AgricultureAlert.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Alert not found'
                }, status=404)
            
            # Create or update reaction
            user_reaction, created = UserReaction.objects.get_or_create(
                alert=content_obj,
                session_id=session_id,
                reaction_type=reaction,
                defaults={
                    'user_ip': user_ip,
                    'user_location': location,
                    'user_soil_type': soil_type,
                    'user_season': season,
                }
            )
            
            # Update alert counters
            if reaction == 'viewed' and created:
                AgricultureAlert.objects.filter(id=content_id).update(
                    view_count=F('view_count') + 1
                )
        
        return JsonResponse({
            'success': True,
            'message': 'Reaction recorded',
            'is_new': created
        })
    
    except Exception as e:
        logger.error(f"Error recording reaction: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to record reaction'
        }, status=500)


def agriculture_advisory_view(request):
    """
    Web page view for Agriculture Advisory Board.
    Renders the suggestion.html template with context-filtered content.
    
    This is NOT an API - it's the user-facing web page.
    """
    
    # Get context from query parameters or form submission
    location = request.GET.get('location', '').strip()
    soil_type = request.GET.get('soil_type', '').strip().lower()
    season = request.GET.get('season', '').strip().lower()
    
    # Initialize empty results
    alerts = []
    suggestions = []
    show_results = False
    error_message = None
    
    # If parameters provided, get filtered results
    if location and soil_type and season:
        # Validate parameters
        valid_soil_types = ['loamy', 'sandy', 'clay', 'silt', 'peaty', 'chalky', 'mixed']
        valid_seasons = ['monsoon', 'summer', 'winter', 'spring', 'autumn']
        
        if soil_type not in valid_soil_types:
            error_message = f"Invalid soil type. Please select from: {', '.join(valid_soil_types)}"
        elif season not in valid_seasons:
            error_message = f"Invalid season. Please select from: {', '.join(valid_seasons)}"
        else:
            # Get filtered content
            alerts = AgricultureAlert.get_filtered_alerts(location, soil_type, season)
            suggestions = AgricultureSuggestion.get_filtered_suggestions(location, soil_type, season)
            show_results = True
            
            # If no results, show fallback message
            if not alerts and not suggestions:
                error_message = "No region-specific advisories found. Showing general recommendations."
                # Get global suggestions
                suggestions = AgricultureSuggestion.objects.filter(
                    is_global=True, 
                    is_active=True,
                    publish_date__lte=timezone.now()
                ).filter(
                    Q(expiry_date__isnull=True) | Q(expiry_date__gt=timezone.now())
                )[:10]
    
    # Prepare context for template
    context = {
        'location': location,
        'soil_type': soil_type,
        'season': season,
        'alerts': alerts[:10],  # Limit display
        'suggestions': suggestions[:20],  # Limit display
        'show_results': show_results,
        'error_message': error_message,
        'soil_type_choices': [
            ('loamy', 'Loamy'),
            ('sandy', 'Sandy'),
            ('clay', 'Clay'),
            ('silt', 'Silt'),
            ('peaty', 'Peaty'),
            ('chalky', 'Chalky'),
            ('mixed', 'Mixed'),
        ],
        'season_choices': [
            ('monsoon', 'Monsoon'),
            ('summer', 'Summer'),
            ('winter', 'Winter'),
            ('spring', 'Spring'),
            ('autumn', 'Autumn'),
        ],
    }
    
    return render(request, 'detection/suggestion.html', context)


def invalidate_advisory_cache():
    """
    Clear all advisory caches.
    Call this when admin updates suggestions or alerts.
    """
    # Clear all advisory-related cache keys
    cache.delete_pattern("advisory_*")
    logger.info("Advisory cache cleared")


# ======================================================
# PRIVACY-FIRST DETECTION HISTORY
# ======================================================

@login_required
def save_detection_history(request, log_id):
    if request.method == "POST":
        log = get_object_or_404(DiagnosisLog, id=log_id)
        # Check if already saved
        history, created = DetectionHistory.objects.get_or_create(
            user=request.user,
            diagnosis_log=log,
            defaults={'notes': request.POST.get('notes', '')}
        )
        if created:
            messages.success(request, "Detection saved to your history.")
        else:
            messages.info(request, "This detection is already in your history.")
        return redirect('detection:my_detection_history')
    return redirect('detection:diagnosis')

@login_required
def my_detection_history(request):
    histories = DetectionHistory.objects.filter(user=request.user).select_related('diagnosis_log')
    return render(request, 'detection/history.html', {'histories': histories})

@login_required
def delete_detection_history(request, history_id):
    if request.method == "POST":
        history = get_object_or_404(DetectionHistory, id=history_id, user=request.user)
        history.delete()
        messages.success(request, "Detection removed from your history.")
    return redirect('detection:my_detection_history')

# ======================================================
# ASK AI - follow-up questions about a diagnosed photo
# ======================================================

def _conversation_owner_matches(conversation, request):
    """
    A thread belongs to the signed-in user, or to the anonymous session that
    created it. Without this check any visitor could read another farmer's
    photo and conversation by guessing a diagnosis id.
    """
    if conversation.user_id:
        return request.user.is_authenticated and conversation.user_id == request.user.id
    return bool(conversation.session_id) and conversation.session_id == request.session.session_key


@require_POST
def ask_ai_api(request):
    """
    Ask one question about a diagnosed image.

    POST JSON: {"diagnosis_log_id": int, "preset": "treatment"} or
               {"diagnosis_log_id": int, "question": "free text"}

    Returns the stored answer plus whether treatment advice was gated, so the
    UI can show the farmer why no chemical was named.
    """
    try:
        payload = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    log_id = payload.get("diagnosis_log_id")
    insect_log_id = payload.get("insect_log_id")

    if not log_id and not insect_log_id:
        return JsonResponse(
            {"error": "diagnosis_log_id or insect_log_id is required"}, status=400
        )
    if log_id and insect_log_id:
        return JsonResponse(
            {"error": "Pass only one of diagnosis_log_id or insect_log_id"}, status=400
        )

    diagnosis_log = None
    insect_log = None
    if insect_log_id:
        try:
            insect_log = InsectIdentificationLog.objects.get(pk=insect_log_id)
        except InsectIdentificationLog.DoesNotExist:
            return JsonResponse({"error": "Insect identification not found"}, status=404)
        kind = "insect"
        subject_status = insect_log.identification_status
    else:
        try:
            diagnosis_log = DiagnosisLog.objects.get(pk=log_id)
        except DiagnosisLog.DoesNotExist:
            return JsonResponse({"error": "Diagnosis not found"}, status=404)
        kind = "plant"
        subject_status = diagnosis_log.diagnosis_status

    try:
        question_text, preset_id = ask_ai.resolve_question(
            payload.get("preset"), payload.get("question"), kind=kind
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if not request.session.session_key:
        request.session.create()

    # One thread per diagnosis per viewer, so follow-ups keep their context.
    conversation, _ = DiagnosisConversation.objects.get_or_create(
        diagnosis_log=diagnosis_log,
        insect_log=insect_log,
        user=request.user if request.user.is_authenticated else None,
        session_id=None if request.user.is_authenticated else request.session.session_key,
        defaults={"language": getattr(settings, "CROP_HEALTH_LANGUAGE", "en")},
    )

    if not _conversation_owner_matches(conversation, request):
        return JsonResponse({"error": "Not your diagnosis"}, status=403)

    if conversation.messages.count() >= ask_ai.MAX_MESSAGES_PER_CONVERSATION:
        return JsonResponse(
            {"error": "This conversation has reached its limit. Start a new diagnosis."},
            status=429,
        )

    DiagnosisMessage.objects.create(
        conversation=conversation,
        role=DiagnosisMessage.ROLE_USER,
        content=question_text,
        preset=preset_id,
    )

    try:
        answer, answer_html, meta = ask_ai.ask(conversation, question_text)
    except ask_ai.AskAIUnavailable as exc:
        # Persist the failure: a thread of unanswered questions is a signal,
        # and silently dropping it hides outages from the admin panel.
        DiagnosisMessage.objects.create(
            conversation=conversation,
            role=DiagnosisMessage.ROLE_ASSISTANT,
            content="",
            preset=preset_id,
            error=str(exc),
            treatment_gated=not abstention.may_show_treatment(subject_status),
        )
        if isinstance(exc, ask_ai.AskAINotConfigured):
            # Not a transient outage - no request will ever succeed until the
            # server is fixed, so say something different and log it loudly.
            logger.error("Ask AI is NOT CONFIGURED: %s", exc)
            message = "The assistant is not set up on this server yet."
        else:
            logger.error(
                "Ask AI unavailable for %s %s: %s", kind, log_id or insect_log_id, exc
            )
            message = "The assistant is unavailable right now. Please try again."

        payload = {"error": message}
        # In development, hand the actual reason back so it is visible in the
        # page instead of only in a terminal the developer may not be watching.
        if settings.DEBUG:
            payload["detail"] = str(exc)
        return JsonResponse(payload, status=503)

    message = DiagnosisMessage.objects.create(
        conversation=conversation,
        role=DiagnosisMessage.ROLE_ASSISTANT,
        content=answer,
        preset=preset_id,
        model_name=meta["model_name"],
        latency_ms=meta["latency_ms"],
        treatment_gated=meta["treatment_gated"],
    )

    return JsonResponse({
        # Markdown is the stored source of truth; HTML is what the page shows.
        "answer": answer,
        "answer_html": answer_html,
        "message_id": message.id,
        "conversation_id": conversation.id,
        "treatment_gated": meta["treatment_gated"],
        "had_image": meta["had_image"],
        "question": question_text,
        "preset": preset_id,
    })


@require_GET
def ask_ai_history(request, log_id, kind="plant"):
    """Prior turns for a subject, so a reloaded page keeps the thread."""
    lookup = {}
    if kind == "insect":
        if not InsectIdentificationLog.objects.filter(pk=log_id).exists():
            return JsonResponse({"error": "Insect identification not found"}, status=404)
        lookup["insect_log_id"] = log_id
    else:
        if not DiagnosisLog.objects.filter(pk=log_id).exists():
            return JsonResponse({"error": "Diagnosis not found"}, status=404)
        lookup["diagnosis_log_id"] = log_id

    conversation = DiagnosisConversation.objects.filter(
        user=request.user if request.user.is_authenticated else None,
        session_id=None if request.user.is_authenticated else request.session.session_key,
        **lookup
    ).first()

    if conversation is None:
        return JsonResponse({"messages": []})

    if not _conversation_owner_matches(conversation, request):
        return JsonResponse({"error": "Not your diagnosis"}, status=403)

    return JsonResponse({
        "conversation_id": conversation.id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                # Rendered on read rather than stored, so the markdown in the
                # database stays the single source of truth.
                "content_html": (
                    answer_format.render_markdown(m.content)
                    if m.role == DiagnosisMessage.ROLE_ASSISTANT else ""
                ),
                "preset": m.preset,
                "treatment_gated": m.treatment_gated,
                "error": bool(m.error),
            }
            for m in conversation.messages.order_by("created_at", "id")
        ],
    })


# ======================================================
# INSECT IDENTIFICATION
# ======================================================

def insect_identification(request):
    """
    Identify an insect from a photo.

    Deliberately does not produce treatment advice. insect.id names the taxon;
    whether that taxon is a pest in this field is a separate judgement the API
    does not reliably make (it reports danger-to-humans for about 3.5% of
    taxa), so the page says what the insect is and routes the decision to a
    human. Many field insects are predators and pollinators, and spraying one
    because an app named it makes the season worse, not better.
    """
    result = None
    error = None

    if request.method == "POST":
        form = InsectUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.cleaned_data['image']

            if image_validator is not None:
                validation_result = image_validator.validate(image)
                if not validation_result.get('is_valid', True):
                    error = validation_result.get('reason', 'Image validation failed')
                    return render(request, "detection/insect.html", {
                        "form": form, "result": None, "error": error,
                        "ask_ai_presets": ask_ai.preset_choices(kind="insect"),
                    })

            try:
                image.seek(0)
                img_pil = Image.open(image)
                img_resolution = f"{img_pil.width}x{img_pil.height}"
            except Exception:
                img_resolution = ""

            try:
                image.seek(0)
                result = insect_service.identify(image)
            except insect_service.InsectServiceUnavailable as exc:
                logger.warning("Insect identification unavailable: %s", exc)
                error = str(exc)
            except Exception as exc:
                logger.error("Insect identification failed: %s", exc)
                error = "Could not identify this photo. Please try again."

            if result is not None:
                if not request.session.session_key:
                    request.session.create()

                image.seek(0)
                top = (result.get("top_predictions") or [{}])[0]
                log = InsectIdentificationLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    session_id=request.session.session_key,
                    user_ip=request.META.get('REMOTE_ADDR'),
                    uploaded_image=compress_image(image),
                    image_resolution=img_resolution,
                    image_size_kb=(image.size // 1024) if getattr(image, 'size', None) else None,
                    common_name=result.get("name", "")[:200],
                    scientific_name=result.get("scientific_name", "")[:200],
                    taxon_id=str(top.get("id") or "")[:100],
                    confidence=result.get("confidence", 0.0),
                    top_predictions=result.get("top_predictions"),
                    margin=result.get("margin"),
                    entropy_score=result.get("entropy_score"),
                    identification_status=result.get("identification_status", "unreliable"),
                    pest_status=result.get("pest_status", "unknown"),
                    provider=result.get("provider", "insect.id"),
                    model_version=result.get("model_version", "")[:60],
                )
                result["log_id"] = log.id
                result["image_url"] = log.uploaded_image.url if log.uploaded_image else None
    else:
        form = InsectUploadForm()

    return render(request, "detection/insect.html", {
        "form": form,
        "result": result,
        "error": error,
        "ask_ai_presets": ask_ai.preset_choices(kind="insect"),
    })
