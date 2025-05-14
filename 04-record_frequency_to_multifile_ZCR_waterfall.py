#!/usr/bin/env python3
import os
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_XCB_GL_INTEGRATION"] = "none"

from gnuradio import gr, qtgui, blocks, analog
from gnuradio.filter import firdes
import osmosdr
import sip
from PyQt5 import Qt, QtCore
import sys
import math
import time
import signal
from collections import deque

class WaterfallExplorer(Qt.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Baofeng Signal Explorer")

        # SDR & signal params
        self.freq = 437.225e6
        self.samp_rate = 2.4e6
        self.audio_rate = 48e3
        self.rf_gain = 40

        # Thresholds
        self.floor_db = -30.0
        self.trigger_rise = 10.0
        self.drop_below_avg = 5.0
        self.zcr_static_threshold = 0.4

        # State
        self.rolling_window = deque(maxlen=20)
        self.zcr_window = deque(maxlen=10)
        self.last_audio = 0
        self.recording = False
        self.filename = ""

        self.tb = gr.top_block()

        # Source
        self.src = osmosdr.source(args="numchan=1 rtl=0")
        self.src.set_sample_rate(self.samp_rate)
        self.src.set_center_freq(self.freq)
        self.src.set_gain(self.rf_gain)

        # Signal strength monitor
        self.mag = blocks.complex_to_mag_squared()
        self.avg = blocks.moving_average_ff(512, 1.0 / 512, 4000, 1)
        self.probe = blocks.probe_signal_f()
        self.tb.connect(self.src, self.mag, self.avg, self.probe)

        # Demodulator
        self.squelch = analog.simple_squelch_cc(-60, 1)
        self.nfm = analog.nbfm_rx(audio_rate=self.audio_rate, quad_rate=self.samp_rate, tau=75e-6, max_dev=5e3)
        self.tb.connect(self.src, self.squelch, self.nfm)

        # Audio probe for ZCR
        self.audio_tap = blocks.probe_signal_f()
        self.audio_tap_in = blocks.keep_one_in_n(gr.sizeof_float, 480)  # 10x per sec at 48kHz
        self.tb.connect(self.nfm, self.audio_tap_in, self.audio_tap)

        # Waterfall
        self.wf = qtgui.waterfall_sink_c(
            1024, firdes.WIN_BLACKMAN_hARRIS,
            self.freq, self.samp_rate, "Waterfall", 1
        )
        self.wf.set_update_time(0.10)
        self.wf.enable_grid(True)
        self.tb.connect(self.src, self.wf)
        self.wf_win = sip.wrapinstance(self.wf.pyqwidget(), Qt.QWidget)

        # GUI
        layout = Qt.QVBoxLayout()
        self.setLayout(layout)

        self.slider = Qt.QSlider(Qt.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(int((437.5e6 - 437.0e6) / 25e3))
        self.slider.setValue(int((self.freq - 437.0e6) / 25e3))
        self.slider.valueChanged.connect(self.update_freq)

        self.label = Qt.QLabel("Signal: ")
        self.label.setAlignment(Qt.Qt.AlignCenter)

        layout.addWidget(self.slider)
        layout.addWidget(self.label)
        layout.addWidget(self.wf_win)

        self.tb.start()

        self.timer = Qt.QTimer()
        self.timer.timeout.connect(self.poll_signal)
        self.timer.start(250)

    def update_freq(self, val):
        freq = 437.0e6 + val * 25e3
        self.freq = freq
        self.src.set_center_freq(freq)
        self.wf.set_frequency_range(freq, self.samp_rate)

    def poll_signal(self):
        level = self.probe.level()
        db = 10 * math.log10(max(level, 1e-12))
        self.label.setText(f"Signal: {db:.2f} dBFS @ {self.freq/1e6:.6f} MHz")
        self.rolling_window.append(db)
        avg_db = sum(self.rolling_window) / len(self.rolling_window)

        # Fake ZCR on audio stream
        audio_val = self.audio_tap.level()
        zcr = abs(audio_val - self.last_audio)
        self.last_audio = audio_val
        self.zcr_window.append(1 if zcr > 1e-3 else 0)
        zcr_ratio = sum(self.zcr_window) / len(self.zcr_window)

        if not self.recording and db > self.floor_db + self.trigger_rise:
            self.filename = f"/tmp/baofeng_{int(time.time())}.wav"
            self._start_recording(self.filename)
            print(f"🔴 Recording ACTIVE at {db:.2f} dBFS")

        elif self.recording:
            signal_dropped = db < self.floor_db + self.drop_below_avg
            static_detected = zcr_ratio > self.zcr_static_threshold

            if signal_dropped and static_detected:
                print(f"⚫️ Recording stopped (ZCR={zcr_ratio:.2f})")
                self._stop_recording()

    def _start_recording(self, filename):
        self.tb.lock()
        try:
            self.wav_sink = blocks.wavfile_sink(filename, 1, int(self.audio_rate), 16)
            self.tb.connect(self.nfm, self.wav_sink)
            self.recording = True
        finally:
            self.tb.unlock()

    def _stop_recording(self):
        time.sleep(0.25)
        self.tb.lock()
        try:
            self.tb.disconnect(self.nfm, self.wav_sink)
        finally:
            self.tb.unlock()

        size = os.path.getsize(self.filename) if os.path.exists(self.filename) else 0
        if size <= 44:
            os.remove(self.filename)
            print(f"⚠️ Deleted empty file: {self.filename}")
        else:
            print(f"💾 Saved file: {self.filename}")
        self.recording = False

    def closeEvent(self, event):
        if self.recording:
            self._stop_recording()
        self.timer.stop()
        self.tb.stop()
        self.tb.wait()
        event.accept()

def handle_sigint(*args):
    print("\n[CTRL+C] Quitting...")
    Qt.QApplication.quit()

signal.signal(signal.SIGINT, handle_sigint)

if __name__ == '__main__':
    app = Qt.QApplication(sys.argv)
    explorer = WaterfallExplorer()
    explorer.resize(1000, 600)
    explorer.show()
    sys.exit(app.exec_())

