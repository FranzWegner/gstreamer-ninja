import asyncio
import threading

from connect import SignallingServerConnection

ROOM_ID = "123"

class Sender:

    def __init__(self, e_emitter):

        self.em = e_emitter

        

        #self.gui_handler = gui_handler

        print("Creating Sender")
        connection = SignallingServerConnection("sender", "receiver", "wss://localhost:8443", ROOM_ID, self.msg_handler)
        
        # helpful: https://gist.github.com/lars-tiede/01e5f5a551f29a5f300e

        # needed because run in extra thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(connection.connect())
        loop.run_until_complete(connection.loop())

    def msg_handler(self, msg):
        print("sender", msg)

        if msg.startswith("ROOM_OK"):
            self.em.emit("change_label", label_id="sender_room_id_label", new_text=ROOM_ID)
