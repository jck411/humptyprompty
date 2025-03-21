# config.py
import logging

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
WEBSOCKET_PATH = "/ws/chat"
HTTP_BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

def setup_logger(name=__name__, level=logging.WARNING):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(ch)
    return logger

logger = setup_logger()
