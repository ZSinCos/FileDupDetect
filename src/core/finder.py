from dataclasses import dataclass
from typing import Optional
from collections import defaultdict
from audio.scanner import AudioMetadata


@dataclass
class DuplicateGroup:
    group_id: int
    files: list[AudioMetadata]
    duplicate_type: str


class DuplicateFinder:
    def __init__(self):
        self.similarity_threshold = 0.95

    def find_duplicates(self, audio_files: list[AudioMetadata]) -> list[DuplicateGroup]:
        if not audio_files:
            return []

        duplicate_groups = []
        group_id = 0
        processed = set()

        hash_groups = self._group_by_hash(audio_files)
        for hash_value, files in hash_groups.items():
            if len(files) > 1 and hash_value:
                group_id += 1
                duplicate_groups.append(DuplicateGroup(
                    group_id=group_id,
                    files=files,
                    duplicate_type='hash'
                ))
                processed.update(f.file_path for f in files)

        remaining_files = [f for f in audio_files if f.file_path not in processed]

        metadata_groups = self._group_by_metadata(remaining_files)
        for key, files in metadata_groups.items():
            if len(files) > 1:
                group_id += 1
                duplicate_groups.append(DuplicateGroup(
                    group_id=group_id,
                    files=files,
                    duplicate_type='metadata'
                ))

        return duplicate_groups

    def _group_by_hash(self, audio_files: list[AudioMetadata]) -> dict:
        groups = defaultdict(list)
        for audio in audio_files:
            if audio.file_hash:
                groups[audio.file_hash].append(audio)
        return dict(groups)

    def _group_by_metadata(self, audio_files: list[AudioMetadata]) -> dict:
        groups = defaultdict(list)

        for audio in audio_files:
            if audio.title and audio.artist:
                key = f"{audio.title.lower()}_{audio.artist.lower()}"
                if audio.duration:
                    duration_key = int(audio.duration / 10)
                    key += f"_{duration_key}"
                groups[key].append(audio)

        return dict(groups)