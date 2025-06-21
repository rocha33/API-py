from fastapi import FastAPI, Query
from youtube_transcript_api import YouTubeTranscriptApi
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Permitir acesso externo (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"mensagem": "API de Legendas do YouTube com FastAPI no Render"}

@app.get("/extrair")
def extrair(video_id: str, idiomas: str = "pt,en"):
    langs = [lang.strip() for lang in idiomas.split(",")]
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
        legendas = [
            {"start": item["start"], "duration": item["duration"], "text": item["text"]}
            for item in transcript
        ]
        return {"status": "ok", "legendas": legendas}
    except Exception as e:
        return {"status": "erro", "mensagem": str(e)}

