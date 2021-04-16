import asyncio
import threading
import sys
import time

from connect import SignallingServerConnection

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')


from gi.repository import Gtk, Gst

Gst.debug_set_active(True)
Gst.debug_set_default_threshold(3)

Gst.init(None)
Gst.init_check(None)



ROOM_ID = "123"

class Receiver:

    def __init__(self, e_emitter):

        self.em = e_emitter
        self.em.on("update_sender_config", self.update_sender_config)
        self.em.on("update_receiver_config", self.update_receiver_config)


        print("Creating Receiver")
        self.connection = SignallingServerConnection("receiver", "sender", "wss://localhost:8443", ROOM_ID, self.msg_handler)
        

        # needed because run in extra thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.connection.connect())
        loop.run_until_complete(self.connection.loop())

    def update_sender_config(self, config):
        self.connection.send_msg({"update_sender_config": config})
    
    def update_receiver_config(self, config):
        Gst.init(sys.argv[1:])
        # pipeline = Gst.Pipeline.new("receiver-pipeline")

        # #gst-launch-1.0 srtsrc uri=srt://:25570 ! decodebin ! autovideosink

        # source = Gst.ElementFactory.make("srtsrc")
        # source.set_property("uri", "srt://:25570")
        # source.set_property("mode", 2)
        # decodebin = Gst.ElementFactory.make("decodebin")
        # #decodebin.
        # preview_sink = Gst.ElementFactory.make("autovideosink")

        # pipeline.add(source)
        # pipeline.add(decodebin)
        # pipeline.add(preview_sink)

        # source.link(decodebin)
        # decodebin.link(preview_sink)

        #WORKS pad_added missing from previous https://stackoverflow.com/questions/49639362/gstreamer-python-decodebin-jpegenc-elements-not-linking
        easy_pipeline = Gst.parse_launch("srtsrc uri=srt://:25570 ! decodebin ! videoconvert ! gtksink name=gtksink")

        gtksink = easy_pipeline.get_by_name("gtksink")
        self.em.emit("start_receiver_preview", gtksink)



        easy_pipeline.set_state(Gst.State.PLAYING)


        
        #pipeline.set_state(Gst.State.PLAYING)

        # wait until EOS or error
        #bus = pipeline.get_bus()
        #msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE,Gst.MessageType.ERROR | Gst.MessageType.EOS)

        # free resources
        #pipeline.set_state(Gst.State.NULL)




    def msg_handler(self, msg):
        print("receiver", msg)

        if msg.startswith("ROOM_OK"):
            self.em.emit("change_label", label_id="receiver_room_id_label", new_text=ROOM_ID)
