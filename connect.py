import ssl
import websockets
import asyncio
import threading
import time
import json

class SignallingServerConnection:
    def __init__(self, own_id, peer_id, server, room_id, msg_handler):
        self.own_id = own_id
        self.peer_id = peer_id
        self.server = server
        self.room_id = room_id
        self.connection = None

        self.msg_handler = msg_handler

    
    def send_msg(self, msg):
        formatted_msg = 'ROOM_PEER_MSG {} {}'.format(self.peer_id, json.dumps(msg))
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.connection.send(formatted_msg))
        loop.close()
        
        

    async def connect(self):
        sslctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        self.connection = await websockets.connect(self.server, ssl=sslctx)
        await self.connection.send('HELLO %s' % self.own_id)
        await self.connection.send('ROOM {}'.format(self.room_id)) 
        

    
    async def loop(self):
        async for msg in self.connection:
            #print(self.own_id, msg)
            self.msg_handler(msg)
            
