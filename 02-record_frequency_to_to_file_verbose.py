#!/usr/bin/env python3
from gnuradio import gr, blocks, analog
import osmosdr
import time
import math
from collections import deque

class NFMRecorder(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "Signal-Aware NFM Recorder")

        self.freq = 437.225e6
        self.samp_rate = 2.4e6
        self.audio_rate = 48e3
        self.rf_gain = 40

        self.floor_db = -30.0
        self.trigger_rise = 10.0      # start if signal exceeds floor + this
        self.return_margin = 2.0      # stop if signal returns to floor + margin
        self.drop_below_avg = 15.0    # stop if signal drops this much below avg

        self.rolling_window = deque(maxlen=20)
        self.avg_db = self.floor_db
        self.recording = False

        self.src = osmosdr.source(args="numchan=1 rtl=0")
        self.src.set_sample_rate(self.samp_rate)
        self.src.set_center_freq(self.freq)
        self.src.set_freq_corr(0)
        self.src.set_gain_mode(False)
        self.src.set_gain(self.rf_gain)

        self.squelch = analog.simple_squelch_cc(-60, 1)

        self.nfm = analog.nbfm_rx(
            audio_rate=self.audio_rate,
            quad_rate=self.samp_rate,
            tau=75e-6,
            max_dev=5e3
        )

        # RSSI Probe
        self.mag = blocks.complex_to_mag_squared()
        self.avg = blocks.moving_average_ff(512, 1.0 / 512, 4000, 1)
        self.probe = blocks.probe_signal_f()

        # Always-connected WAV file
        self.filename = f"/tmp/baofeng_{int(time.time())}.wav"
        self.wav_sink = blocks.wavfile_sink(self.filename, 1, int(self.audio_rate), 16)

        # Gate audio: only pass audio when enabled
        self.gate = blocks.multiply_const_ff(0.0)  # 0.0 = mute, 1.0 = pass

        # Flowgraph connections
        self.connect(self.src, self.mag, self.avg, self.probe)
        self.connect(self.src, self.squelch, self.nfm, self.gate, self.wav_sink)

    def compute_rolling_avg(self):
        if not self.rolling_window:
            return self.floor_db
        return sum(self.rolling_window) / len(self.rolling_window)

    def run_and_monitor(self):
        self.start()
        print("Monitoring 437.225 MHz (NFM)...")
        print(f"Output file: {self.filename}")

        try:
            while True:
                level = self.probe.level()
                db = 10 * math.log10(level) if level > 0 else -100

                if not self.recording:
                    if db > (self.floor_db + self.trigger_rise):
                        self.gate.set_k(1.0)
                        self.rolling_window.clear()
                        self.recording = True
                        print(f"🔴 Recording ACTIVE at {db:.2f} dBFS")
                else:
                    self.rolling_window.append(db)
                    avg_db = self.compute_rolling_avg()

                    if db <= (self.floor_db + self.return_margin):
                        self.gate.set_k(0.0)
                        self.recording = False
                        print(f"⚫️ Recording stopped (floor return @ {db:.2f} dBFS)")
                    elif avg_db - db >= self.drop_below_avg:
                        self.gate.set_k(0.0)
                        self.recording = False
                        print(f"⚫️ Recording stopped (drop from avg {avg_db:.2f} → {db:.2f} dBFS)")

                time.sleep(0.25)

        except KeyboardInterrupt:
            print("\nStopped by user.")
            self.stop()
            self.wait()
            print(f"Saved file: {self.filename}")

if __name__ == '__main__':
    tb = NFMRecorder()
    tb.run_and_monitor()


