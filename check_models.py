import google.generativeai as genai
import os
from dotenv import load_dotenv

# Завантажуємо ключ
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ ПОМИЛКА: Ключ GEMINI_API_KEY не знайдено в .env файлі!")
else:
    print(f"✅ Ключ знайдено: {api_key[:5]}...")
    
    try:
        genai.configure(api_key=api_key)
        print("\n🔍 Запитуємо у Google доступні моделі...")
        
        found = False
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f" - {m.name}")
                found = True
        
        if not found:
            print("\n⚠️ Список порожній. Можливо, ключ невірний або не активований.")
            
    except Exception as e:
        print(f"\n❌ Сталася помилка при підключенні: {e}")
