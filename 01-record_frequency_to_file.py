#!/usr/bin/env python3
from gnuradio import gr, blocks, analog
import osmosdr
import time

class NFMRecorder(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "Baofeng NFM Recorder")

        self.freq = 437.225e6
        self.samp_rate = 2.4e6
        self.audio_rate = 48e3
        self.rf_gain = 40
        self.filename = f"/tmp/baofeng_{int(time.time())}.wav"
        self.squelch_threshold = -60  # dB

        self.src = osmosdr.source(args="numchan=1 rtl=0")
        self.src.set_sample_rate(self.samp_rate)
        self.src.set_center_freq(self.freq)
        self.src.set_freq_corr(0)
        self.src.set_gain_mode(False)
        self.src.set_gain(self.rf_gain)

        # Squelch
        self.squelch = analog.simple_squelch_cc(self.squelch_threshold, 1)

        # NFM demodulator
        self.nfm = analog.nbfm_rx(
            audio_rate=self.audio_rate,
            quad_rate=self.samp_rate,
            tau=75e-6,
            max_dev=5e3
        )

        # Save audio to WAV
        self.wav_sink = blocks.wavfile_sink(self.filename, 1, int(self.audio_rate), 16)

        self.connect(self.src, self.squelch, self.nfm, self.wav_sink)

if __name__ == '__main__':
    tb = NFMRecorder()
    print("Monitoring 437.225 MHz (NFM)...")
    try:
        tb.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\nSaved: {tb.filename}")
        tb.stop()
        tb.wait()


