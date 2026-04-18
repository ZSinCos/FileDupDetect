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
                metadata.title = self._get_tag(tags, ['TIT2', 'title', '\xa9nam'])
                metadata.artist = self._get_tag(tags, ['TPE1', 'artist', '\xa9ART'])
                metadata.album = self._get_tag(tags, ['TALB', 'album', '\xa9alb'])

            return metadata

        except Exception as e:
            print(f"Error extracting metadata from {file_path}: {e}")
            return None

    def _get_tag(self, tags, keys):
        for key in keys:
            if tags is not None:
                try:
                    if isinstance(tags, dict):
                        value = tags.get(key)
                    else:
                        value = getattr(tags, key, None)

                    if value:
                        if isinstance(value, list):
                            return str(value[0])
                        return str(value)
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