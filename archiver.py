import abc
import struct
import zlib
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple
from datetime import datetime

MAGIC = b'PYARCH'
VERSION = 1
FLAGS = 0

HEADER_FMT = '<6sBBI'
ENTRY_FMT = '<HQHQQI'
CHUNK_SIZE = 65536

@dataclass
class FileMeta:
    path: str
    mtime: int
    perms: int
    orig_size: int
    comp_size: int
    crc: int

class ArchiveProcessor(abc.ABC):
    def __init__(self, path: Path, progress_cb=None):
        self.path = path
        self.progress_cb = progress_cb

    def _validate_archive(self) -> Tuple[bytes, int, int, int]:
        if not self.path.exists():
            raise FileNotFoundError(f"Файл не найден: {self.path}")
        with open(self.path, 'rb') as f:
            header = f.read(struct.calcsize(HEADER_FMT))
        if len(header) < struct.calcsize(HEADER_FMT):
            raise RuntimeError("Архив повреждён: заголовок отсутствует")
        magic, ver, flags, count = struct.unpack(HEADER_FMT, header)
        if magic != MAGIC:
            raise RuntimeError("Неверный формат архива")
        if ver != VERSION:
            raise RuntimeError(f"Неподдерживаемая версия архива: {ver}")
        return magic, ver, flags, count

    def _collect_files(self, sources: List[Path]) -> List[Tuple[Path, str]]:
        result = []
        for src in sources:
            p = src.resolve()
            if p.is_file():
                result.append((p, p.name))
            elif p.is_dir():
                for f in sorted(p.rglob('*')):
                    if f.is_file():
                        result.append((f, f.relative_to(p).as_posix()))
            else:
                raise FileNotFoundError(f"Путь не найден: {src}")
        return result

    @abc.abstractmethod
    def execute(self):
        pass

class ArchivePacker(ArchiveProcessor):
    def __init__(self, sources: List[Path], output: Path, level: int = 6, progress_cb=None):
        super().__init__(output, progress_cb)
        self.sources = sources
        self.level = level

    def execute(self):
        files = self._collect_files(self.sources)
        if not files:
            raise ValueError("Не найдено файлов для упаковки")
        total = len(files)
        if self.progress_cb: self.progress_cb(0, total)
        entries = []
        blocks = []
        for i, (abs_path, rel_path) in enumerate(files):
            stat = abs_path.stat()
            comp_data = bytearray()
            compressor = zlib.compressobj(self.level)
            crc = 0
            orig_size = 0
            comp_size = 0
            with open(abs_path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk: break
                    orig_size += len(chunk)
                    crc = zlib.crc32(chunk, crc) & 0xFFFFFFFF
                    data = compressor.compress(chunk)
                    if data:
                        comp_size += len(data)
                        comp_data.extend(data)
            final = compressor.flush()
            if final:
                comp_size += len(final)
                comp_data.extend(final)
            entries.append(FileMeta(rel_path, int(stat.st_mtime), stat.st_mode & 0o777, orig_size, comp_size, crc))
            blocks.append(bytes(comp_data))
            if self.progress_cb: self.progress_cb(i + 1, total)
        with open(self.path, 'wb') as out:
            out.write(struct.pack(HEADER_FMT, MAGIC, VERSION, FLAGS, len(files)))
            for e in entries:
                path_bytes = e.path.encode('utf-8')
                out.write(struct.pack(ENTRY_FMT, len(path_bytes), e.mtime, e.perms, e.orig_size, e.comp_size, e.crc))
                out.write(path_bytes)
            for block in blocks:
                out.write(block)

class ArchiveUnpacker(ArchiveProcessor):
    def __init__(self, archive: Path, dest: Path, progress_cb=None):
        super().__init__(archive, progress_cb)
        self.dest = dest

    def execute(self):
        _, _, _, count = self._validate_archive()
        self.dest.mkdir(parents=True, exist_ok=True)
        entries = []
        with open(self.path, 'rb') as f:
            f.seek(struct.calcsize(HEADER_FMT))
            for _ in range(count):
                hdr = f.read(struct.calcsize(ENTRY_FMT))
                if len(hdr) < struct.calcsize(ENTRY_FMT):
                    raise RuntimeError("Архив повреждён: неполный заголовок файла")
                nl, mtime, perms, orig, comp, crc = struct.unpack(ENTRY_FMT, hdr)
                name_bytes = f.read(nl)
                if len(name_bytes) < nl:
                    raise RuntimeError("Архив повреждён: обрезано имя файла")
                entries.append(FileMeta(name_bytes.decode('utf-8'), mtime, perms, orig, comp, crc))
        total = len(entries)
        if self.progress_cb: self.progress_cb(0, total)
        data_offset = struct.calcsize(HEADER_FMT)
        for e in entries:
            data_offset += struct.calcsize(ENTRY_FMT) + len(e.path.encode('utf-8'))
        with open(self.path, 'rb') as f:
            f.seek(data_offset)
            for i, e in enumerate(entries):
                out_path = self.dest / e.path
                out_path.parent.mkdir(parents=True, exist_ok=True)
                decompressor = zlib.decompressobj()
                result_crc = 0
                bytes_read = 0
                with open(out_path, 'wb') as out_f:
                    while bytes_read < e.comp_size:
                        to_read = min(CHUNK_SIZE, e.comp_size - bytes_read)
                        chunk = f.read(to_read)
                        if not chunk:
                            raise RuntimeError(f"Ошибка чтения: неожиданный конец файла на {e.path}")
                        bytes_read += len(chunk)
                        dec_chunk = decompressor.decompress(chunk)
                        if dec_chunk:
                            out_f.write(dec_chunk)
                            result_crc = zlib.crc32(dec_chunk, result_crc) & 0xFFFFFFFF
                    tail = decompressor.flush()
                    if tail:
                        out_f.write(tail)
                if result_crc != e.crc:
                    raise RuntimeError(f"CRC mismatch: {e.path}")
                try:
                    os.utime(out_path, (e.mtime, e.mtime))
                except Exception:
                    pass
                try:
                    os.chmod(out_path, e.perms)
                except Exception:
                    pass
                if self.progress_cb: self.progress_cb(i + 1, total)

class ArchiveInspector(ArchiveProcessor):
    def __init__(self, archive: Path, progress_cb=None):
        super().__init__(archive, progress_cb)

    def execute(self):
        _, _, _, count = self._validate_archive()
        print(f"{'Имя':<40} {'Исходный':>10} {'Сжатый':>10} {'Сохранено':>10} {'Время':>16}")
        print("-" * 88)
        pos = struct.calcsize(HEADER_FMT)
        with open(self.path, 'rb') as f:
            for _ in range(count):
                f.seek(pos)
                header_data = f.read(struct.calcsize(ENTRY_FMT))
                nl, mtime, perms, orig, comp, crc = struct.unpack(ENTRY_FMT, header_data)
                path = f.read(nl).decode('utf-8')
                pos += struct.calcsize(ENTRY_FMT) + nl
                saved = ((orig - comp) / orig * 100) if orig > 0 else 0.0
                t_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                print(f"{path:<40} {orig:>10} {comp:>10} {saved:>9.1f}% {t_str:>16}")