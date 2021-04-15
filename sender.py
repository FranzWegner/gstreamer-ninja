import asyncio
import threading
import json
import sys
import logging

from connect import SignallingServerConnection

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')


from gi.repository import Gtk, Gst

Gst.init(None)
Gst.init_check(None)

ROOM_ID = "123"

test_config = {'receiver_source_list': 'videotestsrc', 'receiver_protocol_list': 'SRT', 'receiver_encoder_list': 
'H264'}

class Sender:

    def __init__(self, e_emitter):

        self.em = e_emitter

        self.pipeline = None
        self.bus = None
        self.message = None

        #self.create_pipeline_from_config(test_config)
        

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
        elif msg.startswith('ROOM_PEER_MSG'):
            data = json.loads(msg.split(maxsplit=2)[2])
            if "update_sender_config" in data:
                self.create_pipeline_from_config(data["update_sender_config"])
    
    def create_pipeline_from_config(self, config):
        print("Trying to build Gstreamer Pipeline from this config:", config)
        Gst.init(sys.argv[1:])

        source = Gst.ElementFactory.make("videotestsrc", "source")
        tee = Gst.ElementFactory.make("tee", "tee")
        queue = Gst.ElementFactory.make("queue")


        # emit widget only to main

        self.em.emit("start_sender_preview", source)

        #new pipeline for network

        pipeline = Gst.Pipeline.new("sending-pipeline")
        sink = Gst.ElementFactory.make("autovideosink", "sink")

        pipeline.add(source)
        pipeline.add(sink)

        source.link(sink)

        pipeline.set_state(Gst.State.PLAYING)
        


        
