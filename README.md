# Humongous Entertainment Music Extractor

Humongous Entertainment (HE) Music Extractor is a tool to extract music from
HE games. Songs are stored in a monolithic data file with a `.HE4` file
extension.

**DISCLAIMER**: I do not support or endorse piracy. This tool was developed
using data from HE games I purchased myself [on Steam](https://store.steampowered.com/sub/42723/)
and by reading source code of the GPL-licensed [ScummVM](https://github.com/scummvm/scummvm)
which these games run on.

## Table of Contents

- [Install](#install)
- [Usage](#usage)
- [License](#license)

## Install

To get started, clone the repo.

```shell
git clone https://github.com/hawkpath/he-music-extractor.git
cd he-music-extractor
```

You will need [Python](https://python.org) and a copy of [FFmpeg](https://ffmpeg.org/)
for encoding audio. Make sure the ffmpeg binary is on your path environment
variable before running this tool.

## Usage

Basic usage (outputs wav files):

```shell
python HE_music_extractor.py "C:\Program Files (x86)\Steam\steamapps\common\Freddi Fish 2\Freddi2.he4" "C:\Users\Me\Music\FreddiFish2"
```

Output MP3 files with ID3v2 tags (the `^`s on Windows let us continue the command on
the next line -- they're not required):

```shell
python HE_music_extractor.py -f mp3 ^
    --artist "Tom McGurk" ^
    --album "Freddi Fish 2: The Case of the Haunted Schoolhouse" ^
    --year 1996 ^
    "C:\Program Files (x86)\Steam\steamapps\common\Freddi Fish 2\Freddi2.he4" ^
    "C:\Users\Me\Music\Freddi Fish 2 Soundtrack"
```

To see more info and all available options:

```shell
python HE_music_extractor.py --help
```

## License

[MIT © Hawkpath.](LICENSE)
