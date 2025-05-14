#!/usr/bin/env python3
from gnuradio import gr, blocks, analog
import osmosdr
import time
import math
import os
from collections import deque

class NFMRecorder(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "Rolling WAV File Recorder")

        self.freq = 437.225e6
        self.samp_rate = 2.4e6
        self.audio_rate = 48e3
        self.rf_gain = 40

        self.floor_db = -30.0
        self.trigger_rise = 10.0
        self.return_margin = 2.0
        self.drop_below_avg = 15.0

        self.rolling_window = deque(maxlen=20)
        self.recording = False
        self.current_filename = "/tmp/baofeng_current.wav"
        self.wav_sink = None

        # SDR setup
        self.src = osmosdr.source(args="numchan=1 rtl=0")
        self.src.set_sample_rate(self.samp_rate)
        self.src.set_center_freq(self.freq)
        self.src.set_freq_corr(0)
        self.src.set_gain_mode(False)
        self.src.set_gain(self.rf_gain)

        # Signal chain
        self.squelch = analog.simple_squelch_cc(-60, 1)
        self.nfm = analog.nbfm_rx(
            audio_rate=self.audio_rate,
            quad_rate=self.samp_rate,
            tau=75e-6,
            max_dev=5e3
        )

        self.mag = blocks.complex_to_mag_squared()
        self.avg = blocks.moving_average_ff(512, 1.0 / 512, 4000, 1)
        self.probe = blocks.probe_signal_f()

        self.gate = blocks.multiply_const_ff(0.0)

        self.wav_sink = blocks.wavfile_sink(self.current_filename, 1, int(self.audio_rate), 16)

        # Connect graph
        self.connect(self.src, self.mag, self.avg, self.probe)
        self.connect(self.src, self.squelch, self.nfm, self.gate, self.wav_sink)

    def compute_rolling_avg(self):
        if not self.rolling_window:
            return self.floor_db
        return sum(self.rolling_window) / len(self.rolling_window)

    def close_and_rotate_file(self):
        self.gate.set_k(0.0)
        time.sleep(0.2)
        final_name = f"/tmp/baofeng_{int(time.time())}.wav"

        try:
            if os.path.exists(self.current_filename):
                size = os.path.getsize(self.current_filename)
                if size > 44:
                    os.rename(self.current_filename, final_name)
                    print(f"⚫️ Saved recording → {final_name}")
                else:
                    os.remove(self.current_filename)
                    print("⚠️ Deleted empty file.")
        except Exception as e:
            print(f"⚠️ File handling error: {e}")

        # Reset the wav sink
        self.lock()
        try:
            self.disconnect(self.gate, self.wav_sink)
            self.wav_sink = blocks.wavfile_sink(self.current_filename, 1, int(self.audio_rate), 16)
            self.connect(self.gate, self.wav_sink)
        finally:
            self.unlock()

    def run_and_monitor(self):
        self.start()
        print("Monitoring 437.225 MHz (NFM)...")

        try:
            while True:
                level = self.probe.level()
                db = 10 * math.log10(level) if level > 0 else -100
                self.rolling_window.append(db)
                avg_db = self.compute_rolling_avg()

                if not self.recording and db > self.floor_db + self.trigger_rise:
                    self.gate.set_k(1.0)
                    self.recording = True
                    self.rolling_window.clear()
                    print(f"🔴 Recording started at {db:.2f} dBFS")

                elif self.recording:
                    if db <= self.floor_db + self.return_margin or avg_db - db >= self.drop_below_avg:
                        self.close_and_rotate_file()
                        self.recording = False

                time.sleep(0.25)

        except KeyboardInterrupt:
            print("\n[CTRL+C] Shutting down...")
            if self.recording:
                self.close_and_rotate_file()
            self.stop()
            self.wait()

if __name__ == '__main__':
    tb = NFMRecorder()
    tb.run_and_monitor()


