from dataclasses import dataclass
from io import SEEK_SET, SEEK_CUR
import logging
from struct import unpack
from typing import BinaryIO, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class SongInfo:
    """
    Payload is raw unsigned 8-bit PCM data
    """
    id: int
    offset: int
    size: int
    rate: Optional[int] = None
    payload: Optional[bytes] = None
    sbng_code_offset: int = -1


class HEMusicExtractor:

    he_version = 80

    def __init__(self, file: BinaryIO):
        self._file = file

    def read_music_headers(self) -> List[SongInfo]:
        """
        Based on scummvm
        Source: SoundHE::setupHEMusicFile
        """

        file = self._file
        he_version = self.he_version

        assert not file.closed

        # Read header
        logger.debug("Reading file header")
        file.seek(0, SEEK_SET)
        if file.read(4) != b'SONG':
            raise RuntimeError("File is not a music container")

        file.seek(4, SEEK_CUR)  # total_size
        assert file.read(4) == b'SGHD'
        header_len: int = unpack('>I', file.read(4))[0]
        if header_len != 40:
            logger.debug("Header length is not 40, he_version < 80")
            he_version = 70

        total_tracks: int = unpack('<I', file.read(4))[0]
        logger.debug(f"Total tracks: {total_tracks}")
        music_start = 56 if he_version >= 80 else 20
        file.seek(music_start, SEEK_SET)

        # Read song info
        logger.debug("Reading songs info")
        songs = []
        for _ in range(total_tracks):
            id_, offset, size = unpack('<3I', file.read(12))
            logger.debug(f"Song id={id_} offset={offset} size={size}")
            songs.append(SongInfo(id_, offset, size))

            file.seek(9 if he_version >= 80 else 13, SEEK_CUR)

        return songs

    def get_music_data(self) -> List[SongInfo]:
        """
        Based on scummvm
        Source: SoundHE::playHESound
        """
        file = self._file
        songs = self.read_music_headers()

        assert not file.closed

        logger.debug("Reading song data")
        for song in songs:
            logger.debug(f"Seeking to song with id {song.id} at {song.offset}")
            file.seek(song.offset, SEEK_SET)
            sound_fmt = file.read(4)
            if sound_fmt != b'DIGI':
                logger.warning(
                    f"Sound format {sound_fmt} for song with id {song.id} "
                    f"isn't supported; skipping"
                )
                continue

            file.seek(song.offset + 22, SEEK_SET)
            rate: int = unpack('<I', file.read(4))[0]

            # Skip DIGI/TALK (8) and HSHD (24) blocks
            file.seek(song.offset + 32, SEEK_SET)
            chunk_header = file.read(4)
            if chunk_header == b'SBNG':
                # There's apparently some "code" packed in here, I'm just
                # skipping past it
                logger.debug("Code header found; skipping")
                song.sbng_code_offset = 40
                code_len = unpack('>I', file.read(4))[0] - 8
                f.seek(code_len, SEEK_CUR)
                # Ensure we've moved ahead to an SDAT chunk
                chunk_header = f.read(4)
            if chunk_header != b'SDAT':
                logger.warning(
                    f"Song with id {song.id} at offset {song.offset} failed a "
                    f"payload header check; skipping"
                )
                continue
            size: int = unpack('>I', file.read(4))[0] - 8
            logger.debug(f"Reading payload with size {size}")
            payload = file.read(size)

            song.rate = rate
            song.payload = payload

        return songs


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    from subprocess import PIPE, Popen
    import sys

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.setLevel('INFO')


    def write_pcm_to_file(
            output_path: Path, payload: bytes, samplerate: int,
            output_options: List[str] = None
    ):
        """
        Write unsigned 8-bit audio data to an audio file.

        :param output_path: path to write audio file
        :param payload: raw PCM samples
        :param samplerate: samplerate of the audio data
        :param output_options: ffmpeg options for output file
        """

        output_options = output_options or []
        ffmpeg = Popen([
            'ffmpeg', '-hide_banner', '-loglevel', 'error',
            '-f', 'u8', '-ar', str(samplerate), '-i', 'pipe:',
            *output_options,
            str(output_path.resolve())
        ], stdin=PIPE)
        logger.info(f"Writing file {output_path.name}")
        out, err = ffmpeg.communicate(payload)
        if err:
            print(f"ffmpeg returned with error ({err})")
        return out


    def write_pcm_to_mp3(
            output_path: Path,
            payload: bytes,
            samplerate: int,
            quality_or_bitrate: Union[int, str] = 0,
            title: str = None,
            artist: str = None,
            album: str = None,
            year: str = None,
            track: int = None,
            comment: str = None
    ):
        """
        Write unsigned 8-bit audio data to an MP3 file.

        :param output_path: path to write MP3 file
        :param payload: raw PCM samples
        :param samplerate: samplerate of the audio data
        :param quality_or_bitrate: if an integer, encode with this VBR quality
            preset, otherwise if a string (like '320k'), encode with CBR
        :param title: track name
        :param artist: track artist
        :param album: album name
        :param year: year created
        :param track: track number in album
        :param comment: comment string
        """

        options = ['-c:a', 'libmp3lame']

        if not (
                quality_or_bitrate is None
                or isinstance(quality_or_bitrate, (int, str))
        ):
            raise TypeError(
                f"quality_or_bitrate must one of type (int, str) or None, got "
                f"{type(quality_or_bitrate)}"
            )
        if isinstance(quality_or_bitrate, int):
            options += ['-q:a', str(quality_or_bitrate)]
        elif isinstance(quality_or_bitrate, str):
            options += ['-b:a', quality_or_bitrate]

        options += ['-metadata', f'title={title}'] if title else []
        options += ['-metadata', f'artist={artist}'] if artist else []
        options += ['-metadata', f'album={album}'] if album else []
        options += ['-metadata', f'date={year}'] if year else []
        options += ['-metadata', f'track={track}'] if track else []
        options += ['-metadata', f'comment={comment}'] if comment else []
        return write_pcm_to_file(output_path, payload, samplerate, options)


    def try_int_coerce(string: str) -> Union[int, str]:
        """Try to convert string to integer, otherwise keep as string"""
        try:
            return int(string)
        except ValueError:
            return string


    parser = argparse.ArgumentParser(
        description="Extract music from Humongous Entertainment game data"
    )
    parser.add_argument(
        'game_data', type=Path,
        help=(
            "Data file containing music to extract. It should always have "
            "an .HE4 file extension (e.g. PUTTZOO.HE4)."
        )
    )
    parser.add_argument(
        'output_dir', type=Path,
        help="Directory to write music files to"
    )
    parser.add_argument(
        '-f', '--format', default='wav', required=False,
        help="Output audio format"
    )
    parser.add_argument(
        '-p', '--filename_prefix', default='Song', required=False,
        help="Prefix to add to filenames"
    )
    parser.add_argument(
        '--use_song_ids', required=False, action='store_true',
        help=(
            "Use the song IDs found in the data file (default is to number "
            "starting at 1 instead)"
        )
    )
    parser.add_argument(
        '-v', '--verbose', required=False, action='store_true',
        help="Display debug info"
    )

    mp3_group = parser.add_argument_group(
        "MP3 Options", "MP3-specific options (set format with -f mp3)"
    )
    mp3_group.add_argument(
        '--mp3_quality', default=1, required=False, type=try_int_coerce,
        help=(
            "Quality or bitrate of MP3 encoding. Either supply an integer to "
            "encode with a variable bitrate quality preset or supply a string "
            "like 320k to encode with a constant bitrate. (default=1)"
        )
    )

    metadata_group = parser.add_argument_group(
        "Metadata Options",
        "Metadata to add to song files (may only work for MP3 files)"
    )
    metadata_group.add_argument(
        '--title_prefix', default='Song ', required=False,
        help=(
            "Prefix to prepend to song IDs in their title metadata (songs are "
            "identified by numbers instead of names)"
        )
    )
    metadata_group.add_argument(
        '--artist', required=False, help="Soundtrack composer"
    )
    metadata_group.add_argument(
        '--album', required=False, help="Album name"
    )
    metadata_group.add_argument(
        '--year', required=False, help="Year released"
    )
    metadata_group.add_argument(
        '--genre', default='Soundtrack', required=False, help="Music genre"
    )
    metadata_group.add_argument(
        '--comment', required=False, help="Comment to add to each song"
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel('DEBUG')

    game_data: Path = args.game_data
    output_dir: Path = args.output_dir
    format: Optional[str] = args.format
    filename_prefix: str = args.filename_prefix
    use_song_ids: bool = args.use_song_ids

    mp3_quality: Union[int, str] = args.mp3_quality

    title_prefix: str = args.title_prefix
    artist: str = args.artist
    album: str = args.album
    year: str = args.year
    comment: str = args.comment

    with game_data.open('rb') as f:
        songs = HEMusicExtractor(f).get_music_data()

    for i, song in enumerate(songs):
        song_name = song.id if use_song_ids else i+1
        filename = output_dir / f'{filename_prefix}{song_name}.{format}'
        if format == 'mp3':
            write_pcm_to_mp3(
                filename, song.payload, song.rate,
                mp3_quality, title=f'{title_prefix}{song_name}', artist=artist,
                album=album, year=year, track=i+1, comment=comment
            )
        else:
            write_pcm_to_file(filename, song.payload, song.rate)
