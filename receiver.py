import asyncio
import threading
import sys
import time
import requests
import json
import pydivert
import random
import csv


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
        self.em.on("sender_benchmark_started", self.create_new_benchmark)
        self.pipeline = None
        self.config = None
        self.webrtcbin = None
        self.preview_sink = None
        self.benchmark = None
        self.benchmark_started = False
        self.benchmark_mode = False
        self.decoding_errors = 0
        self.chance_of_dropping_packets = 0.00
        self.network_throttle_thread = threading.Thread(target=self.start_traffic_control)
        self.network_throttle_thread.daemon = True

        Gst.debug_add_log_function(self.handle_gst_log_message)


        print("Creating Receiver")
        self.connection = SignallingServerConnection("receiver", "sender", "wss://localhost:8443", ROOM_ID, self.msg_handler)
        

        # needed because run in extra thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.connection.connect())
        loop.run_until_complete(self.connection.loop())

    def handle_gst_log_message(self, category, level, file, function, line, obj, message, *user_data):
        #print(category.get_name(), level, message.get())

        if self.benchmark_mode and self.benchmark_started:
            if category.get_name().startswith("libav") and level == Gst.DebugLevel.ERROR:
                #print("log_error", message.get())
                self.decoding_errors += 1
    
    def create_new_benchmark(self, sender_timestamp):
        self.benchmark = {"sender_start": sender_timestamp}
        print(self.benchmark)

    def start_traffic_control(self):
        #start as admin
        with pydivert.WinDivert("outbound and (tcp.DstPort == 5000)") as w:
            for packet in w:
                #print(chance)
                c = random.random()
                if self.benchmark_started and (c < self.chance_of_dropping_packets):
                    #print(chance)
                    print("current_chance", c)
                    #w.send(packet)
                    
                else:
                    w.send(packet)
                    
                
                
    

    def update_sender_config(self, config):
        self.connection.send_msg({"update_sender_config": config})
    
    def bus_msg_handler(self, bus, message, *user_data):

        #print("typ", message.type)

        if message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print("error_message", err, debug)
            #self.retry_pipeline()
        elif message.type == Gst.MessageType.WARNING:
            msg = message.parse_warning()
            print("warning_message", msg)
        elif message.type == Gst.MessageType.QOS:
            live, running_time, stream_time, timestamp, duration = message.parse_qos()
            jitter, proportion, quality = message.parse_qos_values()
            _format, processed, dropped = message.parse_qos_stats()
            #print(live, running_time, stream_time, timestamp, duration)
            #print(jitter, proportion, quality)
            #print(_format, processed, dropped)
        elif message.type == Gst.MessageType.ELEMENT:
            videoanalyse_struc = message.get_structure()
            luma = videoanalyse_struc.get_value("luma-average")
            if (luma and luma < 0.01):
                if not self.benchmark_started:
                    self.start_benchmark()

    def start_benchmark(self):
        print("Start Benchmark, receiver side")
        self.network_throttle_thread.start()
        #self.start_traffic_control()
        self.benchmark_started = True
        self.decoding_errors = 0
        if self.benchmark:
            self.benchmark["receiver_start"] = time.time_ns()
            self.benchmark["frames_rendered"] = []
            self.benchmark["decoding_errors"] = []
            print(self.benchmark)
            print("Latency in ms", (self.benchmark["receiver_start"] - self.benchmark["sender_start"]) / 1000000 )

            x = threading.Thread(target=self.start_measurements)
            x.daemon = False
            x.start()

    def start_measurements(self):
        fpsdisplaysink = self.pipeline.get_by_name("displaysink")
        seconds_counter = 0
        while seconds_counter < 30:
            frames_rendered = fpsdisplaysink.get_property("frames-rendered")
            #print("frames_rendered", frames_rendered)
            self.benchmark["frames_rendered"].append(frames_rendered)
            self.benchmark["decoding_errors"].append(self.decoding_errors)
            time.sleep(1)
            seconds_counter += 1
        self.stop_benchmark()
    
    def stop_benchmark(self):
        self.benchmark_started = False
        print("final_benchmark", self.benchmark)
        self.save_benchmark_to_file()

    def save_benchmark_to_file(self):
        #new line for avoiding extra line https://docs.python.org/3/library/csv.html at bottom
        with open ("test_file.csv", newline='', mode="w") as benchmark_file:
         
            file_writer = csv.writer(benchmark_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

            file_writer.writerow(["Frames Rendered", "Decoding Errors", "Start Sender", "Start Receiver"])
            file_writer.writerow(["", "", self.benchmark["sender_start"], self.benchmark["receiver_start"]])

            for i,value in enumerate(self.benchmark["frames_rendered"]):
                file_writer.writerow([self.benchmark["frames_rendered"][i], self.benchmark["decoding_errors"][i]])
        
        print("File saved")
    
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
    
    def fps_measurements_callback(self, fpsdisplaysink, fps, droprate, avgfps, *udata):
        if self.benchmark_started:
            pass
            #self.benchmark["fps"].append(fps)
            #print(self.benchmark)

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

        if config["source"] == "benchmarkfilesrc":
            self.benchmark_mode = True

        if config["protocol"] == "SRT":
            self.pipeline = Gst.parse_launch("srtsrc uri=srt://:25570 ! queue ! decodebin ! queue ! videoconvert ! videoanalyse ! fpsdisplaysink signal-fps-measurements=false name=displaysink")
        elif config["protocol"] == "UDP":
            self.pipeline = Gst.parse_launch('udpsrc port=25570 caps = "application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string){}, payload=(int)96" ! queue ! rtp{}depay ! decodebin ! queue ! videoconvert ! videoanalyse ! fpsdisplaysink signal-fps-measurements=false name=displaysink'.format(config["encoder"], config["encoder"].lower()))
        elif config["protocol"] == "TCP":
            self.pipeline = Gst.parse_launch('tcpserversrc host=127.0.0.1 port=25571 ! queue ! matroskademux ! queue ! decodebin ! queue ! videoconvert ! videoanalyse ! fpsdisplaysink signal-fps-measurements=false name=displaysink')
        elif config["protocol"] == "RTMP":
            #gst-launch-1.0 -v rtmpsrc location=rtmp://127.0.0.1:25570/live/obs ! decodebin ! videoconvert ! autovideosink
            self.pipeline = Gst.parse_launch('rtmpsrc location=rtmp://127.0.0.1:25570/live/obs ! decodebin ! queue ! videoconvert ! videoscale ! fpsdisplaysink')
        elif config["protocol"].startswith("HLS"):
            self.pipeline = Gst.parse_launch("souphttpsrc location=http://127.0.0.1:5000/hls/out.m3u8 ! hlsdemux ! decodebin ! queue ! videoconvert ! videoanalyse ! videoscale ! fpsdisplaysink")
        elif config["protocol"].startswith("DASH"):
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
           


        
        
        bus = self.pipeline.get_bus()

        if self.benchmark_mode:
            bus.set_sync_handler(self.bus_msg_handler)

        if config["protocol"].startswith("HLS") or config["protocol"].startswith("DASH") or config["protocol"].startswith("RTMP"):
            x = threading.Thread(target=self.start_pipeline_with_delay)
            x.daemon = True
            x.start()
        else:
            self.pipeline.set_state(Gst.State.PLAYING)


        
        #self.pipeline.set_state(Gst.State.PLAYING)

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

    def start_pipeline_with_delay(self):
        time.sleep(10)
        self.pipeline.set_state(Gst.State.PLAYING)
    
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
