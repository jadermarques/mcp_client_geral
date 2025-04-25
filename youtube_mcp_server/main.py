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
