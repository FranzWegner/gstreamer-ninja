import asyncio
import threading
import sys
import time
import requests
import json
import pydivert
import random



from datetime import datetime


import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

from gi.repository import Gtk, Gst, GObject, GLib

Gst.debug_set_active(False)
Gst.debug_set_default_threshold(3)

Gst.init(None)
Gst.init_check(None)

SENDER_PIPELINE = "filesrc location=B:/python/sample_files_custom/Custom_2.mp4 ! qtdemux ! h264parse config-interval=-1 ! tee name=t t. ! queue ! mpegtsmux ! srtsink uri=srt://192.168.0.119:25570/ latency=0 t. ! queue ! avdec_h264 ! videoanalyse ! videoconvert ! autovideosink"
#SENDER_PIPELINE = "videotestsrc ! videoconvert ! autovideosink"
RECEIVER_PIPELINE = 'srtsrc uri=srt://:25570 ! queue ! decodebin ! queue ! videoanalyse ! videoconvert ! autovideosink'

global chance
chance = 0.00

#sender_sync_point = 0
#receiver_sync_point = None


def sender_msg_handler(bus, message, *user_data):


    if message.type == Gst.MessageType.ELEMENT:
        videoanalyse_struc = message.get_structure()
        luma = videoanalyse_struc.get_value("luma-average")
        timestamp = videoanalyse_struc.get_value("timestamp")
        if (luma and luma < 0.01):
            #dt = datetime.now()
            global sender_sync_point
            sender_sync_point = time.time_ns()
            

def receiver_msg_handler(bus, message, *user_data):
    if message.type == Gst.MessageType.ELEMENT:
        videoanalyse_struc = message.get_structure()
        luma = videoanalyse_struc.get_value("luma-average")
        timestamp = videoanalyse_struc.get_value("timestamp")
        if (luma and luma < 0.01):
            #dt = datetime.now()
            global receiver_sync_point
            receiver_sync_point = time.time_ns()

            print("hello123", (receiver_sync_point - sender_sync_point) / 1000000 )


def message_callback_test(bus, message):
    print(message, "132")

def start_sender():

    ctx = GLib.MainContext.new()
    ctx.push_thread_default()
    loop = GLib.MainLoop(ctx)

    #Gst.init(sys.argv[1:])
    pipeline = Gst.parse_launch(SENDER_PIPELINE)

    pipeline.set_state(Gst.State.PLAYING)

    bus = pipeline.get_bus()
    bus.set_sync_handler(sender_msg_handler)
    
    #GLib.MainContext.push_thread_default(GLib.MainContext().get_thread_default())
    #bus.add_signal_watch()
    #bus.connect("message::state-changed", message_callback_test)



    #loop.run()


def start_receiver():
    Gst.init(sys.argv[1:])
    pipeline = Gst.parse_launch(RECEIVER_PIPELINE)

    pipeline.set_state(Gst.State.PLAYING)

    bus = pipeline.get_bus()
    bus.set_sync_handler(receiver_msg_handler)

def start_traffic_control():
    with pydivert.WinDivert("outbound") as w:
        for packet in w:
            #print(chance)
            c = random.random()
            if c < chance:
                print(chance)
            else:
                w.send(packet)
            
            

if __name__ == "__main__":

    print("hello?")
    
    sender_thread = threading.Thread(target=start_sender)
    receiver_thread = threading.Thread(target=start_receiver)
    network_thread = threading.Thread(target=start_traffic_control)

    sender_thread.daemon = True
    receiver_thread.daemon = True
    network_thread.daemon = True

    try:
        sender_thread.start()
        receiver_thread.start()
        #network_thread.start()
        #while True: time.sleep(100)

        loop = asyncio.get_event_loop()
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
