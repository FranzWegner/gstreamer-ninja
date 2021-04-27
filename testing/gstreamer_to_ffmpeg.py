import sys

import gi

gi.require_version('GLib', '2.0')
gi.require_version('GObject', '2.0')
gi.require_version('Gst', '1.0')

from gi.repository import Gst, GObject, GLib

Gst.debug_set_active(True)
Gst.debug_set_default_threshold(3)

pipeline = None
bus = None
message = None

# initialize GStreamer
Gst.init(sys.argv[1:])

# build the pipeline
pipeline = Gst.parse_launch(
    "videotestsrc ! x264enc ! decodebin ! videoconvert ! autovideosink"
)

# start playing
pipeline.set_state(Gst.State.PLAYING)

# wait until EOS or error
bus = pipeline.get_bus()
msg = bus.timed_pop_filtered(
    Gst.CLOCK_TIME_NONE,
    Gst.MessageType.ERROR | Gst.MessageType.EOS
)

# free resources
pipeline.set_state(Gst.State.NULL)