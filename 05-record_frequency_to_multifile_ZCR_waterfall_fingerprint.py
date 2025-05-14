#!/usr/bin/env python3
import sys, os, time, math, threading, signal
import numpy as np
from gnuradio import gr, blocks, analog, qtgui
from gnuradio.filter import firdes
import osmosdr
from PyQt5 import Qt, QtCore
import sip

# Suppress GL errors over SSH/X11
os.environ["QT_XCB_GL_INTEGRATION"] = "none"
os.environ["QT_OPENGL"] = "software"
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
Qt.QApplication.setAttribute(Qt.Qt.AA_UseSoftwareOpenGL)

class NFMRecorder(gr.top_block):
    def __init__(self, freq=437.225e6):
        super().__init__("NFM Recorder")
        self.freq = freq
        self.samp_rate = 2.4e6
        self.audio_rate = 48e3
        self.rf_gain = 40

        # IQ buffer
        self.iq_sink = blocks.vector_sink_c()

        # Audio buffer for ramp detection
        self.audio_sink = blocks.vector_sink_f()

        # Source
        self.src = osmosdr.source(args="numchan=1 rtl=0")
        self.src.set_sample_rate(self.samp_rate)
        self.src.set_center_freq(self.freq)
        self.src.set_gain(self.rf_gain)

        # Probe for audio power
        self.mag = blocks.complex_to_mag_squared()
        self.avg = blocks.moving_average_ff(512, 1.0/512)
        self.probe = blocks.probe_signal_f()

        # Demod chain
        self.squelch = analog.simple_squelch_cc(-60, 1)
        self.nfm = analog.nbfm_rx(self.audio_rate, self.samp_rate, 75e-6, 5e3)

        # Audio gate + sinks
        self.audio_gate = blocks.multiply_const_ff(0.0)
        self.null_sink = blocks.null_sink(gr.sizeof_float)
        self.wav_sink = None
        self.current_wav = None

        # Connections
        self.connect(self.src, self.mag, self.avg, self.probe)
        self.connect(self.src, self.iq_sink)                             # IQ data always
        self.connect(self.src, self.squelch, self.nfm, self.audio_gate)
        self.connect(self.audio_gate, self.audio_sink)                    # audio for ramp
        self.connect(self.audio_gate, self.null_sink)                    # audio to null by default

    def start_record(self, wav_path):
        """Begin writing demodulated audio to WAV."""
        self.current_wav = wav_path
        self.wav_sink = blocks.wavfile_sink(wav_path, 1, int(self.audio_rate), 16)
        self.lock()
        self.disconnect(self.audio_gate, self.null_sink)
        self.connect(self.audio_gate, self.wav_sink)
        self.unlock()
        self.audio_gate.set_k(1.0)
        self.iq_sink.reset()
        self.audio_sink.reset()

    def stop_record(self):
        """Stop writing audio."""
        self.audio_gate.set_k(0.0)
        if self.wav_sink:
            self.lock()
            self.disconnect(self.audio_gate, self.wav_sink)
            self.connect(self.audio_gate, self.null_sink)
            self.unlock()
            self.wav_sink = None

    def get_audio_db(self):
        lvl = self.probe.level()
        return 10 * math.log10(lvl) if lvl > 0 else -120

    def get_iq(self):
        return np.array(self.iq_sink.data(), dtype=np.complex64)

    def get_audio(self):
        return np.array(self.audio_sink.data(), dtype=np.float32)

class WaterfallExplorer(Qt.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Baofeng Waterfall + Recorder")

        # Recorder
        self.rec = NFMRecorder()
        # Waterfall UI
        self.wf = qtgui.waterfall_sink_c(
            1024, firdes.WIN_BLACKMAN_hARRIS,
            self.rec.freq, self.rec.samp_rate, "Waterfall", 1
        )
        self.wf.set_update_time(0.1)
        self.wf.enable_grid(True)
        wf_win = sip.wrapinstance(self.wf.pyqwidget(), Qt.QWidget)

        # Layout
        layout = Qt.QVBoxLayout(self)
        layout.addWidget(wf_win)
        self.setLayout(layout)
        # connect and then start
        self.rec.connect(self.rec.src, self.wf)
        self.rec.start()

        # thresholds
        self.base_db = -30.0
        self.start_delta = 10.0
        self.stop_delta = 5.0
        self.recording = False

        # Poll timer
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(200)

        # Ctrl+C
        signal.signal(signal.SIGINT, lambda *args: Qt.QApplication.quit())

    def poll(self):
        db = self.rec.get_audio_db()
        if not self.recording and db > self.base_db + self.start_delta:
            fname = f"/tmp/baofeng_{int(time.time())}.wav"
            print(f"🔴 Recording start @ {db:.1f} dBFS → {fname}")
            self.rec.start_record(fname)
            self.filename = fname
            self.recording = True

        elif self.recording and db < self.base_db + self.stop_delta:
            print(f"⚫️ Recording stop @ {db:.1f} dBFS")
            self.rec.stop_record()
            wav = self.filename
            iq = self.rec.get_iq()
            audio = self.rec.get_audio()
            print(f"💾 Saved: {wav}")
            threading.Thread(
                target=self.fingerprint_and_rename,
                args=(wav, iq, audio),
                daemon=True
            ).start()
            self.recording = False

    def fingerprint_and_rename(self, wav_path, iq, audio):
        print(f"🧬 Fingerprint start for {wav_path}")
        # Ramp from audio
        mag = np.abs(audio)
        thr = mag.max() * 0.2
        idx = np.where(mag > thr)[0]
        ramp = idx[0] / self.rec.audio_rate if idx.size else 0.0
        # CFO & BW from IQ
        window = iq * np.hamming(len(iq))
        spec = np.fft.fftshift(np.fft.fft(window))
        power = np.abs(spec) ** 2
        freqs = np.fft.fftshift(np.fft.fftfreq(len(iq), d=1/self.rec.samp_rate))
        peak = freqs[np.argmax(power)]
        cfo = peak / 1e3  # kHz
        mask = power > power.max() * 0.1
        bw = ((freqs[mask][-1] - freqs[mask][0]) / 1e3) if mask.any() else 0.0
        new = wav_path.replace(
            ".wav",
            f"_ramp{ramp:.3f}_cfo{cfo:.1f}kHz_bw{bw:.1f}kHz.wav"
        )
        os.rename(wav_path, new)
        print(f"🧬 Renamed → {new}")

    def closeEvent(self, event):
        print("🛑 Exiting...")
        self.rec.stop_record()
        self.rec.stop()
        self.rec.wait()
        event.accept()

if __name__ == "__main__":
    app = Qt.QApplication(sys.argv)
    win = WaterfallExplorer()
    win.resize(800,600)
    win.show()
    sys.exit(app.exec_())

