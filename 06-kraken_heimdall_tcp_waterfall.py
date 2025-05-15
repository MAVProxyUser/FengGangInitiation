#!/usr/bin/env python3
import sys
import socket
import signal

from PyQt5 import QtWidgets
import sip

from gnuradio import gr, blocks, qtgui
from gnuradio.filter import firdes
from gnuradio.krakensdr.krakensdr_source import krakensdr_source
import os
# — suppress GL errors over SSH/X11 —
os.environ["QT_XCB_GL_INTEGRATION"] = "none"
os.environ["QT_OPENGL"]             = "software"
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
#QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseSoftwareOpenGL)

# ——— Configuration —————————————————————————————————————
HOST       = "127.0.0.1"
IQ_PORT    = 5000
CTRL_PORT  = 5001      # unused unless you need the control interface
CENTER_HZ  = 437.225e6
SAMP_RATE  = 2.4e6
GAIN       = [40.0]

# ——— Port‐check helper ————————————————————————————————————
def check_port(port, name):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((HOST, port))
        s.close()
        print(f"[+] {name} listening on {HOST}:{port}")
    except Exception as e:
        print(f"[!] {name} not reachable on {HOST}:{port}: {e}")
        print("    → Start Heimdall DAQ in eth mode:")
        print("      cd ~/heimdall_daq_fw/Firmware")
        print("      sudo ./daq_stop.sh && sudo ./daq_start_sm.sh")
        sys.exit(1)

# ——— Main GUI + flowgraph —————————————————————————————————
class KrakenWaterfall(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KrakenSDR Live Waterfall")

        # build flowgraph
        self.tb = gr.top_block()

        # instantiate the KrakenSDR source
        try:
            self.src = krakensdr_source(
                ipAddr      = HOST,
                port        = IQ_PORT,
                ctrlPort    = CTRL_PORT,
                numChannels = 1,
                freq        = CENTER_HZ / 1e6,  # in MHz
                gain        = GAIN,
                debug       = False
            )
        except Exception as e:
            print(f"[!] Failed to create KrakenSDR source: {e!r}")
            sys.exit(1)

        # throttle so we don't overwhelm the GUI
        self.throttle = blocks.throttle(
            itemsize        = gr.sizeof_gr_complex,
            samples_per_sec = SAMP_RATE
        )

        # waterfall sink — note: no number_of_inputs kwarg here
        self.wf = qtgui.waterfall_sink_c(
            1024,                                    # fft size
            firdes.WIN_BLACKMAN_hARRIS,              # window
            CENTER_HZ,                               # center freq
            SAMP_RATE,                               # bandwidth
            "Channel 0 Waterfall"                    # name/title
        )
        self.wf.set_update_time(0.10)
        self.wf.enable_grid(True)

        # connect the blocks
        self.tb.connect(self.src, self.throttle, self.wf)

        # wrap & embed in Qt
        wf_win = sip.wrapinstance(self.wf.pyqwidget(), QtWidgets.QWidget)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(wf_win)
        self.setLayout(layout)

        # start flowgraph
        try:
            self.tb.start()
        except Exception as e:
            print(f"[!] Flowgraph start failed: {e!r}")
            sys.exit(1)

    def closeEvent(self, event):
        self.tb.stop()
        self.tb.wait()
        event.accept()

def main():
    # check that the IQ port is up
    check_port(IQ_PORT, "IQ server")
    # if you need control interface, uncomment:
    # check_port(CTRL_PORT, "Control interface")

    app = QtWidgets.QApplication(sys.argv)
    win = KrakenWaterfall()
    win.resize(900, 600)
    win.show()

    # clean exit on Ctrl-C
    def on_quit(signum, frame):
        win.close()
        QtWidgets.QApplication.quit()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, on_quit)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

