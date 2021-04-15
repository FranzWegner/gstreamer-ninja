import ssl
import websockets
import asyncio
import threading
import time

class SignallingServerConnection:
    def __init__(self, own_id, peer_id, server, room_id):
        self.own_id = own_id
        self.peer_id = peer_id
        self.server = server
        self.room_id = room_id
        self.connection = None
        
        

    async def connect(self):
        sslctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        self.connection = await websockets.connect(self.server, ssl=sslctx)
        await self.connection.send('HELLO %s' % self.own_id)
        await self.connection.send('ROOM {}'.format(self.room_id)) 
        

    
    async def loop(self):
        async for msg in self.connection:
            print(self.own_id, msg)
            
