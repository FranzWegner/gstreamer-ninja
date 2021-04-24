import asyncio
import threading
import sys
import time
import requests
import json


from connect import SignallingServerConnection

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

from gi.repository import Gtk, Gst, GObject, GLib

Gst.debug_set_active(True)
Gst.debug_set_default_threshold(4)

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
        self.webrtcbin = None
        self.preview_sink = None


        print("Creating Receiver")
        self.connection = SignallingServerConnection("receiver", "sender", "wss://localhost:8443", ROOM_ID, self.msg_handler)
        

        # needed because run in extra thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.connection.connect())
        loop.run_until_complete(self.connection.loop())

    def update_sender_config(self, config):
        self.connection.send_msg({"update_sender_config": config})
    
    def bus_msg_handler(self, bus, message, *user_data):

        print("typ", message.type)

        if message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print("hahaha", err, debug)
            #self.retry_pipeline()
        elif message.type == Gst.MessageType.WARNING:
            msg = message.parse_warning()
            print("warning_message", msg)
        elif message.type == Gst.MessageType.QOS:
            live, running_time, stream_time, timestamp, duration = message.parse_qos()
            jitter, proportion, quality = message.parse_qos_values()
            _format, processed, dropped = message.parse_qos_stats()
            print(live, running_time, stream_time, timestamp, duration)
            print(jitter, proportion, quality)
            print(_format, processed, dropped)
        elif message.type == Gst.MessageType.ELEMENT:
            struc = message.get_structure()
            #print(struc.to_string())

    
    def retry_pipeline(self):


        state = self.pipeline.get_state(10)[1]
        print("pipeline_state", state)

        if state == Gst.State.READY:
            print("Retrying pipeline in two seconds")
            time.sleep(2)
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline.set_state(Gst.State.PLAYING)

        

        

    async def wait_for_playlist(self):
        #bullshit, not async
        r = requests.get('http://127.0.0.1:5000/hls/playlist.m3u8')
        while r.status_code == 404:
            print(r.status_code)
            await asyncio.sleep(1)
            r = requests.get('http://127.0.0.1:5000/hls/playlist.m3u8')
        return True

    def send_ice_candidate_message(self, _, mlineindex, candidate):
        icemsg = {'ice': {'candidate': candidate, 'sdpMLineIndex': mlineindex}}
        # print(icemsg)
        self.connection.send_msg(icemsg)

    def on_incoming_decodebin_stream(self, _, pad):
        if not pad.has_current_caps():
            print (pad, 'has no caps, ignoring')
            return
        
        # https://github.com/centricular/gstwebrtc-demos/issues/45

        caps = pad.get_current_caps()       
        name = caps.to_string()

        if name.startswith('video'):
            q = Gst.ElementFactory.make('queue')
            q2 = Gst.ElementFactory.make('queue')
            conv = Gst.ElementFactory.make('videoconvert')
            sink = Gst.ElementFactory.make('fpsdisplaysink')
            sink.props.name = "gtksink"
            self.preview_sink = sink
            #self.em.emit("start_receiver_preview", sink)
            #self.pipe.add(q, conv, sink) https://github.com/centricular/gstwebrtc-demos/issues/45#issuecomment-441468933
            self.pipeline.add(q)
            self.pipeline.add(conv)
            self.pipeline.add(q2)
            self.pipeline.add(sink)
            self.pipeline.sync_children_states()
            pad.link(q.get_static_pad('sink'))
            q.link(conv)
            conv.link(sink)





            


    def on_incoming_stream(self, _, pad):
        print("Receiving video...")
        promise = Gst.Promise.new()

        if pad.direction != Gst.PadDirection.SRC:
            return

        decodebin = Gst.ElementFactory.make('decodebin')
        decodebin.connect('pad-added', self.on_incoming_decodebin_stream)
        self.pipeline.add(decodebin)
        decodebin.sync_state_with_parent()
        #self.webrtcbin.props.latency = 5000
        self.webrtcbin.link(decodebin)
    
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
            self.pipeline = Gst.parse_launch("srtsrc uri=srt://:25570 ! queue ! decodebin ! queue ! videoconvert ! fpsdisplaysink")
        elif config["protocol"] == "UDP":
            self.pipeline = Gst.parse_launch('udpsrc port=25570 caps = "application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string){}, payload=(int)96" ! queue ! rtp{}depay ! decodebin ! queue ! videoconvert ! videoscale ! fpsdisplaysink'.format(config["encoder"], config["encoder"].lower()))
        elif config["protocol"] == "TCP":
            self.pipeline = Gst.parse_launch('tcpserversrc host=127.0.0.1 port=25571 ! queue ! matroskademux ! queue ! decodebin ! queue ! videoconvert ! videoscale ! fpsdisplaysink')
        elif config["protocol"] == "RTMP":
            #gst-launch-1.0 -v rtmpsrc location=rtmp://127.0.0.1:25570/live/obs ! decodebin ! videoconvert ! autovideosink
            self.pipeline = Gst.parse_launch('rtmpsrc location=rtmp://127.0.0.1:25570/live/obs ! decodebin ! queue ! videoconvert ! videoscale ! fpsdisplaysink')
        elif config["protocol"] == "HLS":
            self.pipeline = Gst.parse_launch("souphttpsrc location=http://127.0.0.1:5000/hls/playlist.m3u8 ! hlsdemux ! decodebin ! queue ! videoconvert ! videoscale ! fpsdisplaysink")
        elif config["protocol"] == "DASH":
            self.pipeline = Gst.parse_launch("souphttpsrc location=http://127.0.0.1:5000/dash/dash.mpd retries=-1 ! dashdemux ! decodebin ! queue ! videoconvert ! videoscale ! fpsdisplaysink")
        elif config["protocol"] == "WebRTC":
            self.pipeline = Gst.parse_launch("videotestsrc ! videoconvert ! queue ! vp8enc ! rtpvp8pay ! queue ! webrtcbin name=webrtc_receive bundle-policy=max-bundle stun-server=stun://stun.l.google.com:19302")
            self.webrtcbin = self.pipeline.get_by_name('webrtc_receive')
            self.webrtcbin.connect('on-ice-candidate', self.send_ice_candidate_message)
            self.webrtcbin.connect('pad-added', self.on_incoming_stream)
        elif config["protocol"] == "RIST":
            self.pipeline = Gst.parse_launch("ristsrc address=0.0.0.0 port=25570 ! rtpmp2tdepay ! decodebin ! videoconvert ! fpsdisplaysink")



        #WORKS pad_added missing from previous https://stackoverflow.com/questions/49639362/gstreamer-python-decodebin-jpegenc-elements-not-linking

  



        #pipeline.set_state(Gst.State.PLAYING)

        if config["protocol"] != "WebRTC":
            pass
            # last_element = self.pipeline.get_by_name("decodeme")
            # decodebin = Gst.ElementFactory.make("decodebin")
            # queue = Gst.ElementFactory.make("queue")
            # videoconvert = Gst.ElementFactory.make("videoconvert")
            # videoscale = Gst.ElementFactory.make("videoscale")
            # preview_sink = Gst.ElementFactory.make("autovideosink")
            # preview_sink.props.name = "gtksink"

            # self.pipeline.add(decodebin)
            # self.pipeline.add(queue)
            # self.pipeline.add(videoconvert)
            # self.pipeline.add(videoscale)
            # self.pipeline.add(preview_sink)

            # #self.pipeline.sync_children_states()
            # last_element.link(decodebin)
            # decodebin.link(queue)
            # queue.link(videoconvert)
            # videoconvert.link(videoscale)
            # videoscale.link(preview_sink)


            #gtksink = self.pipeline.get_by_name("gtksink")
            #self.preview_sink = gtksink
            #self.em.emit("start_receiver_preview", gtksink)

        #pipeline.set_state(Gst.State.READY)

        if config["protocol"] == "HLS":
            pass
            #block until return 200 instead of 404
            #loop = asyncio.new_event_loop()
            #loop.run_until_complete(self.wait_for_playlist())
           


        

        self.pipeline.set_state(Gst.State.PLAYING)
        
        bus = self.pipeline.get_bus()
        bus.set_sync_handler(self.bus_msg_handler)
        
        

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

    def send_sdp_answer(self, answer):
        text = answer.sdp.as_text()
        sdp = {'type': 'answer', 'sdp': text}
        self.connection.send_msg(sdp)

    def on_answer_created(self, promise):
        promise.wait()
        reply = promise.get_reply()
        answer = reply.get_value("answer")
        
        promise = Gst.Promise.new()
        self.webrtcbin.emit("set-local-description", answer, promise)
        promise.interrupt()
        self.send_sdp_answer(answer)

    def on_remote_dec_set(self, promise, _):
        promise.wait()
        print("Remote Description was set.")
        promise = Gst.Promise.new_with_change_func(self.on_answer_created)
        self.webrtcbin.emit("create-answer", None, promise)

    def msg_handler(self, msg):
        #print("receiver", msg)

        if msg.startswith("ROOM_OK"):
            self.em.emit("change_label", label_id="receiver_room_id_label", new_text=ROOM_ID)
        elif msg.startswith('ROOM_PEER_MSG'):
            data = json.loads(msg.split(maxsplit=2)[2])
            if "sdp" in data:
                sdp = data["sdp"]
                res, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
                offer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER, sdpmsg)

                promise = Gst.Promise.new_with_change_func(self.on_remote_dec_set, None)
                self.webrtcbin.emit("set-remote-description", offer, promise)
            elif "ice" in data:
                mline_index = int(data["ice"]["sdpMLineIndex"])
                candidate = data["ice"]["candidate"]
                self.webrtcbin.emit("add-ice-candidate", mline_index, candidate)
