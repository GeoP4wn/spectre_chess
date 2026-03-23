# Spectre Chess
---
## Overview
---
This is very much still a work in progress. The best place to start is the technical report (particularly the pictures at the end of the document) and the other documents in the docs folder.

This project is designed to be a robotic chessboard constrained to an external height of 60mm. It features an H-bot gantry to move an electromagnet, which in turn moves the chess pieces.
The main computing is done by a Raspberry Pi. The Raspberry Pi controls two ESP32s. One is responsible for the motors and magnets, the other is responsible for the sensors, LEDs and buttons.


AI Disclosure: Generative AI was used to build the basic structure and async loop of the codebase
