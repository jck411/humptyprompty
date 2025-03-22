#!/usr/bin/env python3
import asyncio
import websockets
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_websocket():
    """Test WebSocket connection to the backend server"""
    uri = "ws://127.0.0.1:8000/ws/chat"
    
    logger.info(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("Connected successfully!")
            
            # Send a simple message
            message = {
                "action": "chat",
                "messages": [{"sender": "user", "text": "Hello, this is a test message"}]
            }
            logger.info(f"Sending message: {message}")
            await websocket.send(json.dumps(message))
            
            # Wait for a response
            logger.info("Waiting for response...")
            try:
                for _ in range(5):  # Try up to 5 messages
                    response = await websocket.recv()
                    if isinstance(response, bytes):
                        logger.info(f"Received binary data of length {len(response)}")
                    else:
                        try:
                            data = json.loads(response)
                            logger.info(f"Received response: {data}")
                        except json.JSONDecodeError:
                            logger.info(f"Received text: {response}")
            except websockets.exceptions.ConnectionClosed:
                logger.info("Connection closed by server")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket()) 