import asyncio
import threading

from connect import SignallingServerConnection

ROOM_ID = "123"

class Receiver:

    def __init__(self, e_emitter):

        self.em = e_emitter
        self.em.on("update_sender_config", self.update_sender_config)


        print("Creating Receiver")
        self.connection = SignallingServerConnection("receiver", "sender", "wss://localhost:8443", ROOM_ID, self.msg_handler)
        

        # needed because run in extra thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.connection.connect())
        loop.run_until_complete(self.connection.loop())

    def update_sender_config(self, config):
        self.connection.send_msg({"update_sender_config": config})

    def msg_handler(self, msg):
        print("receiver", msg)

        if msg.startswith("ROOM_OK"):
            self.em.emit("change_label", label_id="receiver_room_id_label", new_text=ROOM_ID)
