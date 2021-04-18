import asyncio
import threading
import sys
import time


from connect import SignallingServerConnection

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')


from gi.repository import Gtk, Gst, GObject, GLib

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
        #loop = GObject.MainLoop()

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

        pipeline = None

        if config["protocol"] == "SRT":
            pipeline = Gst.parse_launch("srtsrc uri=srt://:25570 ! decodebin ! videoconvert ! gtksink name=gtksink")
        elif config["protocol"] == "UDP":
            pipeline = Gst.parse_launch('udpsrc port=25570 caps = "application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string){}, payload=(int)96" ! queue ! rtp{}depay ! decodebin ! videoconvert ! gtksink name=gtksink'.format(config["encoder"], config["encoder"].lower()))
        elif config["protocol"] == "TCP":
            pipeline = Gst.parse_launch('tcpserversrc host=127.0.0.1 port=25571 ! matroskademux ! decodebin ! videoconvert ! gtksink name=gtksink')
        elif config["protocol"] == "RTMP":
            #gst-launch-1.0 -v rtmpsrc location=rtmp://127.0.0.1:25570/live/obs ! decodebin ! videoconvert ! autovideosink
            pipeline = Gst.parse_launch('rtmpsrc location=rtmp://127.0.0.1:25570/live/obs ! decodebin ! videoconvert ! gtksink name=gtksink')


        #WORKS pad_added missing from previous https://stackoverflow.com/questions/49639362/gstreamer-python-decodebin-jpegenc-elements-not-linking

  



        #pipeline.set_state(Gst.State.PLAYING)

        gtksink = pipeline.get_by_name("gtksink")
        self.em.emit("start_receiver_preview", gtksink)

        pipeline.set_state(Gst.State.PLAYING)
        
        bus = pipeline.get_bus()
        
        #bus.add_watch(GLib.PRIORITY_DEFAULT, self.bus_msg_handler, None)
        #bus.create_watch()
        #bus.set_sync_handler(self.bus_msg_handler)

        #bus.connect("message", self.bus_msg_handler)
        #bus.add_signal_watch()
        #bus.enable_sync_message_emission()
        
        #loop.run()
        
        
        
        #pipeline.set_state(Gst.State.PLAYING)

        # wait until EOS or error



        #

        # free resources
        #pipeline.set_state(Gst.State.NULL)

    def bus_msg_handler(receiver, bus, message):
            try:
                print(message.parse_tag())
            except TypeError:
                pass
        #pass

    def msg_handler(self, msg):
        print("receiver", msg)

        if msg.startswith("ROOM_OK"):
            self.em.emit("change_label", label_id="receiver_room_id_label", new_text=ROOM_ID)
