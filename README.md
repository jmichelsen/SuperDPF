# SuperDPF
The next generation of Digital Picture Frames!

### Specifically designed for use with a Raspberry Pi running Raspbian, but any Linux distro should work just fine as long as the required packages can be installed

Required system packages:
8GB SD card (raspien-lite and system packages require ~2GB space but you'll want extra space for picture storage)
fbi, rsync, git, django, postgresql, pip, python3, fim

http://www.nongnu.org/fbi-improved/#docs

#### Features:
- On boot, show pictures in random order (fbi -au)
- sync pictures from rsync server/api/flickr/google-photos/dropbox/amazon?
- web interface for managing pictures, changing frame settings (display speed, automatic idle/off times)
- physical buttons for; back, forward, remove, sleep/power
- voice commands for the same controls
- remove picture from frame and add filename to exclude list so rsync doesn't sync it on next sync
- first run wizard for initial setup (set wireless network info, keyboard map, sleep intervals, voice commands, apis)
- use twitter for communication to owner- DM IP to owner on boot, DM status updates, etc
- create random hostname if one is not provided in wizard

### Install instructions
```
apt-get install fbi git python-pip libjpeg-dev
```
if you choose to use fim instead of fbi, you will need packages: libexif-dev libreadline5 libgif-dev libtiff-dev flex bison
```
git clone https://github.com/jmichelsen/SuperDPF.git && cd SuperDPF
```
```
sudo pip install virtualenv virtualenvwrapper
```
```
echo "source /usr/local/bin/virtualenvwrapper.sh" >>  ~/.bashrc && source ~/.bashrc
```
```
mkvirtualenv sdpf
```
```
pip install -r requirements.pip
```

Probably the best way to do this this time is by using aws s3 sync. Create an album in google photos, download it locally, sync to aws, have the frame sync with aws periodically.
