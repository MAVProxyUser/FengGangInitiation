# FengGangInitiation
Learning to observe, and record various mainstream Chinese radios via Gnuradio. I suck at Gnuradio, so decided to have ChatGPT help me through some random concepts. 

Handsets used for testing: 
Baofeng UV-32 - https://www.amazon.com/dp/B0F1F6Q9RZ<br>
Baofeng DM-32UV - https://www.amazon.com/dp/B0F1FBR4YJ<br>
Tidradio TD-H8 - https://www.amazon.com/dp/B0C27VBC5J<br>
Radtel RT-4D  - https://www.amazon.com/dp/B0DMF898GV<br>

The first example simply raw records the frequency to a wav file. 
```
ubuntu@ubuntu:~/FengGangInitiation$ ./01-record_frequency_to_file.py  
gr-osmosdr 0.2.0.0 (0.2.0) gnuradio 3.8.1.0
built-in source types: file osmosdr fcd rtl rtl_tcp uhd miri hackrf bladerf rfspace airspy airspyhf soapy redpitaya freesrp 
Using device #0 Realtek RTL2838UHIDIR SN: 1004
Found Rafael Micro R820T tuner
[R82XX] PLL not locked!
[R82XX] PLL not locked!
len(audio_taps) = 11563
Monitoring 437.225 MHz (NFM)...
Allocating 15 zero-copy buffers
^C
Saved: /tmp/baofeng_1747233797.wav
```

THe next example just adds a bit of verbosity to the first exaample

```
ubuntu@ubuntu:~/FengGangInitiation$ ./02-record_frequency_to_file_verbose.py
gr-osmosdr 0.2.0.0 (0.2.0) gnuradio 3.8.1.0
built-in source types: file osmosdr fcd rtl rtl_tcp uhd miri hackrf bladerf rfspace airspy airspyhf soapy redpitaya freesrp 
Using device #0 Realtek RTL2838UHIDIR SN: 1004
Found Rafael Micro R820T tuner
[R82XX] PLL not locked!
[R82XX] PLL not locked!
len(audio_taps) = 11563
Allocating 15 zero-copy buffers
Monitoring 437.225 MHz (NFM)...
Output file: /tmp/baofeng_1747233899.wav
🔴 Recording ACTIVE at 1.47 dBFS
⚫️ Recording stopped (floor return @ -33.16 dBFS)
🔴 Recording ACTIVE at 2.76 dBFS
⚫️ Recording stopped (floor return @ -32.74 dBFS)
^C
Stopped by user.
Saved file: /tmp/baofeng_1747233899.wav
```

Next we add multi file output support
```
ubuntu@ubuntu:~/FengGangInitiation$ ./03-record_frequency_to_multifile_verbose.py
gr-osmosdr 0.2.0.0 (0.2.0) gnuradio 3.8.1.0
built-in source types: file osmosdr fcd rtl rtl_tcp uhd miri hackrf bladerf rfspace airspy airspyhf soapy redpitaya freesrp 
Using device #0 Realtek RTL2838UHIDIR SN: 1004
Found Rafael Micro R820T tuner
[R82XX] PLL not locked!
[R82XX] PLL not locked!
len(audio_taps) = 11563
Allocating 15 zero-copy buffers
Monitoring 437.225 MHz (NFM)...
🔴 Recording started at 1.78 dBFS
⚫️ Saved recording → /tmp/baofeng_1747234399.wav
Allocating 15 zero-copy buffers
🔴 Recording started at 0.49 dBFS
⚫️ Saved recording → /tmp/baofeng_1747234404.wav
Allocating 15 zero-copy buffers
🔴 Recording started at 1.43 dBFS
⚫️ Saved recording → /tmp/baofeng_1747234408.wav
Allocating 15 zero-copy buffers
```

To have a tighter audio cutoff we use ZCR (Zero-Crossing Rate)
```
ubuntu@ubuntu:~/FengGangInitiation$ ./working_waterfall.py 
gr-osmosdr 0.2.0.0 (0.2.0) gnuradio 3.8.1.0
built-in source types: file osmosdr fcd rtl rtl_tcp uhd miri hackrf bladerf rfspace airspy airspyhf soapy redpitaya freesrp 
Using device #0 Realtek RTL2838UHIDIR SN: 1004
Found Rafael Micro R820T tuner
[R82XX] PLL not locked!
[R82XX] PLL not locked!
len(audio_taps) = 11563
Allocating 15 zero-copy buffers
Allocating 15 zero-copy buffers
🔴 Recording ACTIVE at 2.12 dBFS
⚫️ Recording stopped (ZCR=0.90)
Allocating 15 zero-copy buffers
💾 Saved file: /tmp/baofeng_1747234447.wav
Allocating 15 zero-copy buffers
🔴 Recording ACTIVE at 2.72 dBFS
⚫️ Recording stopped (ZCR=1.00)
Allocating 15 zero-copy buffers
💾 Saved file: /tmp/baofeng_1747234452.wav
```

Next we add fingerprints based on power rampup, carrier frequency offset, and bandwidth characteristics of the radio that keyed up
```
ubuntu@ubuntu:~/FengGangInitiation$ ./05-record_frequency_to_multifile_ZCR_waterfall_fingerprint.py 
gr-osmosdr 0.2.0.0 (0.2.0) gnuradio 3.8.1.0
built-in source types: file osmosdr fcd rtl rtl_tcp uhd miri hackrf bladerf rfspace airspy airspyhf soapy redpitaya freesrp 
Using device #0 Realtek RTL2838UHIDIR SN: 1004
Found Rafael Micro R820T tuner
[R82XX] PLL not locked!
[R82XX] PLL not locked!
len(audio_taps) = 11563
Allocating 15 zero-copy buffers
🔴 Recording start @ 0.9 dBFS → /tmp/baofeng_1747234676.wav
Allocating 15 zero-copy buffers
⚫️ Recording stop @ -33.2 dBFS
Allocating 15 zero-copy buffers
💾 Saved: /tmp/baofeng_1747234676.wav
🧬 Fingerprint start for /tmp/baofeng_1747234676.wav
🧬 Renamed → /tmp/baofeng_1747234676_ramp1.282_cfo-0.2kHz_bw1.4kHz.wav
🔴 Recording start @ 0.2 dBFS → /tmp/baofeng_1747234686.wav
Allocating 15 zero-copy buffers
⚫️ Recording stop @ -32.9 dBFS
Allocating 15 zero-copy buffers
💾 Saved: /tmp/baofeng_1747234686.wav
🧬 Fingerprint start for /tmp/baofeng_1747234686.wav
🔴 Recording start @ 0.6 dBFS → /tmp/baofeng_1747234693.wav
Allocating 15 zero-copy buffers
🧬 Renamed → /tmp/baofeng_1747234686_ramp1.126_cfo0.1kHz_bw0.0kHz.wav
⚫️ Recording stop @ -32.9 dBFS
Allocating 15 zero-copy buffers
💾 Saved: /tmp/baofeng_1747234693.wav
🧬 Fingerprint start for /tmp/baofeng_1747234693.wav
🧬 Renamed → /tmp/baofeng_1747234693_ramp1.746_cfo0.7kHz_bw1.1kHz.wav
O
```


