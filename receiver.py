import asyncio
import threading
import sys
import time
import requests


from connect import SignallingServerConnection

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')


from gi.repository import Gtk, Gst, GObject, GLib

Gst.debug_set_active(True)
Gst.debug_set_default_threshold(3)

Gst.init(None)
Gst.init_check(None)

#loop = GObject.MainLoop()

ROOM_ID = "123"

class Receiver:

    def __init__(self, e_emitter):
        
        self.em = e_emitter
        self.em.on("update_sender_config", self.update_sender_config)
        self.em.on("update_receiver_config", self.update_receiver_config)
        self.pipeline = None
        self.config = None


        print("Creating Receiver")
        self.connection = SignallingServerConnection("receiver_bla", "sender", "wss://localhost:8443", ROOM_ID, self.msg_handler)
        

        # needed because run in extra thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.connection.connect())
        loop.run_until_complete(self.connection.loop())

    def update_sender_config(self, config):
        self.connection.send_msg({"update_sender_config": config})
    
    def bus_msg_handler(self, bus, message, *user_data):
        if message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print("hahaha", err, debug)
            self.retry_pipeline()
    
    def retry_pipeline(self):
        self.pipeline.set_state(Gst.State.NULL)
        time.sleep(2)
        self.pipeline.set_state(Gst.State.PLAYING)

    async def wait_for_playlist(self):
        #bullshit, not async
        r = requests.get('http://127.0.0.1:5000/hls/playlist.m3u8')
        while r.status_code == 404:
            print(r.status_code)
            await asyncio.sleep(1)
            r = requests.get('http://127.0.0.1:5000/hls/playlist.m3u8')
        return True

    
    def update_receiver_config(self, config):
        Gst.init(sys.argv[1:])

        self.config = config
        #GObject.MainContext.push_thread_default(GObject.MainContext())
        

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

        if (self.pipeline):
            self.pipeline.set_state(Gst.State.NULL)

        self.pipeline = None

        if config["protocol"] == "SRT":
            self.pipeline = Gst.parse_launch("srtsrc uri=srt://:25570 ! queue ! decodebin ! videoconvert ! gtksink name=gtksink")
        elif config["protocol"] == "UDP":
            self.pipeline = Gst.parse_launch('udpsrc port=25570 caps = "application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string){}, payload=(int)96" ! queue ! rtp{}depay ! decodebin ! videoconvert ! gtksink name=gtksink'.format(config["encoder"], config["encoder"].lower()))
        elif config["protocol"] == "TCP":
            self.pipeline = Gst.parse_launch('tcpserversrc host=127.0.0.1 port=25571 ! queue ! matroskademux ! queue !  decodebin ! videoconvert ! gtksink name=gtksink')
        elif config["protocol"] == "RTMP":
            #gst-launch-1.0 -v rtmpsrc location=rtmp://127.0.0.1:25570/live/obs ! decodebin ! videoconvert ! autovideosink
            self.pipeline = Gst.parse_launch('rtmpsrc location=rtmp://127.0.0.1:25570/live/obs ! decodebin ! videoconvert ! gtksink name=gtksink')
        elif config["protocol"] == "HLS":
            self.pipeline = Gst.parse_launch("souphttpsrc location=http://127.0.0.1:5000/hls/playlist.m3u8 ! hlsdemux ! decodebin ! videoconvert ! gtksink name=gtksink")
        elif config["protocol"] == "DASH":
            self.pipeline = Gst.parse_launch("souphttpsrc location=http://127.0.0.1:5000/dash/dash.mpd retries=-1 ! dashdemux ! decodebin ! videoconvert ! gtksink name=gtksink")
        elif config["protocol"] == "WebRTC":
            self.pipeline = Gst.parse_launch("videotestsrc ! videoconvert ! gtksink name=gtksink")


        #WORKS pad_added missing from previous https://stackoverflow.com/questions/49639362/gstreamer-python-decodebin-jpegenc-elements-not-linking

  



        #pipeline.set_state(Gst.State.PLAYING)

        gtksink = self.pipeline.get_by_name("gtksink")
        self.em.emit("start_receiver_preview", gtksink)

        #pipeline.set_state(Gst.State.READY)

        if config["protocol"] == "HLS":
            pass
            #block until return 200 instead of 404
            #loop = asyncio.new_event_loop()
            #loop.run_until_complete(self.wait_for_playlist())
           


        

        self.pipeline.set_state(Gst.State.PLAYING)
        
        bus = self.pipeline.get_bus()
        #bus.set_sync_handler(self.bus_msg_handler)
        
        

        #bus.add_signal_watch()

        #bus.add_watch(GLib.PRIORITY_HIGH, self.bus_msg_handler, None)
        #bus.create_watch()
        #bus.set_sync_handler(self.bus_msg_handler)
        #bus.add_signal_watch()
        #bus.connect("message", self.bus_msg_handler, loop)
        
        #bus.remove_signal_watch()
        
        #bus.enable_sync_message_emission()
        
        #loop.run()
        
        
        
        #pipeline.set_state(Gst.State.PLAYING)

        # wait until EOS or error



        #

        # free resources
        #pipeline.set_state(Gst.State.NULL)



    def msg_handler(self, msg):
        print("receiver", msg)

        if msg.startswith("ROOM_OK"):
            self.em.emit("change_label", label_id="receiver_room_id_label", new_text=ROOM_ID)
