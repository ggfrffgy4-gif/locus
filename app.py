import json
import urllib.request
import urllib.parse
import urllib.error
import os
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ==========================================
# ВСТАВЬТЕ СЮДА ВАШ КЛЮЧ GEMINI:
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# ==========================================

# --- ПОЛУЧЕНИЕ ДО 8-10 ФОТО ИЗ СТАТЬИ И КАТЕГОРИИ ВИКИПЕДИИ ---
def get_wikipedia_campus_photos(uni_name):
    headers = {"User-Agent": "LocusCampusAI/3.0 (student project)"}
    
    # 1. Поиск статьи вуза
    search_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": f"{uni_name} university",
        "format": "json",
        "utf8": 1
    })

    page_title = uni_name
    try:
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get("query", {}).get("search", [])
            if results:
                page_title = results[0]["title"]
    except Exception as e:
        print(f"Ошибка поиска страницы: {e}")

    # 2. Получение списка картинок статьи (берем с запасом)
    images_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query",
        "titles": page_title,
        "prop": "images",
        "imlimit": 30,
        "format": "json",
        "utf8": 1
    })

    found_photos = []
    try:
        req = urllib.request.Request(images_url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            pages = data.get("query", {}).get("pages", {})
            image_titles = []
            for _, p in pages.items():
                for img in p.get("images", []):
                    t = img.get("title", "")
                    lower_t = t.lower()
                    if any(lower_t.endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
                        if not any(bad in lower_t for bad in ["logo", "seal", "coat of arms", "flag", "icon", "stub", "symbol", "signature"]):
                            image_titles.append(t)

            categories = ["Главный корпус", "Архитектура", "Студенческая жизнь", "Библиотека", "Инфраструктура", "Кампус", "Лаборатории", "Аудитории"]
            
            # Загружаем метаданные до 8 лучших фотографий
            for idx, img_t in enumerate(image_titles[:10]):
                if len(found_photos) >= 8:
                    break
                info_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
                    "action": "query",
                    "titles": img_t,
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "iiurlwidth": 800,
                    "format": "json"
                })
                try:
                    req_info = urllib.request.Request(info_url, headers=headers)
                    with urllib.request.urlopen(req_info, timeout=3) as img_resp:
                        img_data = json.loads(img_resp.read().decode('utf-8'))
                        img_pages = img_data.get("query", {}).get("pages", {})
                        for _, ipage in img_pages.items():
                            info_list = ipage.get("imageinfo", [])
                            if info_list:
                                thumb_url = info_list[0].get("thumburl") or info_list[0].get("url")
                                clean_name = img_t.replace("File:", "").replace(".jpg", "").replace(".png", "")
                                if thumb_url:
                                    found_photos.append({
                                        "url": thumb_url,
                                        "title": clean_name[:45],
                                        "category": categories[idx % len(categories)]
                                    })
                except Exception:
                    continue
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")

    return found_photos


# --- ИИ ГЕНЕРАЦИЯ: АТМОСФЕРА + ИСТОРИЯ ---
def get_ai_data(uni_name):
    prompt = f"""
Ты эксперт по высшему образованию. Для университета '{uni_name}' сформируй ответ СТРОГО в формате JSON без markdown блоков:
{{
  "atmosphere": "3-4 емких предложения про реальную студенческую атмосферу, кампус, общежития и вайб учебы на русском языке.",
  "history": "3 емких предложения про историю основания, ключевые вехи становления и наследие вуза на русском языке."
}}
"""
    if GEMINI_API_KEY and GEMINI_API_KEY != "ВАШ_КЛЮЧ_СЮДА":
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=9) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))
                raw = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if raw.startswith("```"):
                    lines = raw.splitlines()
                    raw = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:]).strip()
                return json.loads(raw)
        except Exception as e:
            print(f"Gemini error: {e}")

    return {
        "atmosphere": f"Кампус {uni_name} предлагает активную студенческую среду, современные лаборатории и насыщенную проектную работу.",
        "history": f"Основанный как ведущий образовательный центр, {uni_name} прошел путь масштабного развития и сформировал богатое академическое наследие."
    }


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    data = request.get_json() or {}
    raw_query = data.get('university', '').strip()
    if not raw_query:
        return jsonify({"error": "Пустой запрос"}), 400

    aliases = {
        "nu": "Nazarbayev University",
        "ну": "Nazarbayev University",
        "mit": "Massachusetts Institute of Technology",
        "мит": "Massachusetts Institute of Technology",
        "кбту": "Kazakh-British Technical University",
        "kbtu": "Kazakh-British Technical University",
        "казну": "Al-Farabi Kazakh National University",
        "kaznu": "Al-Farabi Kazakh National University"
    }
    search_uni = aliases.get(raw_query.lower(), raw_query)

    ai_content = get_ai_data(search_uni)
    images = get_wikipedia_campus_photos(search_uni)

    return jsonify({
        "university": raw_query,
        "atmosphere": ai_content.get("atmosphere", ""),
        "history": ai_content.get("history", ""),
        "images": images
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
