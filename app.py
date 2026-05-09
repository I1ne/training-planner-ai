
import json
import re
import os
from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List


app = FastAPI()

load_dotenv()


@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

class RecommendRequest(BaseModel):
    goal: str
    level: str
    days_per_week: int
    duration_min: int
    equipment: Optional[str] = ""
    constraints: Optional[str] = ""
    notes: Optional[str] = ""

class PlanDay(BaseModel):
    day: str
    focus: str
    items: List[str]

class RecommendResponse(BaseModel):
    plan: List[PlanDay]
    explain: str

@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    prompt = f"""
Ты — профессиональный тренер. Составь персональный план тренировок на неделю.

Данные клиента:
- Цель: {req.goal}
- Уровень: {req.level}
- Тренировок в неделю: {req.days_per_week}
- Длительность: {req.duration_min} минут
- Оборудование: {req.equipment or "не указано"}
- Ограничения: {req.constraints or "нет"}
- Пожелания: {req.notes or "нет"}

ВАЖНО:
- Верни ответ ТОЛЬКО как JSON.
- Никаких комментариев.
- Никаких ```json или ``` .
- Никакого текста вне JSON.
- Используй ТОЛЬКО двойные кавычки.
- Никаких переносов строк внутри ключей.
- Строго соблюдай структуру ниже.


Формат ответа:
{{
  "plan": [
    {{
      "day": "День 1",
      "focus": "Акцент тренировки",
      "items": ["пункт 1", "пункт 2", "пункт 3"]
    }}
  ],
  "explain": "Короткое пояснение"
}}
""".strip()

    with GigaChat(
        credentials=os.getenv("GIGACHAT_CREDENTIALS"),
        scope=os.getenv("GIGACHAT_SCOPE"),
        model=os.getenv("GIGACHAT_MODEL", "GigaChat"),
        ca_bundle_file=os.getenv("GIGACHAT_CA_BUNDLE_FILE"),
    ) as client:
        chat = Chat(messages=[Messages(role=MessagesRole.USER, content=prompt)])
        resp = client.chat(chat)

    content = resp.choices[0].message.content.strip()

    # 1) убираем ```json / ``` если модель обернула ответ
    if "```" in content:
        parts = [p.strip() for p in content.split("```")]
        for p in parts:
            if p.startswith("{") and p.endswith("}"):
                content = p
                break

    # 2) вырезаем JSON из текста (если вокруг есть мусор)
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        content = match.group(0)

    # 3) парсим JSON
    try:
        return json.loads(content)
    except Exception:
        return {
            "plan": [{
                "day": "План",
                "focus": "Рекомендации",
                "items": [content[:3000]]
            }],
            "explain": "Ответ получен, но модель вернула нестрогий JSON."
        }
