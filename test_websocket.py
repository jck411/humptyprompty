import asyncio
import websockets

async def test_connection():
    uri = "ws://127.0.0.1:8000/ws/chat"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            # Send a chat message
            await websocket.send('{"action": "chat", "messages": [{"sender": "user", "text": "Hello"}]}')
            print("Sent chat message")
            # Wait for a response with a timeout
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"Received response: {response}")
            except asyncio.TimeoutError:
                print("Timeout waiting for response")
    except Exception as e:
        print(f"Error connecting to WebSocket: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
