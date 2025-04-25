#!/bin/bash

echo "🚀 Criando estrutura do YouTube MCP Server local..."

mkdir -p youtube_mcp_server/tools
cd youtube_mcp_server || exit

# requirements.txt
cat << 'EOF' > requirements.txt
fastapi
uvicorn
httpx
python-dotenv
EOF

# youtube_utils.py
cat << 'EOF' > youtube_utils.py
import httpx
import os

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

BASE_URL = "https://www.googleapis.com/youtube/v3"

def youtube_get(endpoint: str, params: dict):
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY não definida no ambiente.")
    params["key"] = YOUTUBE_API_KEY
    response = httpx.get(f"{BASE_URL}/{endpoint}", params=params)
    response.raise_for_status()
    return response.json()
EOF

# main.py
cat << 'EOF' > main.py
from fastapi import FastAPI, Request
from tools import (
    getVideoDetails, searchVideos, getTranscripts, getRelatedVideos,
    getChannelStatistics, getChannelTopVideos, getVideoEngagementRatio,
    getTrendingVideos, compareVideos
)

app = FastAPI()

@app.get("/")
def root():
    return {"message": "🧠 YouTube MCP Server rodando com FastAPI."}

@app.get("/metadata")
def metadata():
    return {
        "tools": [
            {"name": "getVideoDetails", "description": "Obtém detalhes de vídeos"},
            {"name": "searchVideos", "description": "Pesquisa vídeos"},
            {"name": "getTranscripts", "description": "Obtém transcrição de vídeos"},
            {"name": "getRelatedVideos", "description": "Obtém vídeos relacionados"},
            {"name": "getChannelStatistics", "description": "Estatísticas de canais"},
            {"name": "getChannelTopVideos", "description": "Top vídeos do canal"},
            {"name": "getVideoEngagementRatio", "description": "Engajamento do vídeo"},
            {"name": "getTrendingVideos", "description": "Vídeos em alta"},
            {"name": "compareVideos", "description": "Compara dois vídeos"}
        ]
    }

@app.post("/")
async def invoke_tool(request: Request):
    body = await request.json()
    tool = body.get("tool")
    parameters = body.get("parameters", {})
    tools = {
        "getVideoDetails": getVideoDetails.run,
        "searchVideos": searchVideos.run,
        "getTranscripts": getTranscripts.run,
        "getRelatedVideos": getRelatedVideos.run,
        "getChannelStatistics": getChannelStatistics.run,
        "getChannelTopVideos": getChannelTopVideos.run,
        "getVideoEngagementRatio": getVideoEngagementRatio.run,
        "getTrendingVideos": getTrendingVideos.run,
        "compareVideos": compareVideos.run,
    }
    if tool not in tools:
        return {"error": f"Ferramenta '{tool}' não encontrada."}
    return tools[tool](**parameters)
EOF

# tools/*.py
for TOOL in getVideoDetails searchVideos getTranscripts getRelatedVideos getChannelStatistics getChannelTopVideos getVideoEngagementRatio getTrendingVideos compareVideos
do
cat << EOF > tools/${TOOL}.py
from youtube_utils import youtube_get

def run(**kwargs):
    return youtube_get("${TOOL}", kwargs)
EOF
done

# __init__.py
touch tools/__init__.py

echo "✅ Tudo pronto!"
echo "📁 Navegue para youtube_mcp_server e instale as dependências:"
echo "    cd youtube_mcp_server"
echo "    pip install -r requirements.txt"
echo "🔑 Defina sua API Key em um .env:"
echo "    echo 'YOUTUBE_API_KEY=SUA_CHAVE' > .env"
echo "🚀 Rode o servidor com:"
echo "    uvicorn main:app --reload --port 5002"

