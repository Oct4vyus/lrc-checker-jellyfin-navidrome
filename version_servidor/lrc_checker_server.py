#!/usr/bin/env python3
"""
LRC Checker para bibliotecas de música (Navidrome, etc.)
Verifica que todos los archivos de audio tengan archivos .lrc correspondientes,
que estos contengan timestamps válidos (sincronizados), y que la sincronización
coincida con la duración real del archivo de audio.

Soporta formatos de audio comunes: mp3, flac, ogg, m4a, wma, wav, aiff, opus, wv
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
from enum import Enum

# mutagen para extraer duración de audio
try:
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    from mutagen.mp4 import MP4
    from mutagen.wave import WAVE
    from mutagen.aiff import AIFF
    from mutagen.oggopus import OggOpus
    from mutagen.wavpack import WavPack
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("ADVERTENCIA: mutagen no instalado. La verificación de sincronización real con audio no estará disponible.", file=sys.stderr)


class CheckStatus(Enum):
    OK = "ok"                    # Todo correcto: LRC presente, sincronizado y alineado con audio
    MISSING = "missing"          # No tiene archivo .lrc
    EMPTY = "empty"              # Archivo .lrc vacío
    UNSYNCED = "unsynced"        # Archivo .lrc sin timestamps
    CORRUPT = "corrupt"          # Archivo .lrc ilegible o malformado
    DESYNCED = "desynced"        # LRC con diferencia grande respecto al audio (>60s): probable error real
    REVIEW = "review"            # LRC con diferencia moderada (5-60s): probable outro/fade-out normal
    NO_AUDIO = "no_audio"        # Archivo .lrc huérfano (sin audio correspondiente)


@dataclass
class LrcCheckResult:
    audio_file: Optional[str] = None
    lrc_file: Optional[str] = None
    status: str = ""
    details: str = ""
    timestamp_count: int = 0
    line_count: int = 0
    has_metadata: bool = False
    relative_path: str = ""
    # Campos de sincronización con audio
    audio_duration_sec: Optional[float] = None
    lrc_last_timestamp_sec: Optional[float] = None
    sync_offset_sec: Optional[float] = None  # Diferencia entre último timestamp y duración
    is_signed: bool = False  # True si el .lrc contiene la marca "Oct4vyus Kandle" (ya revisado/corregido)


class LrcChecker:
    # Extensiones de audio soportadas
    AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.m4a', '.wma', '.wav',
                        '.aiff', '.opus', '.wv', '.aac', '.mp4', '.alac'}
    
    # Patrones de timestamp LRC sincronizado
    TIMESTAMP_PATTERNS = [
        re.compile(r'\[(\d{1,2}):(\d{2})\.(\d{2,3})\]'),      # [mm:ss.xx] / [mm:ss.xxx]
        re.compile(r'\[(\d{1,2}):(\d{2}):(\d{2})\.(\d{2,3})\]'),  # [hh:mm:ss.xx]
    ]
    # Enhanced LRC (word-by-word)
    ENHANCED_TIMESTAMP_PATTERN = re.compile(r'<(\d{1,2}):(\d{2})\.(\d{2,3})>')
    
    # Patrón de metadatos LRC
    METADATA_PATTERN = re.compile(r'\[(ar|ti|al|au|by|length|offset|re|tool|ve|la|id):\s*([^\]]*)\]', re.IGNORECASE)
    
    # Offset tag [offset:+/-milliseconds]
    OFFSET_PATTERN = re.compile(r'\[offset:([+-]?\d+)\]', re.IGNORECASE)

    # Marca de archivo "firmado" (ya revisado/corregido manualmente).
    # Texto literal, case-sensitive, tal como lo confirmó el usuario.
    # Puede aparecer con o sin espacio después del timestamp que la precede.
    SIGNED_MARKER = "Oct4vyus Kandle"
    SIGNED_MARKER_PATTERN = re.compile(re.escape(SIGNED_MARKER))

    def __init__(self, music_dir: str, verbose: bool = False, check_orphans: bool = True,
                 sync_tolerance_sec: float = 5.0, enable_sync_check: bool = True,
                 review_threshold_sec: float = 60.0):
        self.music_dir = Path(music_dir).resolve()
        self.verbose = verbose
        self.check_orphans = check_orphans
        self.sync_tolerance_sec = sync_tolerance_sec
        self.enable_sync_check = enable_sync_check and MUTAGEN_AVAILABLE
        # Umbral desde el cual una diferencia grande se considera error real
        # en vez de un probable outro/fade-out normal. Ver discusión: esto es
        # una estimación basada en distribución observada, no un valor exacto.
        self.review_threshold_sec = review_threshold_sec
        self.results: List[LrcCheckResult] = []
        self.stats = {
            'total_audio_files': 0,
            'total_lrc_files': 0,
            'ok': 0,
            'missing': 0,
            'empty': 0,
            'unsynced': 0,
            'corrupt': 0,
            'desynced': 0,
            'review': 0,
            'orphan_lrc': 0,
            'signed': 0,
            'scanned_at': datetime.now().isoformat(),
        }

    def log(self, msg: str):
        if self.verbose:
            print(msg, file=sys.stderr)

    def get_audio_duration(self, audio_path: Path) -> Optional[float]:
        """Extrae la duración en segundos de un archivo de audio usando mutagen."""
        if not MUTAGEN_AVAILABLE:
            return None
        
        ext = audio_path.suffix.lower()
        try:
            if ext == '.mp3':
                audio = MP3(str(audio_path))
            elif ext == '.flac':
                audio = FLAC(str(audio_path))
            elif ext in ('.ogg', '.oga'):
                audio = OggVorbis(str(audio_path))
            elif ext in ('.m4a', '.mp4', '.aac'):
                audio = MP4(str(audio_path))
            elif ext == '.wav':
                audio = WAVE(str(audio_path))
            elif ext in ('.aiff', '.aif'):
                audio = AIFF(str(audio_path))
            elif ext == '.opus':
                audio = OggOpus(str(audio_path))
            elif ext == '.wv':
                audio = WavPack(str(audio_path))
            elif ext == '.wma':
                # WMA requiere mutagen.asf
                from mutagen.asf import ASF
                audio = ASF(str(audio_path))
            else:
                return None
            
            return audio.info.length
        except Exception as e:
            self.log(f"  No se pudo leer duración de {audio_path.name}: {e}")
            return None

    def parse_timestamp_to_seconds(self, match: Tuple) -> float:
        """Convierte un match de timestamp regex a segundos totales."""
        groups = match
        if len(groups) == 3:
            # mm:ss.xx
            mm, ss, xx = groups
            return int(mm) * 60 + int(ss) + int(xx) / (1000 if len(xx) == 3 else 100)
        elif len(groups) == 4:
            # hh:mm:ss.xx
            hh, mm, ss, xx = groups
            return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(xx) / (1000 if len(xx) == 3 else 100)
        return 0.0

    def extract_timestamps(self, content: str, exclude_signed_line: bool = False) -> List[float]:
        """Extrae todos los timestamps de sincronización del contenido LRC, ordenados.

        Si exclude_signed_line=True, ignora la línea que contiene la marca de
        firma (SIGNED_MARKER), para que su timestamp no se use como "último
        timestamp" en el cálculo de sincronización (esa línea es un marcador
        manual, no parte de la letra real).
        """
        timestamps = []
        
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            
            # Ignorar metadatos
            if self.METADATA_PATTERN.fullmatch(line):
                continue

            # Ignorar la línea de firma si se pidió excluirla
            if exclude_signed_line and self.SIGNED_MARKER_PATTERN.search(line):
                continue
            
            # Timestamps estándar [mm:ss.xx]
            for pattern in self.TIMESTAMP_PATTERNS:
                for match in pattern.finditer(line):
                    timestamps.append(self.parse_timestamp_to_seconds(match.groups()))
            
            # Timestamps enhanced <mm:ss.xx>
            for match in self.ENHANCED_TIMESTAMP_PATTERN.finditer(line):
                timestamps.append(self.parse_timestamp_to_seconds(match.groups()))
        
        return sorted(timestamps)

    def get_lrc_offset_ms(self, content: str) -> int:
        """Extrae el valor [offset:+/-ms] si existe."""
        match = self.OFFSET_PATTERN.search(content)
        if match:
            return int(match.group(1))
        return 0

    def has_valid_timestamps(self, content: str) -> Tuple[bool, int, int]:
        """
        Verifica si el contenido tiene timestamps válidos de sincronización.
        Retorna: (tiene_timestamps, cantidad_timestamps, cantidad_lineas_con_texto)
        """
        lines = content.splitlines()
        timestamp_count = 0
        text_lines = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if self.METADATA_PATTERN.fullmatch(line):
                continue
            
            has_ts = False
            for pattern in self.TIMESTAMP_PATTERNS:
                matches = pattern.findall(line)
                if matches:
                    has_ts = True
                    timestamp_count += len(matches)
            
            # También contar enhanced timestamps
            enhanced = self.ENHANCED_TIMESTAMP_PATTERN.findall(line)
            if enhanced:
                has_ts = True
                timestamp_count += len(enhanced)
            
            if has_ts:
                text_lines += 1
            elif len(line) > 0 and not line.startswith('['):
                text_lines += 1
        
        return timestamp_count > 0, timestamp_count, text_lines

    def check_lrc_file(self, lrc_path: Path, audio_path: Optional[Path] = None) -> LrcCheckResult:
        """Analiza un archivo .lrc existente. Si se proporciona audio_path, verifica sincronización."""
        result = LrcCheckResult(
            lrc_file=str(lrc_path),
            relative_path=str(lrc_path.relative_to(self.music_dir))
        )
        
        # Extraer duración del audio si está disponible
        if audio_path and self.enable_sync_check:
            result.audio_duration_sec = self.get_audio_duration(audio_path)
        
        try:
            content = lrc_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = lrc_path.read_text(encoding='utf-8-sig')
            except Exception as e:
                result.status = CheckStatus.CORRUPT.value
                result.details = f"No se pudo leer el archivo: {e}"
                return result
        except Exception as e:
            result.status = CheckStatus.CORRUPT.value
            result.details = f"No se pudo leer el archivo: {e}"
            return result
        
        # Detectar si el archivo ya fue revisado/corregido manualmente (firma)
        result.is_signed = bool(self.SIGNED_MARKER_PATTERN.search(content))

        # Verificar si está vacío
        if not content or not content.strip():
            result.status = CheckStatus.EMPTY.value
            result.details = "Archivo .lrc vacío"
            return result
        
        # Verificar metadatos
        metadata_matches = self.METADATA_PATTERN.findall(content)
        result.has_metadata = len(metadata_matches) > 0
        
        # Verificar timestamps
        has_ts, ts_count, line_count = self.has_valid_timestamps(content)
        result.timestamp_count = ts_count
        result.line_count = line_count
        
        if not has_ts:
            result.status = CheckStatus.UNSYNCED.value
            result.details = f"Sin sincronización: {line_count} líneas de texto, 0 timestamps"
            return result
        
        # A partir de aquí: tiene timestamps. Verificar sincronización con audio si es posible.
        if audio_path and self.enable_sync_check and result.audio_duration_sec is not None:
            # Extraer todos los timestamps y aplicar offset si existe.
            # Se excluye la línea de firma (si existe) para que su timestamp
            # -que es solo un marcador manual, no letra real- no distorsione
            # el cálculo de sync_offset_sec.
            timestamps = self.extract_timestamps(content, exclude_signed_line=result.is_signed)
            offset_ms = self.get_lrc_offset_ms(content)
            offset_sec = offset_ms / 1000.0
            
            if timestamps:
                last_ts = timestamps[-1] + offset_sec
                result.lrc_last_timestamp_sec = last_ts
                result.sync_offset_sec = result.audio_duration_sec - last_ts
                
                # Verificar si está dentro de la tolerancia
                abs_offset = abs(result.sync_offset_sec)
                
                if abs_offset <= self.sync_tolerance_sec:
                    result.status = CheckStatus.OK.value
                    result.details = (f"Sincronizado OK: último timestamp {self._fmt_time(last_ts)} vs "
                                    f"audio {self._fmt_time(result.audio_duration_sec)} "
                                    f"(diferencia: {result.sync_offset_sec:+.1f}s)")
                elif abs_offset <= self.review_threshold_sec:
                    result.status = CheckStatus.REVIEW.value
                    direction = "excede" if result.sync_offset_sec < 0 else "es menor que"
                    result.details = (f"REVISAR: último timestamp {self._fmt_time(last_ts)} {direction} "
                                    f"la duración del audio ({self._fmt_time(result.audio_duration_sec)}). "
                                    f"Diferencia: {abs_offset:.1f}s. Probablemente un outro/fade-out "
                                    f"instrumental normal, o el tiempo que tarda en cantarse la última línea "
                                    f"(esto es una estimación, no una certeza: verificar manualmente si dudás).")
                else:
                    result.status = CheckStatus.DESYNCED.value
                    direction = "excede" if result.sync_offset_sec < 0 else "es menor que"
                    result.details = (f"DESINCRONIZADO: último timestamp {self._fmt_time(last_ts)} {direction} "
                                    f"la duración del audio ({self._fmt_time(result.audio_duration_sec)}). "
                                    f"Diferencia: {abs_offset:.1f}s. Diferencia demasiado grande para ser "
                                    f"solo un outro normal: revisar con prioridad.")
            else:
                # Raro: tiene ts_count > 0 pero no extrajimos ninguno (regex mismatch)
                result.status = CheckStatus.UNSYNCED.value
                result.details = "Formato de timestamps no reconocido correctamente"
        else:
            # Sin audio o sin mutagen: solo verificar que tenga timestamps
            result.status = CheckStatus.OK.value
            if not self.enable_sync_check:
                result.details = f"Sincronizado: {ts_count} timestamps en {line_count} líneas (verificación de audio desactivada)"
            else:
                result.details = f"Sincronizado: {ts_count} timestamps en {line_count} líneas (sin audio para comparar)"
        
        return result

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        """Formatea segundos como mm:ss.xx."""
        m = int(seconds // 60)
        s = seconds % 60
        return f"{m:02d}:{s:05.2f}"

    def scan(self) -> List[LrcCheckResult]:
        """Escanea el directorio de música y verifica todos los archivos."""
        # IMPORTANTE: reiniciar antes de escanear. Sin esto, llamar a scan() más
        # de una vez en el mismo proceso (como hace --reparar, o el endpoint
        # /escanear del servidor) duplica cada fila y dobla las estadísticas.
        self.results = []
        scanned_at = datetime.now().isoformat()
        self.stats = {
            'total_audio_files': 0,
            'total_lrc_files': 0,
            'ok': 0,
            'missing': 0,
            'empty': 0,
            'unsynced': 0,
            'corrupt': 0,
            'desynced': 0,
            'review': 0,
            'orphan_lrc': 0,
            'signed': 0,
            'scanned_at': scanned_at,
        }
        self.log(f"Escaneando: {self.music_dir}")
        if not self.enable_sync_check:
            self.log("ADVERTENCIA: Verificación de sincronización con audio desactivada (mutagen no disponible)")
        else:
            self.log(f"Tolerancia de sincronización: {self.sync_tolerance_sec}s")
        
        audio_files: List[Path] = []
        lrc_files: List[Path] = []
        
        for root, _, files in os.walk(self.music_dir):
            for filename in files:
                file_path = Path(root) / filename
                ext = file_path.suffix.lower()
                if ext in self.AUDIO_EXTENSIONS:
                    audio_files.append(file_path)
                elif ext == '.lrc':
                    lrc_files.append(file_path)
        
        self.stats['total_audio_files'] = len(audio_files)
        self.stats['total_lrc_files'] = len(lrc_files)
        self.log(f"Archivos de audio encontrados: {len(audio_files)}")
        self.log(f"Archivos .lrc encontrados: {len(lrc_files)}")
        
        matched_lrc = set()
        
        # Verificar cada archivo de audio
        for audio_path in audio_files:
            rel_path = audio_path.relative_to(self.music_dir)
            lrc_path = audio_path.with_suffix('.lrc')
            
            self.log(f"Verificando: {rel_path}")
            
            if lrc_path.exists():
                matched_lrc.add(lrc_path.resolve())
                result = self.check_lrc_file(lrc_path, audio_path)
                result.audio_file = str(audio_path)
                result.relative_path = str(rel_path)
            else:
                result = LrcCheckResult(
                    audio_file=str(audio_path),
                    relative_path=str(rel_path),
                    status=CheckStatus.MISSING.value,
                    details="No se encontró archivo .lrc correspondiente"
                )
            
            self.results.append(result)
            self.stats[result.status] = self.stats.get(result.status, 0) + 1
            if result.is_signed:
                self.stats['signed'] += 1
        
        # Verificar archivos .lrc huérfanos
        if self.check_orphans:
            for lrc_path in lrc_files:
                if lrc_path.resolve() not in matched_lrc:
                    rel_path = lrc_path.relative_to(self.music_dir)
                    result = self.check_lrc_file(lrc_path)
                    result.status = CheckStatus.NO_AUDIO.value
                    result.details = f"Archivo .lrc huérfano: no hay audio correspondiente"
                    result.relative_path = str(rel_path)
                    self.results.append(result)
                    self.stats['orphan_lrc'] += 1
                    if result.is_signed:
                        self.stats['signed'] += 1
        
        return self.results

    def reparar_lrc(self, result: LrcCheckResult) -> bool:
        """Repara un archivo .lrc en estado REVIEW agregando un timestamp final con la duración real."""
        if result.status != CheckStatus.REVIEW.value:
            return False
        if not result.lrc_file or not result.audio_duration_sec:
            return False

        lrc_path = Path(result.lrc_file)
        if not lrc_path.exists():
            return False

        duration = result.audio_duration_sec
        minutes = int(duration // 60)
        seconds = duration % 60
        final_timestamp = f"[{minutes:02d}:{seconds:05.2f}]"

        try:
            with open(lrc_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{final_timestamp}\n")
            # No se marca como firmado: eso es solo para archivos con "Oct4vyus Kandle"
            # Actualizamos las stats en memoria para que un generate_html_report()
            # posterior refleje el cambio SIN necesidad de re-escanear todo el disco.
            self.stats['review'] = max(0, self.stats.get('review', 0) - 1)
            self.stats['ok'] = self.stats.get('ok', 0) + 1
            result.status = CheckStatus.OK.value
            result.details = f"Reparado: timestamp final agregado ({final_timestamp}) con duración real {self._fmt_time(duration)}"
            return True
        except Exception as e:
            result.details = f"Error al reparar: {e}"
            return False

    def generate_json_report(self, output_path: Optional[str] = None) -> str:
        """Genera un reporte en formato JSON."""
        report = {
            'scan_info': {
                'music_directory': str(self.music_dir),
                'scanned_at': self.stats['scanned_at'],
                'scanner_version': '2.0.0',
                'sync_check_enabled': self.enable_sync_check,
                'sync_tolerance_sec': self.sync_tolerance_sec,
                'review_threshold_sec': self.review_threshold_sec,
            },
            'statistics': {
                'total_audio_files': self.stats['total_audio_files'],
                'total_lrc_files': self.stats['total_lrc_files'],
                'ok': self.stats.get('ok', 0),
                'missing': self.stats.get('missing', 0),
                'empty': self.stats.get('empty', 0),
                'unsynced': self.stats.get('unsynced', 0),
                'review': self.stats.get('review', 0),
                'desynced': self.stats.get('desynced', 0),
                'corrupt': self.stats.get('corrupt', 0),
                'orphan_lrc': self.stats.get('orphan_lrc', 0),
                'signed': self.stats.get('signed', 0),
            },
            'summary': {
                'coverage_percent': round(
                    (self.stats.get('ok', 0) / max(self.stats['total_audio_files'], 1)) * 100, 2
                ),
                'issues_count': (
                    self.stats.get('missing', 0) +
                    self.stats.get('empty', 0) +
                    self.stats.get('unsynced', 0) +
                    self.stats.get('review', 0) +
                    self.stats.get('desynced', 0) +
                    self.stats.get('corrupt', 0)
                ),
                # Subconjunto de issues_count que amerita prioridad real,
                # excluyendo 'review' (probables outros/fade-outs normales).
                'priority_issues_count': (
                    self.stats.get('missing', 0) +
                    self.stats.get('empty', 0) +
                    self.stats.get('unsynced', 0) +
                    self.stats.get('desynced', 0) +
                    self.stats.get('corrupt', 0)
                ),
            },
            'results': [asdict(r) for r in self.results]
        }
        
        json_output = json.dumps(report, indent=2, ensure_ascii=False)
        
        if output_path:
            Path(output_path).write_text(json_output, encoding='utf-8')
        
        return json_output

    def generate_html_report(self, output_path: Optional[str] = None,
                              server_base_url: str = "http://localhost:8080") -> str:
        """Genera un reporte visual en HTML.

        server_base_url: URL base (protocolo+host+puerto) donde el mini-servidor
        de reparación está escuchando, TAL COMO LA VA A VER EL NAVEGADOR que abra
        este HTML. Si el HTML se abre por SMB/file:// desde otra PC, "localhost"
        NO sirve: hay que pasar la IP o hostname real del servidor OMV.
        """
        
        status_classes = {
            'ok': 'status-ok',
            'missing': 'status-missing',
            'empty': 'status-empty',
            'unsynced': 'status-unsynced',
            'review': 'status-review',
            'desynced': 'status-desynced',
            'corrupt': 'status-corrupt',
            'no_audio': 'status-orphan',
        }
        
        status_labels = {
            'ok': '✅ OK',
            'missing': '❌ Falta .lrc',
            'empty': '⚠️ .lrc Vacío',
            'unsynced': '⚠️ Sin Sincronizar',
            'review': '🟡 Revisar (posible outro)',
            'desynced': '🔴 Desincronizado',
            'corrupt': '❌ Corrupto',
            'no_audio': 'ℹ️ Huérfano',
        }
        
        rows = ""
        for r in self.results:
            status_class = status_classes.get(r.status, '')
            status_label = status_labels.get(r.status, r.status)
            audio_name = Path(r.audio_file).name if r.audio_file else '-'
            lrc_name = Path(r.lrc_file).name if r.lrc_file else '-'
            
            # Columna extra de sincronización
            sync_info = ""
            if r.audio_duration_sec is not None and r.lrc_last_timestamp_sec is not None:
                sync_info = f"<span class='sync-badge' title='Audio: {self._fmt_time(r.audio_duration_sec)} | LRC: {self._fmt_time(r.lrc_last_timestamp_sec)}'>Δ{r.sync_offset_sec:+.1f}s</span>"
            elif r.audio_duration_sec is not None:
                sync_info = f"<span class='sync-badge muted'>Audio: {self._fmt_time(r.audio_duration_sec)}</span>"

            # Columna de firma (archivo ya revisado/corregido manualmente)
            signed_class = " row-signed" if r.is_signed else ""
            signed_info = "<span class='signed-badge' title=\"Contiene la marca de firma\">✍️ Firmado</span>" if r.is_signed else ""
            
            # Botón Reparar solo para archivos en REVIEW
            repair_btn = ""
            if r.status == CheckStatus.REVIEW.value and r.lrc_file:
                lrc_js = r.lrc_file.replace('\\', '\\\\').replace("'", "\\'")
                repair_btn = f'<button onclick="repararLrc(\'{lrc_js}\')" class="repair-btn">Reparar</button>'

            rows += f"""
            <tr class="{status_class}{signed_class}">
                <td class="status-cell">{status_label}</td>
                <td title="{r.audio_file or ''}">{audio_name}</td>
                <td title="{r.lrc_file or ''}">{lrc_name}</td>
                <td>{r.details}</td>
                <td class="num">{r.timestamp_count}</td>
                <td class="num">{r.line_count}</td>
                <td class="sync-col">{sync_info}</td>
                <td class="signed-col">{signed_info}</td>
                <td>{repair_btn}</td>
            </tr>
            """
        
        # Estadísticas
        total = self.stats['total_audio_files']
        ok = self.stats.get('ok', 0)
        missing = self.stats.get('missing', 0)
        empty = self.stats.get('empty', 0)
        unsynced = self.stats.get('unsynced', 0)
        review = self.stats.get('review', 0)
        desynced = self.stats.get('desynced', 0)
        corrupt = self.stats.get('corrupt', 0)
        orphan = self.stats.get('orphan_lrc', 0)
        signed = self.stats.get('signed', 0)
        coverage = round((ok / max(total, 1)) * 100, 1)
        sync_check_badge = "<span class='badge'>con mutagen</span>" if self.enable_sync_check else "<span class='badge warn'>sin mutagen</span>"
        
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte LRC Checker - {self.stats['scanned_at'][:10]}</title>
    <style>
        :root {{
            --bg: #0f0f1a;
            --surface: #1a1a2e;
            --surface-light: #252542;
            --text: #e0e0e0;
            --text-muted: #8888aa;
            --accent: #6c5ce7;
            --ok: #00b894;
            --missing: #e74c3c;
            --empty: #f39c12;
            --unsynced: #e67e22;
            --review: #f1c40f;
            --desynced: #ff4757;
            --corrupt: #c0392b;
            --orphan: #3498db;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{ max-width: 1500px; margin: 0 auto; }}
        h1 {{ text-align: center; margin-bottom: 5px; color: var(--accent); }}
        .subtitle {{ text-align: center; color: var(--text-muted); margin-bottom: 5px; }}
        .version {{ text-align: center; color: var(--text-muted); font-size: 0.85rem; margin-bottom: 25px; }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            margin-bottom: 25px;
        }}
        .stat-card {{
            background: var(--surface);
            border-radius: 12px;
            padding: 18px 10px;
            text-align: center;
            border: 1px solid var(--surface-light);
        }}
        .stat-card .number {{ font-size: 1.8rem; font-weight: bold; }}
        .stat-card .label {{ color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }}
        .stat-ok {{ color: var(--ok); }}
        .stat-missing {{ color: var(--missing); }}
        .stat-empty {{ color: var(--empty); }}
        .stat-unsynced {{ color: var(--unsynced); }}
        .stat-review {{ color: var(--review); }}
        .stat-desynced {{ color: var(--desynced); }}
        .stat-corrupt {{ color: var(--corrupt); }}
        .stat-coverage {{ color: var(--accent); }}
        
        .progress-bar {{
            width: 100%;
            height: 28px;
            background: var(--surface);
            border-radius: 14px;
            overflow: hidden;
            margin-bottom: 25px;
            border: 1px solid var(--surface-light);
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--ok), #00cec9);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.9rem;
            transition: width 0.5s ease;
        }}
        
        .filters {{ margin-bottom: 18px; display: flex; gap: 8px; flex-wrap: wrap; }}
        .filters button {{
            padding: 7px 14px;
            border: none;
            border-radius: 18px;
            background: var(--surface);
            color: var(--text);
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.9rem;
        }}
        .filters button:hover, .filters button.active {{ background: var(--accent); }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            background: var(--surface-light);
            font-size: 0.75rem;
            margin-left: 8px;
            color: var(--ok);
        }}
        .badge.warn {{ color: var(--empty); }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border-radius: 12px;
            overflow: hidden;
            font-size: 0.92rem;
        }}
        th {{
            background: var(--surface-light);
            padding: 12px 10px;
            text-align: left;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 0.78rem;
            letter-spacing: 0.5px;
        }}
        td {{ padding: 10px; border-bottom: 1px solid var(--surface-light); vertical-align: top; }}
        tr:hover {{ background: rgba(108, 92, 231, 0.05); }}
        .num {{ text-align: center; font-variant-numeric: tabular-nums; }}
        
        .status-ok {{ border-left: 4px solid var(--ok); }}
        .status-missing {{ border-left: 4px solid var(--missing); }}
        .status-empty {{ border-left: 4px solid var(--empty); }}
        .status-unsynced {{ border-left: 4px solid var(--unsynced); }}
        .status-review {{ border-left: 4px solid var(--review); }}
        .status-desynced {{ border-left: 4px solid var(--desynced); }}
        .status-corrupt {{ border-left: 4px solid var(--corrupt); }}
        .status-orphan {{ border-left: 4px solid var(--orphan); }}
        .status-cell {{ font-weight: 600; white-space: nowrap; }}
        
        .sync-col {{ white-space: nowrap; }}
        .sync-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 6px;
            background: rgba(0,184,148,0.15);
            color: var(--ok);
            font-size: 0.82rem;
            font-variant-numeric: tabular-nums;
        }}
        .sync-badge.muted {{
            background: rgba(136,136,170,0.1);
            color: var(--text-muted);
        }}

        .signed-col {{ white-space: nowrap; }}
        .signed-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 6px;
            background: rgba(108, 92, 231, 0.15);
            color: var(--accent);
            font-size: 0.82rem;
        }}
        
        .repair-btn {{
            padding: 4px 10px;
            border: none;
            border-radius: 6px;
            background: linear-gradient(90deg, var(--accent), #8c7ae6);
            color: #fff;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 2px 4px rgba(108, 92, 231, 0.3);
        }}
        .repair-btn:hover {{
            background: linear-gradient(90deg, #8c7ae6, var(--accent));
            box-shadow: 0 4px 8px rgba(108, 92, 231, 0.4);
            transform: translateY(-1px);
        }}
        .footer {{
            text-align: center;
            margin-top: 25px;
            color: var(--text-muted);
            font-size: 0.85rem;
        }}
        
        @media (max-width: 900px) {{
            .stats-grid {{ grid-template-columns: repeat(3, 1fr); }}
            td, th {{ padding: 8px 6px; font-size: 0.85rem; }}
            .sync-col {{ display: none; }}
            .signed-col {{ display: none; }}
        }}
        @media (max-width: 600px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 LRC Checker Report</h1>
        <p class="subtitle">{self.music_dir} | Escaneado: {self.stats['scanned_at']}</p>
        <p class="version">LRC Checker v2.0.0 {sync_check_badge} | Tolerancia OK: {self.sync_tolerance_sec}s | Umbral revisión/error: {self.review_threshold_sec}s</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="number stat-ok">{ok}</div>
                <div class="label">OK</div>
            </div>
            <div class="stat-card">
                <div class="number stat-missing">{missing}</div>
                <div class="label">Sin .lrc</div>
            </div>
            <div class="stat-card">
                <div class="number stat-empty">{empty}</div>
                <div class="label">.lrc Vacíos</div>
            </div>
            <div class="stat-card">
                <div class="number stat-unsynced">{unsynced}</div>
                <div class="label">Sin Timestamps</div>
            </div>
            <div class="stat-card">
                <div class="number stat-review">{review}</div>
                <div class="label">Revisar (posible outro)</div>
            </div>
            <div class="stat-card">
                <div class="number stat-desynced">{desynced}</div>
                <div class="label">Desincronizado</div>
            </div>
            <div class="stat-card">
                <div class="number stat-corrupt">{corrupt}</div>
                <div class="label">Corruptos</div>
            </div>
            <div class="stat-card">
                <div class="number stat-coverage">{coverage}%</div>
                <div class="label">Cobertura OK</div>
            </div>
            <div class="stat-card">
                <div class="number" style="color: var(--accent);">{signed}</div>
                <div class="label">✍️ Firmados</div>
            </div>
        </div>
        
        <div class="progress-bar">
            <div class="progress-fill" style="width: {coverage}%">{coverage}% OK</div>
        </div>
        
        <div class="filters">
            <button class="active" onclick="filterRows('all')">Todos ({total + orphan})</button>
            <button onclick="filterRows('ok')">✅ OK ({ok})</button>
            <button onclick="filterRows('missing')">❌ Missing ({missing})</button>
            <button onclick="filterRows('empty')">⚠️ Empty ({empty})</button>
            <button onclick="filterRows('unsynced')">⚠️ Unsynced ({unsynced})</button>
            <button onclick="filterRows('review')">🟡 Revisar ({review})</button>
            <button onclick="filterRows('desynced')">🔴 Desync ({desynced})</button>
            <button onclick="filterRows('corrupt')">❌ Corrupt ({corrupt})</button>
            <button onclick="filterRows('orphan')">ℹ️ Huérfanos ({orphan})</button>
            <button onclick="filterRows('signed')">✍️ Firmados ({signed})</button>
        </div>
        
        <table id="resultsTable">
            <thead>
                <tr>
                    <th>Estado</th>
                    <th>Audio</th>
                    <th>.lrc</th>
                    <th>Detalles</th>
                    <th>TS</th>
                    <th>Lín</th>
                    <th>Sync</th>
                    <th>Firmado</th>
                    <th>Reparar</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        
        <div class="footer">
            {self.stats['total_audio_files']} archivos de audio | 
            {self.stats['total_lrc_files']} archivos .lrc |
            Verificación de audio: {'activada' if self.enable_sync_check else 'desactivada'}
        </div>
        <div style="text-align:center; margin-top: 10px;">
            <button onclick="escanearAhora()" id="scanBtn" class="repair-btn" style="background: var(--accent);">🔄 Escanear ahora</button>
            <span id="scanStatus" style="color: var(--text-muted); margin-left: 10px;"></span>
        </div>
    </div>
    
    <script>
        const REPAIR_SERVER_URL = "{server_base_url}";
        function filterRows(status) {{
            const rows = document.querySelectorAll('#resultsTable tbody tr');
            const buttons = document.querySelectorAll('.filters button');
            buttons.forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            rows.forEach(row => {{
                const matches = status === 'all'
                    || (status === 'signed' ? row.classList.contains('row-signed') : row.classList.contains('status-' + status));
                row.style.display = matches ? '' : 'none';
            }});
        }}

        function repararLrc(lrcFile) {{
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = 'Reparando...';

            const url = REPAIR_SERVER_URL + '/reparar?archivo=' + encodeURIComponent(lrcFile);
            fetch(url, {{ method: 'POST' }})
                .then(r => r.text().then(text => ({{ ok: r.ok, text }})))
                .then(({{ ok, text }}) => {{
                    alert((ok ? 'OK: ' : 'Rechazado: ') + text);
                    if (ok) {{
                        // El servidor ya regeneró el HTML en disco con el nuevo estado.
                        // Recargamos para traer esa versión actualizada.
                        location.reload();
                    }} else {{
                        btn.disabled = false;
                        btn.textContent = 'Reparar';
                    }}
                }})
                .catch(err => {{
                    alert('No se pudo conectar con el servidor de reparación en:\\n' + REPAIR_SERVER_URL +
                          '\\n\\nVerificá que:\\n' +
                          '1) El contenedor esté corriendo.\\n' +
                          '2) El puerto esté publicado en docker-compose (ports: 9080:8080).\\n' +
                          '3) REPAIR_SERVER_URL apunte a la IP real del servidor, no a localhost.\\n\\n' +
                          'Detalle técnico: ' + err);
                    btn.disabled = false;
                    btn.textContent = 'Reparar';
                }});
        }}

        function escanearAhora() {{
            const btn = document.getElementById('scanBtn');
            const status = document.getElementById('scanStatus');
            btn.disabled = true;
            status.textContent = 'Escaneando... esto puede tardar según el tamaño de tu biblioteca.';

            fetch(REPAIR_SERVER_URL + '/escanear', {{ method: 'POST' }})
                .then(r => r.text())
                .then(text => {{
                    status.textContent = text;
                    location.reload();
                }})
                .catch(err => {{
                    status.textContent = 'Error al conectar con el servidor: ' + err;
                    btn.disabled = false;
                }});
        }}
    </script>
</body>
</html>"""
        
        if output_path:
            Path(output_path).write_text(html, encoding='utf-8')
        
        return html

    def generate_text_report(self) -> str:
        """Genera un reporte de texto simple para logs."""
        lines = [
            "=" * 65,
            "  LRC CHECKER REPORT v2.0.0",
            "=" * 65,
            f"Directorio: {self.music_dir}",
            f"Escaneado:  {self.stats['scanned_at']}",
            f"Sync check: {'ACTIVADO (mutagen)' if self.enable_sync_check else 'DESACTIVADO'}",
            f"Tolerancia: {self.sync_tolerance_sec}s (OK) / {self.review_threshold_sec}s (revisar vs. error real)",
            "-" * 65,
            f"  Archivos de audio:  {self.stats['total_audio_files']}",
            f"  Archivos .lrc:      {self.stats['total_lrc_files']}",
            "",
            "  RESULTADOS:",
            f"    ✅ OK:              {self.stats.get('ok', 0)}",
            f"    ❌ Sin .lrc:        {self.stats.get('missing', 0)}",
            f"    ⚠️  .lrc Vacíos:    {self.stats.get('empty', 0)}",
            f"    ⚠️  Sin timestamps:  {self.stats.get('unsynced', 0)}",
            f"    🟡 Revisar (posible outro): {self.stats.get('review', 0)}",
            f"    🔴 Desincronizado:  {self.stats.get('desynced', 0)}",
            f"    ❌ Corruptos:       {self.stats.get('corrupt', 0)}",
            f"    ℹ️  Huérfanos:       {self.stats.get('orphan_lrc', 0)}",
            f"    ✍️  Firmados:        {self.stats.get('signed', 0)} (excluidos del cálculo de sync)",
            "",
            f"  Cobertura OK: {round((self.stats.get('ok', 0) / max(self.stats['total_audio_files'], 1)) * 100, 1)}%",
            "=" * 65,
        ]
        
        # Listar problemas
        issues = [r for r in self.results if r.status != CheckStatus.OK.value]
        if issues:
            lines.append("\n  ARCHIVOS CON PROBLEMAS:")
            for r in issues[:50]:
                audio = Path(r.audio_file).name if r.audio_file else '-'
                lrc = Path(r.lrc_file).name if r.lrc_file else '-'
                lines.append(f"    [{r.status.upper()}] {audio} | {lrc}")
                lines.append(f"      → {r.details}")
            if len(issues) > 50:
                lines.append(f"    ... y {len(issues) - 50} más")
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Verifica archivos .lrc en bibliotecas de música, incluyendo sincronización con audio',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  lrc_checker.py /music
  lrc_checker.py /music --json --output-dir /reports
  lrc_checker.py /music --html -o /reports --tolerance 3.0 --verbose
        """
    )
    parser.add_argument('music_dir', help='Directorio raíz de la biblioteca de música')
    parser.add_argument('-j', '--json', action='store_true', help='Generar reporte JSON')
    parser.add_argument('--html', action='store_true', help='Generar reporte HTML')
    parser.add_argument('-o', '--output-dir', default='/reports', help='Directorio de salida (default: /reports)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Mostrar progreso en consola')
    parser.add_argument('--no-orphans', action='store_true', help='No verificar archivos .lrc huérfanos')
    parser.add_argument('--tolerance', type=float, default=5.0, help='Tolerancia en segundos para considerar sincronizado (default: 5.0)')
    parser.add_argument('--review-threshold', type=float, default=60.0, help='Diferencia en segundos a partir de la cual se considera error real en vez de posible outro/fade-out (default: 60.0). Es una estimación, ajustable con prueba y error.')
    parser.add_argument('--no-sync-check', action='store_true', help='Desactivar verificación de duración con audio (solo verifica sintaxis de timestamps)')
    parser.add_argument('--serve', action='store_true', help='Iniciar mini servidor web en el puerto 8080 y quedarse corriendo (modo bajo demanda: sin loop de escaneo periódico)')
    parser.add_argument('--server-url', type=str, default='http://localhost:8080',
                        help='URL base (protocolo+host+puerto) donde el navegador va a encontrar el mini-servidor. '
                             'Si el HTML se abre desde otra PC (ej. por SMB), NO puede ser localhost: debe ser la IP/hostname real del servidor.')
    parser.add_argument('--reparar', type=str, metavar='ARCHIVO_LRC', nargs='?', const='all',
                        help='Repara archivos .lrc en estado REVIEW agregando timestamp final con duración real. '
                             'Si se pasa un archivo .lrc específico, solo repara ese. '
                             'Sin argumento, repara todos los archivos en REVIEW.')
    parser.add_argument('--exit-zero', action='store_true', help='Salir con código 0 aunque haya problemas (útil para loops continuos)')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.music_dir):
        print(f"Error: El directorio '{args.music_dir}' no existe.", file=sys.stderr)
        sys.exit(1)
    
    if not MUTAGEN_AVAILABLE and not args.no_sync_check:
        print("ADVERTENCIA: mutagen no instalado. La verificación de sincronización real no estará disponible.", file=sys.stderr)
    
    # Crear directorio de salida
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Ejecutar escaneo
    checker = LrcChecker(
        music_dir=args.music_dir,
        verbose=args.verbose,
        check_orphans=not args.no_orphans,
        sync_tolerance_sec=args.tolerance,
        enable_sync_check=not args.no_sync_check,
        review_threshold_sec=args.review_threshold
    )
    checker.scan()

    # Funcionalidad de reparación
    if args.reparar is not None:
        repaired = 0
        if args.reparar == 'all':
            for r in checker.results:
                if r.status == CheckStatus.REVIEW.value:
                    if checker.reparar_lrc(r):
                        repaired += 1
        else:
            # Si se pasó un archivo .lrc específico
            lrc_path = Path(args.reparar)
            if lrc_path.exists():
                # Buscar el resultado correspondiente
                for r in checker.results:
                    if r.lrc_file and str(Path(r.lrc_file).resolve()) == str(lrc_path.resolve()):
                        if checker.reparar_lrc(r):
                            repaired += 1
            else:
                print(f"Archivo no encontrado: {args.reparar}", file=sys.stderr)
        if repaired > 0:
            print(f"Reparados: {repaired} archivo(s) en estado REVIEW.")
            # Volver a escanear para actualizar resultados y pasar a OK
            checker.scan()
        else:
            print("No se reparó ningún archivo (no había archivos en REVIEW o falló la reparación).")

    # Generar reportes
    html_path = output_dir / 'lrc_report.html'
    json_path = output_dir / 'lrc_report.json'
    if args.json or not args.html:
        checker.generate_json_report(str(json_path))
        print(f"Reporte JSON guardado: {json_path}")
    
    if args.html:
        checker.generate_html_report(str(html_path), server_base_url=args.server_url)
        print(f"Reporte HTML guardado: {html_path}")
    
    # Siempre imprimir resumen en texto
    print(checker.generate_text_report())
    
    # Iniciar mini servidor web si se pidió --serve.
    # Modo "bajo demanda": no hay loop de re-escaneo periódico. El propio
    # servidor expone /escanear para disparar un re-escaneo cuando se necesite
    # (botón "Escanear ahora" en el HTML, o un curl/cron externo si se quiere).
    if args.serve:
        print(f"Iniciando servidor de reparación en el puerto 8080 (URL pública configurada: {args.server_url}) ...")
        print("(Los botones 'Reparar' y 'Escanear ahora' del HTML hacen peticiones a este servidor)")
        try:
            run_server(checker, str(html_path), str(json_path), args.server_url, port=8080)
        except KeyboardInterrupt:
            print("Servidor detenido.")

    # Salir con código de error si hay problemas (a menos que se pida lo contrario)
    if not args.exit_zero:
        issues = checker.stats.get('missing', 0) + checker.stats.get('empty', 0) + \
                 checker.stats.get('unsynced', 0) + checker.stats.get('corrupt', 0) + \
                 checker.stats.get('desynced', 0)
        if issues > 0:
            sys.exit(1)


# Mini servidor web integrado para que los botones "Reparar" y "Escanear ahora"
# del HTML funcionen. Reutiliza checker.reparar_lrc() (soporta todos los formatos
# de audio, no solo mp3) y checker.scan(), en vez de reimplementar la lógica.
try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse
    import shutil

    class RepairHandler(BaseHTTPRequestHandler):
        # Se asignan desde run_server() antes de arrancar el servidor.
        checker: 'LrcChecker' = None
        html_path: str = None
        json_path: str = None

        def _send(self, code: int, body: str):
            encoded = body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            # Necesario porque el HTML se abre normalmente como file:// (ej. por SMB),
            # y sin este header el navegador bloquea la respuesta del fetch() por CORS.
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.end_headers()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/reparar':
                self._handle_reparar(urllib.parse.parse_qs(parsed.query))
            elif parsed.path == '/escanear':
                self._handle_escanear()
            else:
                self._send(404, 'Ruta no encontrada')

        def do_GET(self):
            # /escanear también admite GET, por si se quiere disparar con
            # curl/cron externo sin depender del botón del navegador.
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/escanear':
                self._handle_escanear()
            elif parsed.path == '/status':
                self._send(200, 'ok')
            else:
                self._send(404, 'Ruta no encontrada. Usá POST /reparar?archivo=... o POST /escanear')

        def _handle_reparar(self, query):
            archivo = query.get('archivo', [''])[0]
            if not archivo:
                self._send(400, 'Falta el parámetro archivo')
                return

            checker = RepairHandler.checker
            try:
                lrc_path = Path(archivo).resolve()
            except Exception as e:
                self._send(400, f'Ruta inválida: {e}')
                return

            # No permitir reparar nada fuera de MUSIC_DIR: evita que alguien pase
            # una ruta arbitraria y el servidor escriba en cualquier archivo del contenedor.
            try:
                lrc_path.relative_to(checker.music_dir)
            except ValueError:
                self._send(403, 'Ruta fuera del directorio de música. Rechazado por seguridad.')
                return

            if lrc_path.suffix.lower() != '.lrc':
                self._send(400, 'Solo se pueden reparar archivos .lrc')
                return

            if not lrc_path.exists():
                self._send(404, 'El archivo no existe en disco')
                return

            # Buscar el resultado correspondiente en el ÚLTIMO escaneo en memoria.
            result = None
            for r in checker.results:
                if r.lrc_file and Path(r.lrc_file).resolve() == lrc_path:
                    result = r
                    break

            if result is None:
                self._send(404, 'Ese archivo no está en el último escaneo. Probá "Escanear ahora" y reintentá.')
                return

            if result.status != CheckStatus.REVIEW.value:
                # Evita duplicar el timestamp final si se hace doble clic o si el
                # archivo ya fue reparado en una petición anterior.
                self._send(409, f'Este archivo ya no está en estado REVISAR (estado actual: "{result.status}"). No se modifica, para no duplicar el timestamp final.')
                return

            # Backup del .lrc original antes de tocarlo, una única vez.
            backup_path = lrc_path.with_suffix(lrc_path.suffix + '.bak')
            if not backup_path.exists():
                try:
                    shutil.copy2(lrc_path, backup_path)
                except Exception as e:
                    self._send(500, f'No se pudo crear el backup, reparación cancelada por seguridad: {e}')
                    return

            if checker.reparar_lrc(result):
                checker.generate_html_report(RepairHandler.html_path, server_base_url=RepairHandler.server_url)
                checker.generate_json_report(RepairHandler.json_path)
                self._send(200, result.details)
            else:
                self._send(500, f'No se pudo reparar: {result.details}')

        def _handle_escanear(self):
            checker = RepairHandler.checker
            checker.scan()
            checker.generate_html_report(RepairHandler.html_path, server_base_url=RepairHandler.server_url)
            checker.generate_json_report(RepairHandler.json_path)
            self._send(200, f"Escaneo completo: {checker.stats.get('review', 0)} archivo(s) en estado REVISAR, "
                             f"{checker.stats.get('ok', 0)} OK de {checker.stats.get('total_audio_files', 0)} total.")

        def log_message(self, fmt, *args):
            # Silenciar logs por request del servidor HTTP estándar.
            pass

    def run_server(checker: 'LrcChecker', html_path: str, json_path: str,
                   server_url: str = 'http://localhost:8080', port: int = 8080):
        RepairHandler.checker = checker
        RepairHandler.html_path = html_path
        RepairHandler.json_path = json_path
        RepairHandler.server_url = server_url
        server = HTTPServer(('0.0.0.0', port), RepairHandler)
        print(f"Servidor de reparación escuchando en el puerto {port} del contenedor.")
        server.serve_forever()

except ImportError:
    pass  # http.server es parte de la librería estándar, siempre está disponible


if __name__ == '__main__':
    main()
