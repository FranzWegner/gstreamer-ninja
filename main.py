import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

from gi.repository import Gtk, Gst
Gst.init(None)
Gst.init_check(None)


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


if __name__ == "__main__":
    app = WindowMain()
    app.main()