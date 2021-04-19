# https://github.com/Dejvino/birdie/blob/8b104cbd234e9a2a33ca5fb84e3f4096aa10f1b4/play-alarm-sound

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GLib
import sys
import os


Gst.init(None)
mainloop = GLib.MainLoop()

source = Gst.ElementFactory.make("videotestsrc", "source")
sink = Gst.ElementFactory.make("autovideosink", "sink")

pl = Gst.Pipeline.new("test-pipeline")

pl.add(source)
pl.add(sink)
source.link(sink)

bus = pl.get_bus()
#bus.add_signal_watch()
#bus.connect("message", bus_call, mainloop)




def bus_call(bus, message, *loop):
    print(message)
    global pl
    if message.type == Gst.MessageType.EOS:
        pl.set_state(Gst.State.READY)
        pl.set_state(Gst.State.PLAYING)
    elif message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write(f"Gst Error: {err}: {debug}\n")
        loop.quit()
    return True


pl.set_state(Gst.State.PLAYING)
bus.set_sync_handler(bus_call)

try:
    mainloop.run()
except:
    mainloop.quit()