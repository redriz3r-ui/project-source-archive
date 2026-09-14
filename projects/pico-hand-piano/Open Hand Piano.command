#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
pico_python="/Applications/Thonny.app/Contents/Frameworks/Python.framework/Versions/3.14/bin/python3.14"
if [ ! -x "$pico_python" ]; then
  echo "This saved build uses the Python runtime bundled with Thonny on this Mac."
  echo "Install Thonny from https://thonny.org if it has been removed."
  read -r -p "Press Return to close."
  exit 1
fi
"$pico_python" hand_slider.py
pico_result=$?
if [ "$pico_result" -ne 0 ]; then
  read -r -p "The app stopped with an error above. Press Return to close."
fi
exit "$pico_result"
