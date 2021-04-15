import threading
import time
import event_emitter as events

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

from gi.repository import Gtk, Gst
Gst.init(None)
Gst.init_check(None)

from sender import Sender

em = events.EventEmitter()



class WindowMain:

    def __init__(self, e_emitter):

        self.em = e_emitter
        
        self.em.on("change_label", self.change_label)

        self.builder = Gtk.Builder()
        self.builder.add_from_file("gui/gstreamer-ninja-gui.glade")
        self.builder.connect_signals(self)

        self.window_receiver = self.builder.get_object("window_receiver")
        self.window_receiver.set_keep_above(True)
        self.window_receiver.show()

        self.window_sender = self.builder.get_object("window_sender")
        self.window_sender.move(1920,0)
        self.window_sender.set_keep_above(True)
        #self.change_label("sender_room_id_label", "blablabla")
        self.window_sender.show()
        

    def change_label(self, label_id, new_text):
        #dirty, has to wait for windows to load up
        time.sleep(2)
        label = self.builder.get_object(label_id)
        label.set_text(new_text)
    
    def main(self):
        Gtk.main()
        




def gui_handler(command, data):
    #if command == "CHANGE_LABEL":
    #    app.change_label(data["label_id", data["label_text"]])
    #app.change_label("sender_room_id_label", "blablabla")
    pass

def start_sender():
    sender = Sender(em)

def start_gui():
    app = WindowMain(em)
    app.main()


if __name__ == "__main__":
    
    gui_thread = threading.Thread(target=start_gui)
    sender_thread = threading.Thread(target=start_sender)

    gui_thread.daemon = True
    sender_thread.daemon = True

    try:
        gui_thread.start()
        sender_thread.start()
        while True: time.sleep(100)
    except (KeyboardInterrupt, SystemExit):
        pass
    



    


