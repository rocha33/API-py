from fastapi import FastAPI, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import yt_dlp
import os
import uuid
import asyncio
import shutil
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Pasta para salvar downloads (crie manualmente ou deixe o código criar)
DOWNLOAD_DIR = Path("/tmp/downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código de startup (opcional – roda quando a API inicia)
    # Exemplo: print("Aplicação iniciando... carregando recursos")
    # ... (pode carregar modelos, conexões, etc.)

    yield  # ← aqui a API começa a aceitar requisições normalmente

    # Código de shutdown (executa quando a API para / é desligada)
    try:
        shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)
        # print("Pasta downloads limpa com sucesso")
    except Exception as e:
        # Silencioso para evitar erros visíveis no log final
        pass  # ou logar: logger.warning(f"Erro na limpeza: {e}")

app = FastAPI(
    title="YouTube Downloader API",
    description="API simples para baixar vídeos do YouTube usando yt-dlp",
    version="1.0.0"
)


# Tempo para deletar arquivos após download (em segundos)
AUTO_DELETE_AFTER = 3600  # 1 hora

app.mount("/files", StaticFiles(directory=DOWNLOAD_DIR), name="files")

class DownloadRequest(BaseModel):
    url: str
    format: str = "mp4"  # "mp4" ou "mp3"
    quality: Optional[str] = "best"  # "best", "720p", "480p", etc.

def get_ydl_opts(format_type: str, quality: str):
    common = {
        'outtmpl': str(DOWNLOAD_DIR / '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'continuedl': True,
        'retries': 10,
    }

    if format_type == "mp3":
        return {
            **common,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',  # ou '320' se quiser mais alta
            }],
        }
    else:  # mp4
        if quality == "best":
            fmt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == "720p":
            fmt = 'bestvideo[height<=720][ext=mp4]+bestaudio/best'
        else:
            fmt = 'best[ext=mp4]'
        
        return {**common, 'format': fmt}

async def download_video(url: str, format_type: str, quality: str, task_id: str):
    try:
        ydl_opts = get_ydl_opts(format_type, quality)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            filename = ydl.prepare_filename(info)
            
            # Download real
            ydl.download([url])
            
        # Retorna o caminho do arquivo baixado
        return {"status": "completed", "filename": Path(filename).name, "task_id": task_id}
    
    except Exception as e:
        return {"status": "error", "message": str(e), "task_id": task_id}

@app.post("/download")
async def start_download(
    request: DownloadRequest,
    background_tasks: BackgroundTasks
):
    task_id = str(uuid.uuid4())
    
    background_tasks.add_task(
        download_video,
        request.url,
        request.format,
        request.quality,
        task_id
    )
    
    return JSONResponse({
        "status": "queued",
        "task_id": task_id,
        "message": "Download iniciado em background. Verifique /status/{task_id} ou /files depois."
    })

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    # Simples: verifica se o arquivo existe (em produção use Redis/Celery para status real)
    for file in DOWNLOAD_DIR.iterdir():
        if task_id in file.name:  # heurística simples
            return {"status": "completed", "file": file.name, "url": f"/files/{file.name}"}
    
    return {"status": "processing or not found", "task_id": task_id}

@app.get("/files/{filename}")
async def serve_file(filename: str):
    file_path = DOWNLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado ou expirado")
    
    # Agenda deleção após envio (opcional)
    asyncio.create_task(delete_after(file_path, AUTO_DELETE_AFTER))
    
    return FileResponse(file_path, filename=filename, media_type="application/octet-stream")

async def delete_after(path: Path, delay: int):
    await asyncio.sleep(delay)
    if path.exists():
        path.unlink()

@app.on_event("shutdown")
def cleanup():
    # Opcional: limpa pasta ao parar a API
    shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)

#if __name__ == "__main__":
#    import uvicorn
#    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)