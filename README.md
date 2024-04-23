This is a fixed forked version from other vectorator versions, this prevents any crashes with the robot and ensures every bit of control can take place. This also uses open weather api to get weather and forecast. You can also include your own rss news feed yourself within the config.py which includes other configurations.

Steps of installation are pretty straight forward, ensure your wire-pod and you have wirepod-vector-python-sdk installed and set up.

Do not worry about changing the texts in the local files, all local files will be read before it downloads any from any website or github.

1. Git clone this repo to a folder, ensure you do it in the root if using raspberry pi or any other linux os.
2. Use cd ~/vectorator
3. Use python3 vectorator.py --serial <robot serial number> (Without the <>)

This ensures you can specify which robot on your wirepod to connect too and control. 
