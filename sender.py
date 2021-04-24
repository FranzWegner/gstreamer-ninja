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

gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

from gi.repository import Gtk, Gst

Gst.debug_set_active(False)
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
        self.webrtcbin = None
        self.benchmark_started = False

        #self.create_pipeline_from_config(test_config)
        

        #self.gui_handler = gui_handler

        print("Creating Sender")
        self.connection = SignallingServerConnection("sender", "receiver", "wss://localhost:8443", ROOM_ID, self.msg_handler)
        
        # helpful: https://gist.github.com/lars-tiede/01e5f5a551f29a5f300e

        # needed because run in extra thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.connection.connect())
        loop.run_until_complete(self.connection.loop())

    def msg_handler(self, msg):
        #print("sender", msg)
        
        if msg.startswith("ROOM_OK"):
            self.em.emit("change_label", label_id="sender_room_id_label", new_text=ROOM_ID)
        elif msg.startswith('ROOM_PEER_MSG'):
            data = json.loads(msg.split(maxsplit=2)[2])
            if "update_sender_config" in data:
                self.create_pipeline_from_config(data["update_sender_config"])
                #pass
            elif "sdp" in data:
                sdp = data["sdp"]
                res, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
                answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
                promise = Gst.Promise.new_with_change_func(self.on_remote_dec_set)
                self.webrtcbin.emit("set-remote-description", answer, promise)
            elif "ice" in data:
                mline_index = int(data["ice"]["sdpMLineIndex"])
                candidate = data["ice"]["candidate"]
                self.webrtcbin.emit("add-ice-candidate", mline_index, candidate)
                print("ICE Candidate:", candidate)            
    
    def on_remote_dec_set(self, promise):
        promise.wait()
        print("Got Answer and Set Remote Description")



    def get_correct_payloader_element(self, encoder):
        return Gst.ElementFactory.make("rtp" + encoder.lower() + "pay")

    def send_sdp_offer(self, offer):
        text = offer.sdp.as_text()
        sdp = {'type': 'offer', 'sdp': text}
        self.connection.send_msg(sdp)

    def on_offer_created(self, promise, webrtcbin, __):
        promise.wait()
        reply = promise.get_reply()
        offer = reply.get_value('offer')
        promise = Gst.Promise.new()
        webrtcbin.emit('set-local-description', offer, promise)
        promise.interrupt()
        self.send_sdp_offer(offer)

    def on_negotiation_needed(self, webrtcbin):
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, webrtcbin, None)
        webrtcbin.emit('create-offer', None, promise)
        #self.create_data_channel()


    def send_ice_candidate_message(self, _, mlineindex, candidate):
        icemsg = {'ice': {'candidate': candidate, 'sdpMLineIndex': mlineindex}}
        # print(icemsg)
        #formatted_ice = 'ROOM_PEER_MSG {} {}'.format(self.peer_id, icemsg)
        #loop = asyncio.new_event_loop()
        #loop.run_until_complete(self.conn.send(formatted_ice))
        #loop.close()
        self.connection.send_msg(icemsg)


    def on_new_transceiver(self, webrtcbin, transceiver, *user_data):
        print("new_transceiver", transceiver)
        #promise = Gst.Promise.new_with_change_func(self.on_data_channel_created, webrtcbin, None)
        #self.create_data_channel()

    def start_benchmark(self):
        self.benchmark_started = True
        print("Start the benchmark!")

    def bus_msg_handler(self, bus, message, *user_data):
        if message.type == Gst.MessageType.ELEMENT:
            videoanalyse_struc = message.get_structure()
            luma = videoanalyse_struc.get_value("luma-average")
            timestamp = videoanalyse_struc.get_value("timestamp")
            if (luma and luma < 0.01):
                if not self.benchmark_started:
                    self.start_benchmark()
                

    def print_stats(self):
        while True:
            time.sleep(1)
            if (self.webrtcbin):
                promise = Gst.Promise.new()
                self.webrtcbin.emit("get-stats", None, promise)
                promise.wait()
                print(promise.get_reply().to_string())
            else:
                print(self.pipeline.get_by_name("network_sink").props.stats.to_string())

    def create_pipeline_from_config(self, config):

        if (self.pipeline):
            self.pipeline.set_state(Gst.State.NULL)

        self.pipeline = None        

        print("Trying to build Gstreamer Pipeline from this config:", config)
        Gst.init(sys.argv[1:])
        self.pipeline = Gst.Pipeline.new("sender-pipeline")

        source = None
        decodebin = None

        if config["source"] == "videotestsrc":
            source = Gst.ElementFactory.make("videotestsrc")
            source.props.pattern = "ball"
        elif config["source"] == "filesrc":
            source = Gst.ElementFactory.make("filesrc")
            source.props.location = "B:/python/gst-examples-master-webrtc/webrtc/sendrecv/gst/test.mp4"
            decodebin = Gst.ElementFactory.make("decodebin")
            self.pipeline = Gst.parse_launch('filesrc location="E:/2020-10-17_ChaosCity5/Entrance Videos/WINNING CUT/SenzaVolto_2020_WINNING_CUT.avi" ! decodebin ! queue ! videoconvert name=teeme')
        elif config["source"] == "benchmarkfilesrc":
            #unnesccary
            source = Gst.ElementFactory.make("filesrc")
            decodebin = Gst.ElementFactory.make("decodebin")
            self.pipeline = Gst.parse_launch('filesrc location="B:/python/sample_files_custom/Custom_2.mp4" ! decodebin ! queue ! videoconvert name=teeme')


        #source.set_property("is-live", True)
        tee = Gst.ElementFactory.make("tee")
        preview_queue = Gst.ElementFactory.make("queue")
        network_queue = Gst.ElementFactory.make("queue")
        videoanalyse = Gst.ElementFactory.make("videoanalyse")
        preview_sink = Gst.ElementFactory.make("autovideosink")

        videoconvert = Gst.ElementFactory.make("videoconvert")
        videoconvert2 = Gst.ElementFactory.make("videoconvert")
        videoscale = Gst.ElementFactory.make("videoscale")
        
        encoder = None
        caps = None

        # caps nicht nötig bei SRT und UDP bisher
        if config["encoder"] == "H264":
            encoder = Gst.ElementFactory.make("x264enc")
            encoder.set_property("tune", "zerolatency")
            encoder.set_property("key-int-max", 10)
            encoder.set_property("speed-preset", "faster")

            caps = Gst.Caps.from_string("video/x-h264, profile=high")
        elif config["encoder"] == "H265":
            encoder = Gst.ElementFactory.make("x265enc")
            encoder.props.tune = "zerolatency"
            encoder.set_property("key-int-max", 10)
            encoder.set_property("speed-preset", "ultrafast")
            caps = Gst.Caps.from_string("video/x-h265, profile=main")
        elif config["encoder"] == "VP8":
            encoder = Gst.ElementFactory.make("vp8enc")
            caps = Gst.Caps.from_string("video/x-vp8, profile=0")
            encoder.set_property("end-usage", "vbr")
            encoder.set_property("threads", 5)
            encoder.set_property("max-quantizer", 63)
            encoder.set_property("min-quantizer", 10)
            encoder.set_property("deadline", 1)

        elif config["encoder"] == "VP9":
            encoder = Gst.ElementFactory.make("vp9enc")
            caps = Gst.Caps.from_string("video/x-vp9, profile=0")
            encoder.set_property("end-usage", "vbr")
            encoder.set_property("threads", 5)
            encoder.set_property("max-quantizer", 63)
            encoder.set_property("min-quantizer", 30)
            encoder.set_property("deadline", 1)
            encoder.set_property("cpu-used", 12)
            encoder.set_property("target-bitrate", 2500000)


        muxer = None
        network_sink = None
        parser = None

        if config["protocol"] == "SRT":

            if config["encoder"] == "H264" or config["encoder"] == "H265":
                muxer = Gst.ElementFactory.make("mpegtsmux")
            else:
                muxer = Gst.ElementFactory.make("matroskamux")
                muxer.props.streamable = True

            
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
            muxer.props.streamable = True
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
        elif config["protocol"] == "WebRTC":
            muxer = self.get_correct_payloader_element(config["encoder"])

            network_sink = Gst.ElementFactory.make("webrtcbin")
            self.webrtcbin = network_sink
            network_sink.props.name = "webrtc_send"
            network_sink.set_property("bundle-policy", "max-compat")
            network_sink.set_property("stun-server", 'stun://stun.l.google.com:19302')

            network_sink.connect('on-negotiation-needed', self.on_negotiation_needed)
            network_sink.connect('on-ice-candidate', self.send_ice_candidate_message)
            network_sink.connect('on-new-transceiver', self.on_new_transceiver)
            #network_sink.connect('on-data-channel', self.on_data_channel)
        elif config["protocol"] == "RIST":
            #gst-launch-1.0 filesrc location=B:/python/sample_files_custom/Custom_1.mp4 ! qtdemux ! h264parse config-interval=-1 ! mpegtsmux ! rtpmp2tpay ! ristsink address=127.0.0.1 port=5004
            
            parser = Gst.ElementFactory.make("mpegtsmux")
            muxer = Gst.ElementFactory.make("rtpmp2tpay")
            network_sink = Gst.ElementFactory.make("ristsink")
            network_sink.props.address = "127.0.0.1"
            network_sink.props.port = 25570


    







        

        #self.em.emit("start_sender_preview", preview_sink)

        
        network_sink.props.name = "network_sink"
        if not decodebin:
            self.pipeline.add(source)
            

        self.pipeline.add(tee)
        self.pipeline.add(preview_queue)
        self.pipeline.add(network_queue)
        self.pipeline.add(videoscale)
        self.pipeline.add(videoanalyse)
        self.pipeline.add(preview_sink)


        self.pipeline.add(videoconvert)
        self.pipeline.add(encoder)
        if (parser):
            self.pipeline.add(parser)

        self.pipeline.add(muxer)
        self.pipeline.add(network_sink)

        if (decodebin):
            self.pipeline.get_by_name("teeme").link(tee)
        else:
            source.link(tee)
        
        tee.link(preview_queue)
        tee.link(network_queue)
        preview_queue.link(videoscale)
        videoscale.link(videoanalyse)
        videoanalyse.link(preview_sink)

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

        bus = self.pipeline.get_bus()
        #bus.set_sync_handler(self.bus_msg_handler)

        x = threading.Thread(target=self.print_stats)
        x.daemon = True
        #x.start()

        # options = Gst.Structure("application/data-channel")
        # options.set_value("ordered", True)
        # options.set_value("max-retransmits", 0)
        # data_channel = self.webrtcbin.emit('create-data-channel', "input", options)
        # print("hallo_echo", data_channel)
        # wait until EOS or error
        #bus = pipeline.get_bus()
        #msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE,Gst.MessageType.ERROR | Gst.MessageType.EOS)

        # free resources
        #pipeline.set_state(Gst.State.NULL)



        

        


        
