import asyncio
import websockets

async def test_rpc():
    try:
        uri = "ws://127.0.0.1:6463/?v=1&client_id=your_client_id"
        async with websockets.connect(uri) as ws:
            msg = await ws.recv()
            print("Connected and received:", msg)
    except Exception as e:
        print("Connection failed:", e)

asyncio.run(test_rpc())
