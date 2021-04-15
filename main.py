import threading
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

from gi.repository import Gtk, Gst
Gst.init(None)
Gst.init_check(None)

from sender import Sender

class WindowMain:

    def __init__(self):
        self.builder = Gtk.Builder()
        self.builder.add_from_file("gui/gstreamer-ninja-gui.glade")
        self.builder.connect_signals(self)

        self.window_receiver = self.builder.get_object("window_receiver")
        self.window_receiver.set_keep_above(True)
        self.window_receiver.show()

        self.window_sender = self.builder.get_object("window_sender")
        self.window_sender.move(1920,0)
        self.window_sender.set_keep_above(True)
        self.window_sender.show()




    
    def main(self):
        Gtk.main()
        



def start_sender():
    sender = Sender()

def start_gui():
    app = WindowMain()
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
    



    


