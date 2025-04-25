from youtube_utils import youtube_get

def run(**kwargs):
    return youtube_get("getTrendingVideos", kwargs)
