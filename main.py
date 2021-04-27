import threading
import time
import event_emitter as events
import sys
import logging
import asyncio
import pydivert
import random
#logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

from gi.repository import Gtk, Gst

#Gst.debug_set_active(True)
#Gst.debug_set_default_threshold(3)

Gst.init(None)
Gst.init_check(None)

from sender import Sender
from receiver import Receiver

em = events.EventEmitter()

chance = 0.05


class WindowMain:

    def __init__(self, e_emitter):

        self.em = e_emitter
        
        self.em.on("change_label", self.change_label)
        self.em.on("remove_container", self.remove_container)
        self.em.on("start_sender_preview", self.start_sender_preview)
        self.em.on("start_receiver_preview", self.start_receiver_preview)
        

        self.builder = Gtk.Builder()
        self.builder.add_from_file("gui/gstreamer-ninja-gui.glade")
        self.builder.connect_signals(self)

        self.window_receiver = self.builder.get_object("window_receiver")
        #self.window_receiver.set_keep_above(True)
        self.window_receiver.show()

        self.window_sender = self.builder.get_object("window_sender")
        self.window_sender.move(1920,0)
        #self.window_sender.set_keep_above(True)
        #self.change_label("sender_room_id_label", "blablabla")
        self.window_sender.show()
        

    def change_label(self, label_id, new_text):
        #dirty, has to wait for windows to load up
        time.sleep(2)
        label = self.builder.get_object(label_id)
        label.set_text(new_text)
    
    def remove_container(self, container_id, window):
        if window == "sender":
            self.builder.get_object("sender_container").remove(self.builder.get_object(container_id))
        else:
            self.builder.get_object("receiver_container").remove(self.builder.get_object(container_id))

        
    
    def on_receiver_request_video_button_clicked(self, user_data):
        config = {
            "source": self.builder.get_object("receiver_source_list").get_active_text(),
            "protocol": self.builder.get_object("receiver_protocol_list").get_active_text(),
            "encoder": self.builder.get_object("receiver_encoder_list").get_active_text(),
            "address": self.builder.get_object("receiver_address").get_text(),
            "port": self.builder.get_object("receiver_port").get_text()
        }

        

        #start receiver
        self.em.emit("update_receiver_config", config)

        

        self.em.emit("update_sender_config", config)

    def on_click_me_clicked(self, user_data):
        pass

    def on_sender_connect_button_clicked(self, sender_room_id_entry):
        #print(sender_room_id_entry.get_text())
        sender_thread = threading.Thread(target=start_sender, args=[sender_room_id_entry.get_text()])
        sender_thread.daemon = True
        sender_thread.start()
        
    def on_receiver_connect_button_clicked(self, receiver_room_id_entry):
    #print(sender_room_id_entry.get_text())
        receiver_thread = threading.Thread(target=start_receiver, args=[receiver_room_id_entry.get_text()])
        receiver_thread.daemon = True
        receiver_thread.start()
    


    def start_sender_preview(self, gtksink):

        #time.sleep(1)


        container = self.builder.get_object("sender_local_preview_container")

        children = container.get_children()

        if (len(children) > 0):
            children[0].destroy()

        container.pack_start(gtksink.props.widget, True, True, 0)
        gtksink.props.widget.show()

        #receive like this
        #gst-launch-1.0 srtsrc uri=srt://:25570 ! decodebin ! autovideosink
    
    def start_receiver_preview(self, gtksink):

        logging.debug(gtksink)

        container = self.builder.get_object("receiver_local_preview_container")
        
        #detect if gtksink is already running seperate windows, usually when webrtcbin is used
        parent_window = gtksink.props.widget.get_parent_window()
        if parent_window:
            gtksink.props.widget.unparent()

        children = container.get_children()

        if (len(children) > 0):
            children[0].destroy()

        container.pack_start(gtksink.props.widget, True, True, 0)

        gtksink.props.widget.show()


        


    
    def main(self):
        Gtk.main()
        




def gui_handler(command, data):
    #if command == "CHANGE_LABEL":
    #    app.change_label(data["label_id", data["label_text"]])
    #app.change_label("sender_room_id_label", "blablabla")
    pass

def start_sender(*args):
    sender = Sender(em, args[0])

def start_receiver(*args):
    receiver = Receiver(em, args[0])

def start_gui():
    app = WindowMain(em)
    app.main()



if __name__ == "__main__":
    
    gui_thread = threading.Thread(target=start_gui)
    #sender_thread = threading.Thread(target=start_sender)
    #receiver_thread = threading.Thread(target=start_receiver)

    gui_thread.daemon = True
    #sender_thread.daemon = True
    #receiver_thread.daemon = True

    try:
        gui_thread.start()
        #sender_thread.start()
        #receiver_thread.start()
        #while True: time.sleep(100)
        loop = asyncio.get_event_loop()
        
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
