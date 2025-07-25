# ENTROPY_SRC HWIP Technical Specification

[`entropy_src`](https://reports.opentitan.org/hw/ip/entropy_src/dv/latest/report.html):
![](https://dashboards.lowrisc.org/badges/dv/entropy_src/test.svg)
![](https://dashboards.lowrisc.org/badges/dv/entropy_src/passing.svg)
![](https://dashboards.lowrisc.org/badges/dv/entropy_src/functional.svg)
![](https://dashboards.lowrisc.org/badges/dv/entropy_src/code.svg)

# Overview

This document specifies ENTROPY_SRC hardware IP functionality.
This module conforms to the [Comportable guideline for peripheral functionality.](../../../doc/contributing/hw/comportability/README.md)

## Features

- This revision provides an interface to an external physical random noise generator (also referred to as a physical true random number generator or PTRNG).
The PTRNG external source is a physical true random noise source.
A noise source and its relation to an entropy source are defined by [SP 800-90B.](https://csrc.nist.gov/publications/detail/sp/800-90b/final)
- Configurable noise source bus width, supporting 4-256 bits.
- A set of registers is provided for firmware to obtain entropy bits.
- Interrupts are supported:
  - Entropy bits are available for firmware consumption.
  - The internal health tests have detected a test failure.
  - An internal FIFO error has occurred.
- Two health checks that are defined by SP 800-90B are performed by this revision: Repetition Count and Adaptive Proportion tests.
- Two additional hardware health checks are performed by this revision: Bucket and Markov tests.
- Firmware-defined (mailbox-based) and vendor-defined health checks are also supported.
- A health check failure alert is supported by this revision.

## Description

This IP block provides an entropy source that is capable of using a PTRNG (Physical True Random Number Generator) noise source to generate random values in a manner that is compliant both with FIPS (though NIST SP 800-90B) and CC (AIS31) recommendations.

At a high-level, the ENTROPY_SRC block, when enabled, will continuously collect entropy bits from the PTRNG noise source, perform health tests on the collected entropy bits, pack them, send them through a conditioning unit, and finally store them into a FIFO.
The content of this FIFO can either be sent out through a hardware interface or alternatively (but not simultaneously) read by firmware over the TL-UL bus.
The random values generated by the ENTROPY_SRC block serve as non-deterministic seeds for the CSRNG block.
The outputs of the CSRNG are then used either directly by firmware or are distributed to other hardware blocks through the Entropy Distribution Network.

In the terms of AIS31 classes, this block is meant to satisfy the requirements for a PTG.2 class physical entropy source, with "internal" entropy (an AIS31 term, meaning the min-entropy as measured just *before the output pins*) exceeding 0.997 entropy-bits/output-bit.
In NIST terms, this block satisfies the requirements for a "full-entropy" source, which requires even smaller deviations from ideal entropy, at the level of less than one part in 2<sup>64</sup>.

The raw noise bits from the PTRNG noise source (external to this block) are subjected to a sequence of health-checks to screen the raw signals for statistical defects which would cause any significant deviations from ideal entropy at the output of the conditioning block.
These tests include:
- The Repetition Count test, which screens for stuck-bits, or a complete failure of the PTRNG noise source,
- The Adaptive Proportion test, which screens for statistical bias in the number of 1's or 0's output by the noise source,
- The "Bucket Test", which looks for correlations between the individual noise channels that the external noise source concatenates together to produce the raw noise sequence,
- The "Markov Test", which looks for unexpected first-order temporal correlations between bits output by the individual noise channels,
- The "Mailbox Test", in which raw-noise data is transferred to firmware in contiguous blocks, so that firmware can perform custom tests, and signal a failure through the same path as the other tests, and
- Optional Vendor Specific tests, which allow silicon creators to extend the health checks by adding a top-level block external to this IP.

The Repetition Count and Adaptive Proportion test are specifically recommended by SP 800-90B, and are implemented in accordance with those recommendations.
In FIPS/CC compliant mode, all checks except the Repetition Count test are performed on a fixed window of data of configurable size, by default consisting of 2048 bits each.
Per the definition in SP 800-90B, the Repetition Count test does not operate on a fixed window.
The repetition count test fails if any sequence of bits continuously asserts the same value for too many samples, as determined by the programmable threshold, regardless of whether that sequence crosses any window boundaries.
The thresholds for these tests should be chosen to achieve a low false-positive rate (&alpha;) given a conservative estimate of the manufacturing tolerances of the PTRNG noise source.
The combined choice of threshold and window size then determine the false-negative rate (&beta;), or the probability of missing statistical defects at any particular magnitude.

When the IP is disabled by clearing the [`MODULE_ENABLE`](./doc/registers.md#MODULE_ENABLE) register, all health checks are disabled and all counters internal to the health checks are reset.

When operating in FIPS/CC compliant mode, the raw outputs of the PTRNG noise source are passed through a conditioning function based on a suitable secure hash function (SHA-3) which has been vetted by NIST to meet the stringent requirements for a full-entropy source.
In order to compensate for the fact our tests (like *all* realistic statistical tests) have finite resolution for detecting defects, we conservatively use 2048 bits of PTRNG noise source to construct each 384 bit conditioned entropy sample by default.
The effectively used number of bits is equal to the configured health test window size.
When passed through the conditioning block, the resultant entropy stream will be full entropy unless the PTRNG noise source has encountered some statistical defect serious enough to reduce the raw min-entropy to a level below 0.375 bits of entropy per output bit.
We choose this level as our definition of "non-tolerable statistical defects" for the purposes of evaluating this system under AIS31.
Given this definition of "non-tolerable defects", the health-checks as implemented for this block will almost certainly detect any of the previously mentioned defects in a single iteration of the health checks (i.e. such serious defects will be detected with very low &beta;).

In addition to the brief, low-latency health checks, various long-term statistics are accumulated in registers for additional diagnostic purposes or for in-depth analysis.

There are two modes in which entropy bits are delivered, boot-time / bypass mode and FIPS/CC compliant mode.
Boot-time / bypass mode will deliver bits sooner for specific on-boot obfuscation applications, though the bits may not yet have been subjected to the same level of startup health checks required for FIPS or CC compliance.

In boot-time / bypass mode health checks only operate on a window of 384 bits.
The boot-time / bypass mode health checks are the same as the FIPS/CC health-checks, though with different thresholds.
They are sensitive to the same types of statistical defects, though at reduced statistical resolution.
With suitable thresholds, the boot-time health checks can be operate both with low false-alarm rates (low &alpha;), while still confirming with low &beta; that the total entropy of the first seed contains at least 80 bits of total entropy.
During start up the initial 384 bits are held in a buffer until the boot-time start-up health checks are performed.
Storing the seed in this buffer, allows this seed to released to the CSRNG immediately after the entropy has been confirmed.

Boot-time / bypass mode also has the feature that it bypasses the SHA conditioning function, as only 384 bits are used in the initial boot-time seed.

For maximal flexibility in normal operation, the conditioning function can also be implemented by firmware.
When this firmware conditioning feature is activated, data read directly out of the noise source can be re-inserted into the entropy pipeline via a TL-UL register after it has been processed by firmware.
It should be noted that this firmware algorithm must be vetted by NIST to satisfy the requirements for a full-entropy source.
This feature can also be disabled for security purposes, either by locking the feature via the [`REGWEN`](./doc/registers.md#regwen) register at boot, or by a write to one-time programmable (OTP) memory.

## Compatibility
This IP block does not have any direct hardware compatibility requirements.
However, the general design of this block follows the overall NIST recommendations, as described by SP 800-90B.
