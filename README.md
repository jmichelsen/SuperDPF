# SuperDPF
The next generation of Digital Picture Frames!

### Specifically designed for use with a Raspberry Pi running Raspbian, but any Linux distro should work just fine as long as the required packages can be installed

Required system packages:
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

### Install instructions
```
apt-get install python3 fib rsync git python3-pip postgresql
```
