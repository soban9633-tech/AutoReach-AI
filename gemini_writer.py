import json
import re
import requests

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
GEMINI_FALLBACK_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def test_gemini_connection(api_key):
    """
    Verifies that the provided Gemini API Key is valid and can generate content.
    Returns: (bool success, str message)
    """
    if not api_key or not str(api_key).strip():
        return False, "Gemini API key is required"

    url = f"{GEMINI_API_URL}?key={api_key.strip()}"
    payload = {
        "contents": [{
            "parts": [{"text": "Say 'OK' if you can read this."}]
        }],
        "generationConfig": {
            "maxOutputTokens": 10
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True, "Gemini API Connected Successfully! AI engine is ready."
        else:
            err_data = response.json() if response.text else {}
            err_msg = err_data.get('error', {}).get('message', f"HTTP {response.status_code}")
            return False, f"Gemini Error: {err_msg}"
    except Exception as e:
        return False, f"Connection Failed: {str(e)}"

def generate_personalized_pitch(api_key, contact_data, sender_offer, channel="whatsapp", sender_info=None):
    """
    Uses Google Gemini AI to analyze contact_data from the sheet and generate
    a hyper-personalized cold outreach message tailored to their specific business.
    
    channel: 'whatsapp' or 'email'
    Returns:
      If whatsapp: str (the personalized message body)
      If email: dict {'subject': str, 'body': str}
    """
    if not api_key:
        raise ValueError("Gemini API Key is missing")

    sender_info = sender_info or {
        "name": "Muhammad Soban",
        "company": "RenZoify",
        "whatsapp": "+92 314 3530776",
        "email": "soban9633@gmail.com",
        "website": "https://renzoify.com | https://synvoice.io"
    }

    # Format contact data for prompt
    prospect_details = []
    for k, v in contact_data.items():
        if v and str(v).strip():
            prospect_details.append(f"- {k}: {v}")
    prospect_text = "\n".join(prospect_details)

    if channel == "email":
        system_instruction = f"""You are an elite B2B cold email copywriter.
Analyze this prospect from our Excel sheet and craft a high-converting, personalized cold email.

PROSPECT DETAILS FROM SHEET:
{prospect_text}

SENDER OFFER / PITCH:
{sender_offer}

SENDER INFORMATION:
Name: {sender_info.get('name', 'Muhammad Soban')}
Company: {sender_info.get('company', 'RenZoify')}
WhatsApp: {sender_info.get('whatsapp', '+92 314 3530776')}
Email: {sender_info.get('email', 'soban9633@gmail.com')}
Website: {sender_info.get('website', 'https://renzoify.com')}

RULES:
1. Address the prospect by their exact company/agency name or person name if available.
2. In the first 1-2 sentences, genuinely reference their specific city, services, or website so they know you researched them.
3. Tailor the sender offer specifically to how it directly benefits THEIR business niche.
4. Keep the email concise, polite, and persuasive (under 130 words).
5. End with a low-friction CTA (e.g. offering 1 complimentary sample reel).
6. Return your output strictly as a JSON object with two keys: "subject" and "body". Do NOT wrap in markdown backticks or explanation.
Example JSON:
{{"subject": "Complimentary Sample Video Reel for [Company]", "body": "Dear [Company] Team,\\n\\n..."}}
"""
    else:
        # WhatsApp
        system_instruction = f"""You are an elite B2B WhatsApp outreach copywriter.
Analyze this prospect from our Excel sheet and craft a high-converting, personalized WhatsApp message.

PROSPECT DETAILS FROM SHEET:
{prospect_text}

SENDER OFFER / PITCH:
{sender_offer}

SENDER INFORMATION:
Name: {sender_info.get('name', 'Muhammad Soban')}
Company: {sender_info.get('company', 'RenZoify')}
WhatsApp: {sender_info.get('whatsapp', '+92 314 3530776')}
Email: {sender_info.get('email', 'soban9633@gmail.com')}
Website: {sender_info.get('website', 'https://renzoify.com | https://synvoice.io')}

RULES:
1. Start with a warm greeting addressing their exact Company/Agency Name (e.g. Assalam-o-Alaikum [Company Name] Team, or Hello [Company Name] Team).
2. Specifically mention their city and their exact services/specialties from the sheet in the first 2 sentences.
3. Explain how our video management (30 promotional video ads & short-form reels/month) helps their exact niche get direct client bookings.
4. Propose 1 complimentary sample video for one of their current packages/services.
5. End with our contact details and portfolio links.
6. Use natural, conversational tone with 2-3 tasteful emojis (✈️, 🎬, etc.).
7. Keep it concise and easy to read on mobile (between 80 and 140 words).
8. Return ONLY the final message text to send on WhatsApp. No introductory or explanatory chatter.
"""

    payload = {
        "contents": [{
            "parts": [{"text": system_instruction}]
        }],
        "generationConfig": {
            "temperature": 0.65,
            "maxOutputTokens": 1000
        }
    }

    url = f"{GEMINI_API_URL}?key={api_key.strip()}"
    try:
        response = requests.post(url, json=payload, timeout=25)
        if response.status_code != 200:
            # Try fallback URL
            fallback_url = f"{GEMINI_FALLBACK_URL}?key={api_key.strip()}"
            response = requests.post(fallback_url, json=payload, timeout=25)

        if response.status_code == 200:
            result_json = response.json()
            candidates = result_json.get('candidates', [])
            if candidates:
                text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '').strip()
                if channel == "email":
                    # Try parsing JSON
                    try:
                        clean_text = re.sub(r'^```json\s*', '', text)
                        clean_text = re.sub(r'\s*```$', '', clean_text).strip()
                        parsed = json.loads(clean_text)
                        return parsed
                    except Exception:
                        return {"subject": f"Partnership Offer for {contact_data.get('Agency / Company Name', contact_data.get('Name', 'Your Business'))}", "body": text}
                return text
        else:
            raise RuntimeError(f"Gemini API returned status {response.status_code}: {response.text}")

    except Exception as e:
        raise RuntimeError(f"Gemini Generation Failed: {str(e)}")
