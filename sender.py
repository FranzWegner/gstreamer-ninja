import asyncio
import threading

from connect import SignallingServerConnection


class Sender:

    def __init__(self):
        print("Creating Sender")
        connection = SignallingServerConnection("sender", "receiver", "wss://localhost:8443", "123")
        
        # helpful: https://gist.github.com/lars-tiede/01e5f5a551f29a5f300e

        # needed because run in extra thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(connection.connect())
        loop.run_until_complete(connection.loop())
        