import asyncio
import threading
import json
import sys
import logging
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
                #pass
    
    
    def get_correct_payloader_element(self, encoder):
        return Gst.ElementFactory.make("rtp" + encoder.lower() + "pay")

    def create_pipeline_from_config(self, config):

        if (self.pipeline):
            self.pipeline.set_state(Gst.State.NULL)

        self.pipeline = None        

        print("Trying to build Gstreamer Pipeline from this config:", config)
        Gst.init(sys.argv[1:])
        self.pipeline = Gst.Pipeline.new("sender-pipeline")

        source = Gst.ElementFactory.make("videotestsrc")
        source.props.pattern = "ball"
        #source.set_property("is-live", True)
        tee = Gst.ElementFactory.make("tee")
        preview_queue = Gst.ElementFactory.make("queue")
        network_queue = Gst.ElementFactory.make("queue")
        preview_sink = Gst.ElementFactory.make("gtksink")

        videoconvert = Gst.ElementFactory.make("videoconvert")
        
        encoder = None
        caps = None

        # caps nicht nötig bei SRT und UDP bisher
        if config["encoder"] == "H264":
            encoder = Gst.ElementFactory.make("x264enc")
            encoder.set_property("tune", "zerolatency")
            encoder.set_property("key-int-max", 15)
            caps = Gst.Caps.from_string("video/x-h264, profile=high")
        elif config["encoder"] == "H265":
            encoder = Gst.ElementFactory.make("x265enc")
            encoder.props.tune = "zerolatency"
            encoder.set_property("key-int-max", 15)
            #encoder.props.bitrate = 1024
            caps = Gst.Caps.from_string("video/x-h265, profile=main")
        elif config["encoder"] == "VP8":
            encoder = Gst.ElementFactory.make("vp8enc")
            caps = Gst.Caps.from_string("video/x-vp8, profile=0")
        elif config["encoder"] == "VP9":
            encoder = Gst.ElementFactory.make("vp9enc")
            caps = Gst.Caps.from_string("video/x-vp9, profile=0")


        muxer = None
        network_sink = None
        parser = None

        if config["protocol"] == "SRT":
            muxer = Gst.ElementFactory.make("mpegtsmux")
            network_sink = Gst.ElementFactory.make("srtsink")
            network_sink.set_property("uri", "srt://192.168.0.119:25570/")
            network_sink.set_property("wait-for-connection", "false")
            network_sink.set_property("mode", 1)
        elif config["protocol"] == "UDP":
            # gst-launch-1.0 -v videotestsrc ! x264enc tune=zerolatency ! rtph264pay ! udpsink host=127.0.0.1 port=25570
            
            
            muxer = self.get_correct_payloader_element(config["encoder"])

            network_sink = Gst.ElementFactory.make("udpsink")
            network_sink.props.host = "127.0.0.1"
            network_sink.props.port = 25570
        elif config["protocol"] == "TCP":
            #gst-launch-1.0 -v videotestsrc ! timeoverlay ! vp8enc ! matroskamux ! tcpclientsink host=127.0.0.1 port=25571
            if (config["encoder"] == "H265"):
                parser = Gst.ElementFactory.make("h265parse")
            muxer = Gst.ElementFactory.make("matroskamux")
            network_sink = Gst.ElementFactory.make("tcpclientsink")
            network_sink.props.host = "127.0.0.1"
            network_sink.props.port = 25571
        elif config["protocol"] == "RTMP":
            #gst-launch-1.0 -v videotestsrc ! timeoverlay ! x264enc tune=zerolatency ! flvmux ! rtmpsink location="rtmp://127.0.0.1:25570/live/obs live=1"
            muxer = Gst.ElementFactory.make("flvmux")
            network_sink = Gst.ElementFactory.make("rtmpsink")
            network_sink.props.location = "rtmp://127.0.0.1:25570/live/obs live=1"
        elif config["protocol"] == "HLS":
            #gst-launch-1.0 videotestsrc is-live=true ! x264enc ! mpegtsmux ! hlssink max-files=5 target-duration=2 playlist-location="B:/python/gstreamer-ninja/tmp/hls/playlist.m3u8" location=B:/python/gstreamer-ninja/tmp/hls/segment%05d.ts
            muxer = Gst.ElementFactory.make("mpegtsmux")
            network_sink = Gst.ElementFactory.make("hlssink")
            network_sink.set_property("playlist-location", "B:/python/gstreamer-ninja/http-server/hls/playlist.m3u8")
            network_sink.set_property("location", "B:/python/gstreamer-ninja/http-server/hls/segment%05d.ts")
            network_sink.set_property("target-duration", 2)
        elif config["protocol"] == "DASH":
            #dummy

            muxer = Gst.ElementFactory.make("mpegtsmux")
            network_sink = Gst.ElementFactory.make("fakesink")








        

        self.em.emit("start_sender_preview", preview_sink)

        self.pipeline.add(source)
        self.pipeline.add(tee)
        self.pipeline.add(preview_queue)
        self.pipeline.add(network_queue)
        self.pipeline.add(preview_sink)


        self.pipeline.add(videoconvert)
        self.pipeline.add(encoder)
        if (parser):
            self.pipeline.add(parser)

        self.pipeline.add(muxer)
        self.pipeline.add(network_sink)

        source.link(tee)
        tee.link(preview_queue)
        tee.link(network_queue)
        preview_queue.link(preview_sink)
        network_queue.link(videoconvert)
        videoconvert.link(encoder)
        #encoder.link_filtered(muxer, caps)

        if (parser):
            encoder.link(parser)
            parser.link(muxer)
        else:
            encoder.link(muxer)
  
        muxer.link(network_sink)

        

        # emit widget only to main

        if config["protocol"] == "DASH":
            self.pipeline = Gst.parse_launch("videotestsrc is-live=true pattern=ball ! videoconvert ! x264enc ! dashsink.video_0 dashsink name=dashsink max-files=5 target-duration=2 mpd-root-path=B:/python/gstreamer-ninja/http-server/dash/ dynamic=true minimum-update-period=1000")
            #self.em.emit("start_sender_preview", self.pipeline.get_by_name("gtksink"))

        self.pipeline.set_state(Gst.State.PLAYING)

        # wait until EOS or error
        #bus = pipeline.get_bus()
        #msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE,Gst.MessageType.ERROR | Gst.MessageType.EOS)

        # free resources
        #pipeline.set_state(Gst.State.NULL)



        

        


        
