import os
import hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import mutagen


SUPPORTED_FORMATS = {'.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma'}


@dataclass
class AudioMetadata:
    file_path: str
    file_name: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    duration: Optional[float] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    file_size: int = 0
    file_hash: Optional[str] = None
    fingerprint: Optional[str] = None
    album_cover: Optional[bytes] = None
    lyrics: Optional[str] = None


class AudioScanner:
    def __init__(self):
        self.supported_formats = SUPPORTED_FORMATS

    def scan_folder(self, folder_path: str) -> list[AudioMetadata]:
        audio_files = []
        folder = Path(folder_path)

        if not folder.exists():
            return audio_files

        for root, dirs, files in os.walk(folder):
            for file in files:
                file_path = os.path.join(root, file)
                ext = Path(file).suffix.lower()

                if ext in self.supported_formats:
                    metadata = self.extract_metadata(file_path)
                    if metadata:
                        audio_files.append(metadata)

        return audio_files

    def extract_metadata(self, file_path: str) -> Optional[AudioMetadata]:
        try:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)

            metadata = AudioMetadata(
                file_path=file_path,
                file_name=file_name,
                file_size=file_size
            )

            audio = mutagen.File(file_path)
            if audio is not None:
                if hasattr(audio, 'info'):
                    metadata.duration = getattr(audio.info, 'length', None)
                    metadata.bitrate = getattr(audio.info, 'bitrate', None)
                    metadata.sample_rate = getattr(audio.info, 'sample_rate', None)

                tags = audio.tags or {}
                metadata.title = self._get_tag(audio, ['TIT2', 'title', '\xa9nam']) or audio.get('title') or None
                metadata.artist = self._get_tag(audio, ['TPE1', 'artist', '\xa9ART']) or audio.get('artist') or None
                metadata.album = self._get_tag(audio, ['TALB', 'album', '\xa9alb']) or audio.get('album') or None

                metadata.album_cover = self._get_album_cover(audio)
                metadata.lyrics = self._get_lyrics(audio)

            return metadata

        except Exception as e:
            print(f"Error extracting metadata from {file_path}: {e}")
            return None

    def _get_tag(self, audio, keys):
        for key in keys:
            try:
                value = audio.get(key)
                if value:
                    if hasattr(value, 'text'):
                        return value.text[0] if value.text else None
                    elif isinstance(value, list):
                        return str(value[0])
                    return str(value)
            except:
                pass
        return None

    def _get_album_cover(self, audio) -> Optional[bytes]:
        try:
            for key in ['APIC:', 'cover', 'Covr']:
                try:
                    value = audio.get(key)
                    if value:
                        if hasattr(value, 'data'):
                            return value.data
                        elif isinstance(value, list) and len(value) > 0:
                            if hasattr(value[0], 'data'):
                                return value[0].data
                        elif isinstance(value, bytes):
                            return value
                except:
                    pass
        except:
            pass
        return None

    def _get_lyrics(self, audio) -> Optional[str]:
        for key in ['USLT::eng', 'USLT', 'lyrics', '\xa9lyr']:
            try:
                value = audio.get(key)
                if value:
                    if hasattr(value, 'text'):
                        return str(value.text)
                    elif isinstance(value, list):
                        return str(value[0])
                    elif isinstance(value, str):
                        return value
            except:
                pass
        return None

    def calculate_hash(self, file_path: str, algorithm: str = 'md5') -> Optional[str]:
        try:
            hash_func = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            print(f"Error calculating hash for {file_path}: {e}")
            return None