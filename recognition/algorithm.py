#!/usr/bin/python3

import numpy as np
from typing import List, Optional, Any
from copy import deepcopy

from recognition.signature_format import DecodedMessage, FrequencyPeak, FrequencyBand

HANNING_MATRIX = np.hanning(2050)[1:-1]


class RingBuffer:
    def __init__(self, buffer_size: int, default_value: Any = None):
        self.buffer_size = buffer_size
        self.position = 0
        self.num_written = 0
        if isinstance(default_value, (int, float)):
            self.data = np.full(buffer_size, default_value, dtype=float)
        else:
            self.data = np.array([deepcopy(default_value) for _ in range(buffer_size)], dtype=object)

    def append(self, value: Any):
        self.data[self.position] = value
        self.position = (self.position + 1) % self.buffer_size
        self.num_written += 1

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            return self.data[idx]
        return self.data[idx % self.buffer_size]


class SignatureGenerator:
    def __init__(self):
        self.input_pending_processing: np.ndarray = np.array([], dtype=np.int16)
        self.samples_processed = 0

        self.ring_buffer_of_samples = RingBuffer(2048, 0)
        self.fft_outputs = RingBuffer(256, np.zeros(1025, dtype=float))
        self.spread_ffts_output = RingBuffer(256, np.zeros(1025, dtype=float))

        self.MAX_TIME_SECONDS = 3.1
        self.MAX_PEAKS = 255

        self.next_signature = DecodedMessage()
        self.next_signature.sample_rate_hz = 16000
        self.next_signature.number_samples = 0
        self.next_signature.frequency_band_to_sound_peaks = {}

    def feed_input(self, s16le_mono_samples: List[int]):
        self.input_pending_processing = np.concatenate((self.input_pending_processing, np.array(s16le_mono_samples, dtype=np.int16)))

    def get_next_signature(self) -> Optional[DecodedMessage]:
        if len(self.input_pending_processing) - self.samples_processed < 128:
            return None

        while (len(self.input_pending_processing) - self.samples_processed >= 128 and
               (self.next_signature.number_samples / self.next_signature.sample_rate_hz < self.MAX_TIME_SECONDS or
                sum(len(peaks) for peaks in self.next_signature.frequency_band_to_sound_peaks.values()) < self.MAX_PEAKS)):
            self.process_input(self.input_pending_processing[self.samples_processed:self.samples_processed + 128])
            self.samples_processed += 128

        returned_signature = self.next_signature

        self.next_signature = DecodedMessage()
        self.next_signature.sample_rate_hz = 16000
        self.next_signature.number_samples = 0
        self.next_signature.frequency_band_to_sound_peaks = {}

        self.ring_buffer_of_samples = RingBuffer(2048, 0)
        self.fft_outputs = RingBuffer(256, np.zeros(1025, dtype=float))
        self.spread_ffts_output = RingBuffer(256, np.zeros(1025, dtype=float))

        return returned_signature

    def process_input(self, s16le_mono_samples: np.ndarray):
        self.next_signature.number_samples += len(s16le_mono_samples)

        for i in range(0, len(s16le_mono_samples), 128):
            self.do_fft(s16le_mono_samples[i:i + 128])
            self.do_peak_spreading_and_recognition()

    def do_fft(self, batch_of_128_s16le_mono_samples: np.ndarray):
        start = self.ring_buffer_of_samples.position
        end = (start + len(batch_of_128_s16le_mono_samples)) % 2048

        if start < end:
            self.ring_buffer_of_samples.data[start:end] = batch_of_128_s16le_mono_samples
        else:
            part = 2048 - start
            self.ring_buffer_of_samples.data[start:] = batch_of_128_s16le_mono_samples[:part]
            self.ring_buffer_of_samples.data[:end] = batch_of_128_s16le_mono_samples[part:]

        self.ring_buffer_of_samples.position = end
        self.ring_buffer_of_samples.num_written += len(batch_of_128_s16le_mono_samples)

        excerpt = np.concatenate((self.ring_buffer_of_samples.data[self.ring_buffer_of_samples.position:],
                                  self.ring_buffer_of_samples.data[:self.ring_buffer_of_samples.position]))

        fft_results = np.fft.rfft(HANNING_MATRIX * excerpt)
        fft_magnitude = (fft_results.real ** 2 + fft_results.imag ** 2) / (1 << 17)
        fft_magnitude = np.maximum(fft_magnitude, 1e-10)

        self.fft_outputs.append(fft_magnitude)

    def do_peak_spreading_and_recognition(self):
        self.do_peak_spreading()
        if self.spread_ffts_output.num_written >= 46:
            self.do_peak_recognition()

    def do_peak_spreading(self):
        spread_last_fft = self.fft_outputs[self.fft_outputs.position - 1].copy()

        spread_last_fft[:-2] = np.maximum.reduce([spread_last_fft[:-2], spread_last_fft[1:-1], spread_last_fft[2:]])

        for former_fft_num in [-1, -3, -6]:
            former_fft_output = self.spread_ffts_output[self.spread_ffts_output.position + former_fft_num]
            np.maximum(former_fft_output, spread_last_fft, out=former_fft_output)

        self.spread_ffts_output.append(spread_last_fft)

    def do_peak_recognition(self):
        fft_minus_46 = self.fft_outputs[self.fft_outputs.position - 46]
        fft_minus_49 = self.spread_ffts_output[self.spread_ffts_output.position - 49]

        bins = range(10, 1015)
        for bin_position in bins:
            if (fft_minus_46[bin_position] >= 1/64 and
                    fft_minus_46[bin_position] >= fft_minus_49[bin_position - 1]):

                max_neighbor = max(fft_minus_49[bin_position + offset] for offset in [-10, -7, -4, -3, 1, 2, 5, 8])

                if fft_minus_46[bin_position] > max_neighbor:
                    max_neighbor_other = max([
                        self.spread_ffts_output[(self.spread_ffts_output.position + offset) % self.spread_ffts_output.buffer_size][bin_position - 1]
                        for offset in [-53, -45, *range(165, 201, 7), *range(214, 250, 7)]
                    ])

                    if fft_minus_46[bin_position] > max_neighbor_other:
                        fft_number = self.spread_ffts_output.num_written - 46

                        peak_mag = np.log(max(1/64, fft_minus_46[bin_position])) * 1477.3 + 6144
                        peak_mag_before = np.log(max(1/64, fft_minus_46[bin_position - 1])) * 1477.3 + 6144
                        peak_mag_after = np.log(max(1/64, fft_minus_46[bin_position + 1])) * 1477.3 + 6144

                        peak_var_1 = peak_mag * 2 - peak_mag_before - peak_mag_after
                        peak_var_2 = (peak_mag_after - peak_mag_before) * 32 / peak_var_1

                        corrected_bin = bin_position * 64 + peak_var_2

                        frequency_hz = corrected_bin * (16000 / 2 / 1024 / 64)

                        if frequency_hz < 250:
                            continue
                        elif frequency_hz < 520:
                            band = FrequencyBand._250_520
                        elif frequency_hz < 1450:
                            band = FrequencyBand._520_1450
                        elif frequency_hz < 3500:
                            band = FrequencyBand._1450_3500
                        elif frequency_hz <= 5500:
                            band = FrequencyBand._3500_5500
                        else:
                            continue

                        if band not in self.next_signature.frequency_band_to_sound_peaks:
                            self.next_signature.frequency_band_to_sound_peaks[band] = []

                        self.next_signature.frequency_band_to_sound_peaks[band].append(
                            FrequencyPeak(fft_number, int(peak_mag), int(corrected_bin), 16000)
                        )