"""UI strings for SpectraGlyph (Swedish and English)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QLocale

UiLang = Literal["sv", "en"]


@dataclass(frozen=True)
class UIStrings:
    # Menu (macOS may merge "SpectraGlyph" menu; we still provide titles)
    menu_view: str
    menu_language: str
    lang_auto: str
    lang_sv: str
    lang_en: str
    menu_help: str
    shortcuts_action: str
    shortcuts_dialog_title: str
    shortcuts_dialog_body: str

    # File menu + recents
    menu_file: str
    file_open: str
    file_recent: str
    file_recent_empty: str
    file_recent_clear: str
    file_export: str
    file_exit: str
    recent_missing: str

    # Main window
    choose_audio: str
    choose_audio_tooltip: str
    no_audio_loaded: str
    preview_watermark: str
    play_preview: str
    stop_preview: str
    play_tooltip: str
    play_needs_audio: str
    play_failed: str
    play_preparing: str
    status_hint_drop: str
    pick_audio_title: str
    pick_audio_filter: str
    reading_file: str
    load_audio_error: str
    spectrogram_error: str
    audio_loaded_hint: str
    channels_abbr: str
    preview_error: str
    export_need_source: str
    exporting: str
    export_saved_status: str
    export_error: str
    export_done_title: str
    export_done_body: str
    export_done_open_audacity: str
    export_done_show_folder: str
    export_done_close: str
    audacity_not_found: str
    save_preset_title: str
    preset_name_label: str
    preset_saved: str
    view_guide_copied: str
    error_title: str

    # Main — view guide (multi-line, {placeholders} for format)
    view_guide_intro: str
    view_guide_step1: str
    view_guide_step2: str
    view_guide_step3_header: str
    view_guide_fft: str
    view_guide_window: str
    view_guide_dyn: str
    view_guide_time: str
    view_guide_freq: str

    # Controls panel
    group_mode: str
    mode_invisible: str
    mode_full: str
    group_placement: str
    label_start: str
    label_duration: str
    label_fmin: str
    label_fmax: str
    label_strength: str
    group_bg: str
    bg_alpha: str
    bg_auto: str
    bg_white: str
    bg_black: str
    bg_chroma: str
    bg_luminance: str
    chroma_color_btn: str
    chroma_pick_title: str
    chroma_current_tooltip: str
    label_method: str
    label_threshold: str
    invert: str
    reset: str
    save_preset: str
    view_guide_btn: str
    view_guide_tooltip: str
    export: str
    export_tooltip: str

    # Source panel (image / text)
    tab_image: str
    tab_text: str
    pick_image: str
    pick_image_tooltip: str
    clear: str
    no_image: str
    drop_png_here: str
    text_placeholder: str
    label_font_size: str
    label_letter_spacing: str
    pick_image_title: str
    pick_image_filter: str
    image_error: str

    # Spectrogram view
    axis_frequency: str
    axis_time: str
    empty_spectrogram_hint: str

    # Long audio + progress
    long_audio_title: str
    long_audio_intro: str
    long_audio_load_full: str
    long_audio_load_first_n: str
    long_audio_load_range: str
    long_audio_range_start: str
    long_audio_range_length: str
    audio_segment_badge: str
    audio_probe_failed_detail: str
    progress_loading_audio: str
    progress_spectrogram: str

    # Export dialog
    export_dialog_title: str
    filter_lossless: str
    filter_lossy: str
    lossy_title: str
    lossy_body: str


def _sv() -> UIStrings:
    return UIStrings(
        menu_view="Visning",
        menu_language="Språk",
        lang_auto="Systemstandard",
        lang_sv="Svenska",
        lang_en="Engelska",
        menu_help="Hjälp",
        shortcuts_action="Tangentbord…",
        shortcuts_dialog_title="Tangentbordsgenvägar",
        shortcuts_dialog_body=(
            "• Öppna ljudfil — Ctrl+O\n"
            "• Välj bild — Ctrl+I\n"
            "• Exportera ljud — Ctrl+E\n"
            "• Spela upp / stoppa — Mellanslag\n"
        ),
        menu_file="Arkiv",
        file_open="Öppna ljudfil…",
        file_recent="Senaste filer",
        file_recent_empty="(inga senaste filer)",
        file_recent_clear="Rensa lista",
        file_export="Exportera…",
        file_exit="Avsluta",
        recent_missing="Filen finns inte längre: {path}",
        choose_audio="🎵  Välj ljudfil…",
        choose_audio_tooltip="Välj en ljudfil att bädda in vattenmärket i (Ctrl+O)",
        no_audio_loaded="Ingen ljudfil laddad",
        preview_watermark="👁  Förhandsgranska vattenmärke",
        play_preview="▶  Spela",
        stop_preview="■  Stoppa",
        play_tooltip="Spela upp det som visas i spektrogrammet (original eller med vattenmärke, mellanslag).",
        play_needs_audio="Ladda en ljudfil först innan du spelar.",
        play_failed="Uppspelning misslyckades: {msg}",
        play_preparing="Förbereder uppspelning med vattenmärke…",
        status_hint_drop="Dra in en ljudfil och en bild – sedan knappen 'Exportera'.",
        pick_audio_title="Välj ljudfil",
        pick_audio_filter="Ljudfiler ({exts})",
        reading_file="Läser in {name}…",
        load_audio_error="Kunde inte läsa ljudet: {msg}",
        spectrogram_error="Spektrogram-fel: {msg}",
        audio_loaded_hint="Ljud: {name} ({sr} Hz, {dur:.1f}s)",
        channels_abbr="kanaler",
        preview_error="Förhandsgranskningsfel: {msg}",
        export_need_source="Ladda eller skriv något i Bild/Text först.",
        exporting="Exporterar…",
        export_saved_status="Exporterad: {path}",
        export_error="Exportfel: {msg}",
        export_done_title="Klart",
        export_done_body=(
            "Sparad till:\n{path}\n\n"
            "Öppna filen i Audacity eller Spek för att se vattenmärket."
        ),
        export_done_open_audacity="Öppna i Audacity",
        export_done_show_folder="Visa i mapp",
        export_done_close="Stäng",
        audacity_not_found=(
            "Hittar ingen Audacity-installation. Installera Audacity eller öppna filen manuellt."
        ),
        save_preset_title="Spara preset",
        preset_name_label="Namn:",
        preset_saved="Preset '{name}' sparad.",
        view_guide_copied="View-guide kopierad till urklipp.",
        error_title="Fel",
        view_guide_intro="Så här ser du vattenmärket i ljudfilen:\n\n",
        view_guide_step1="1. Öppna filen i Audacity (eller Spek / Sonic Visualiser).\n",
        view_guide_step2="2. Välj spår-menyn → Spectrogram view.\n",
        view_guide_step3_header="3. Inställningar:\n",
        view_guide_fft="   • FFT-storlek: 4096\n",
        view_guide_window="   • Fönster: Hann\n",
        view_guide_dyn="   • Dynamiskt omfång: 80 dB\n",
        view_guide_time="4. Tidsposition: {t0:.2f}s – {t1:.2f}s\n",
        view_guide_freq="5. Frekvensomfång: {f0} Hz – {f1} Hz",
        group_mode="Läge",
        mode_invisible="Invisible (>15 kHz)",
        mode_full="Full range",
        group_placement="Placering",
        label_start="Starttid:",
        label_duration="Längd:",
        label_fmin="Frekvens min:",
        label_fmax="Frekvens max:",
        label_strength="Styrka:",
        group_bg="Bakgrund / mask",
        bg_alpha="Alpha-kanal (PNG)",
        bg_auto="Auto (hörnsampling)",
        bg_white="Ta bort vitt",
        bg_black="Ta bort svart",
        bg_chroma="Ta bort färgnyckel…",
        bg_luminance="Luminans",
        chroma_color_btn="Färg…",
        chroma_pick_title="Välj färg att ta bort",
        chroma_current_tooltip="Vald färgnyckel: {rgb}",
        label_method="Metod:",
        label_threshold="Tröskel:",
        invert="Invertera",
        reset="Återställ",
        save_preset="Spara preset",
        view_guide_btn="📋 View-guide",
        view_guide_tooltip=(
            "Kopierar instruktioner till urklipp så mottagaren vet "
            "vilka FFT-inställningar som visar vattenmärket."
        ),
        export="💾  Exportera…",
        export_tooltip="Skriv ut ljudfil med vattenmärke (Ctrl+E)",
        tab_image="🖼  Bild",
        tab_text="🅰  Text",
        pick_image="📁 Välj bild…",
        pick_image_tooltip="Välj en bild som ritas in i spektrogrammet (Ctrl+I)",
        clear="Rensa",
        no_image="Ingen bild vald",
        drop_png_here="Dra och släpp en PNG här",
        text_placeholder="Skriv text som ska ritas i spektrogrammet…",
        label_font_size="Fontstorlek:",
        label_letter_spacing="Teckenavstånd:",
        pick_image_title="Välj bild",
        pick_image_filter="Bilder (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
        image_error="Fel: {detail}",
        axis_frequency="Frekvens",
        axis_time="Tid",
        empty_spectrogram_hint="Dra in en ljudfil eller klicka 'Välj ljudfil…'",
        long_audio_title="Lång ljudfil",
        long_audio_intro=(
            "{name}: cirka {minutes:.1f} min ({mb:.1f} MB).\n\n"
            "Det kan ta tid att läsa in och räkna spektrogram. "
            "Du kan välja att bara ladda ett tidsintervall för att arbeta snabbare."
        ),
        long_audio_load_full="Läs in hela filen",
        long_audio_load_first_n="Ladda bara de första {sec} s",
        long_audio_load_range="Ladda ett eget intervall",
        long_audio_range_start="Börjar vid:",
        long_audio_range_length="Längd:",
        audio_segment_badge=" · {start:.1f}–{end:.1f} s av {total:.1f} s",
        audio_probe_failed_detail=(
            "Kunde inte läsa filens metadata ({err}). Hela filen laddas — det kan ta en stund."
        ),
        progress_loading_audio="Läser in ljud…",
        progress_spectrogram="Beräknar spektrogram…",
        export_dialog_title="Exportera ljudfil",
        filter_lossless="WAV (*.wav);;FLAC (*.flac)",
        filter_lossy="MP3 (*.mp3);;AAC (*.m4a)",
        lossy_title="Förlustformat",
        lossy_body=(
            "Du valde {fmt}-format.\n\n"
            "Komprimering med förlust (MP3/AAC) kan dämpa eller ta bort höga "
            "frekvenser och därmed påverka eller förstöra vattenmärket. "
            "WAV eller FLAC rekommenderas starkt för att behålla bilden klart synlig.\n\n"
            "Vill du exportera ändå?"
        ),
    )


def _en() -> UIStrings:
    return UIStrings(
        menu_view="View",
        menu_language="Language",
        lang_auto="System default",
        lang_sv="Swedish",
        lang_en="English",
        menu_help="Help",
        shortcuts_action="Keyboard shortcuts…",
        shortcuts_dialog_title="Keyboard shortcuts",
        shortcuts_dialog_body=(
            "• Open audio file — Ctrl+O\n"
            "• Choose image — Ctrl+I\n"
            "• Export audio — Ctrl+E\n"
            "• Play / stop — Space\n"
        ),
        menu_file="File",
        file_open="Open audio…",
        file_recent="Recent files",
        file_recent_empty="(no recent files)",
        file_recent_clear="Clear list",
        file_export="Export…",
        file_exit="Exit",
        recent_missing="File no longer exists: {path}",
        choose_audio="🎵  Choose audio file…",
        choose_audio_tooltip="Pick an audio file to embed the watermark in (Ctrl+O)",
        no_audio_loaded="No audio file loaded",
        preview_watermark="👁  Preview watermark",
        play_preview="▶  Play",
        stop_preview="■  Stop",
        play_tooltip="Play what the spectrogram shows (original or watermarked, Space).",
        play_needs_audio="Load an audio file before playing.",
        play_failed="Playback failed: {msg}",
        play_preparing="Preparing watermarked playback…",
        status_hint_drop="Drop an audio file and an image — then use 'Export'.",
        pick_audio_title="Choose audio file",
        pick_audio_filter="Audio files ({exts})",
        reading_file="Reading {name}…",
        load_audio_error="Could not load audio: {msg}",
        spectrogram_error="Spectrogram error: {msg}",
        audio_loaded_hint="Audio: {name} ({sr} Hz, {dur:.1f}s)",
        channels_abbr="ch",
        preview_error="Preview error: {msg}",
        export_need_source="Load an image or enter text under Image/Text first.",
        exporting="Exporting…",
        export_saved_status="Exported: {path}",
        export_error="Export error: {msg}",
        export_done_title="Done",
        export_done_body=(
            "Saved to:\n{path}\n\n"
            "Open the file in Audacity or Spek to see the watermark."
        ),
        export_done_open_audacity="Open in Audacity",
        export_done_show_folder="Show in folder",
        export_done_close="Close",
        audacity_not_found=(
            "Could not find an Audacity install. Install Audacity or open the file manually."
        ),
        save_preset_title="Save preset",
        preset_name_label="Name:",
        preset_saved="Preset '{name}' saved.",
        view_guide_copied="View guide copied to clipboard.",
        error_title="Error",
        view_guide_intro="How to reveal the watermark in the audio file:\n\n",
        view_guide_step1="1. Open the file in Audacity (or Spek / Sonic Visualiser).\n",
        view_guide_step2="2. Use the track menu → Spectrogram view.\n",
        view_guide_step3_header="3. Suggested settings:\n",
        view_guide_fft="   • FFT size: 4096\n",
        view_guide_window="   • Window: Hann\n",
        view_guide_dyn="   • Dynamic range: 80 dB\n",
        view_guide_time="4. Time range: {t0:.2f}s – {t1:.2f}s\n",
        view_guide_freq="5. Frequency range: {f0} Hz – {f1} Hz",
        group_mode="Mode",
        mode_invisible="Invisible (>15 kHz)",
        mode_full="Full range",
        group_placement="Placement",
        label_start="Start time:",
        label_duration="Duration:",
        label_fmin="Freq min:",
        label_fmax="Freq max:",
        label_strength="Strength:",
        group_bg="Background / mask",
        bg_alpha="Alpha channel (PNG)",
        bg_auto="Auto (corner sampling)",
        bg_white="Remove white",
        bg_black="Remove black",
        bg_chroma="Chroma key…",
        bg_luminance="Luminance",
        chroma_color_btn="Color…",
        chroma_pick_title="Pick chroma key color",
        chroma_current_tooltip="Current chroma key: {rgb}",
        label_method="Method:",
        label_threshold="Threshold:",
        invert="Invert",
        reset="Reset",
        save_preset="Save preset",
        view_guide_btn="📋 View guide",
        view_guide_tooltip=(
            "Copies instructions to the clipboard so viewers know "
            "which FFT settings reveal the watermark."
        ),
        export="💾  Export…",
        export_tooltip="Write the watermarked audio file (Ctrl+E)",
        tab_image="🖼  Image",
        tab_text="🅰  Text",
        pick_image="📁  Choose image…",
        pick_image_tooltip="Choose an image to paint into the spectrogram (Ctrl+I)",
        clear="Clear",
        no_image="No image selected",
        drop_png_here="Drop a PNG here",
        text_placeholder="Type text to paint into the spectrogram…",
        label_font_size="Font size:",
        label_letter_spacing="Letter spacing:",
        pick_image_title="Choose image",
        pick_image_filter="Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
        image_error="Error: {detail}",
        axis_frequency="Frequency",
        axis_time="Time",
        empty_spectrogram_hint="Drop an audio file or click 'Choose audio file…'",
        long_audio_title="Long audio file",
        long_audio_intro=(
            "{name}: about {minutes:.1f} min ({mb:.1f} MB).\n\n"
            "Decoding and building the spectrogram can take a while. "
            "You can load only a time range to work faster."
        ),
        long_audio_load_full="Load entire file",
        long_audio_load_first_n="Load only the first {sec} s",
        long_audio_load_range="Load a custom range",
        long_audio_range_start="Start at:",
        long_audio_range_length="Length:",
        audio_segment_badge=" · {start:.1f}–{end:.1f} s of {total:.1f} s",
        audio_probe_failed_detail=(
            "Could not read file metadata ({err}). Loading the full file — this may take a while."
        ),
        progress_loading_audio="Loading audio…",
        progress_spectrogram="Computing spectrogram…",
        export_dialog_title="Export audio",
        filter_lossless="WAV (*.wav);;FLAC (*.flac)",
        filter_lossy="MP3 (*.mp3);;AAC (*.m4a)",
        lossy_title="Lossy format",
        lossy_body=(
            "You chose {fmt}.\n\n"
            "Lossy compression (MP3/AAC) can attenuate or remove high "
            "frequencies and may damage or erase the watermark. "
            "WAV or FLAC is strongly recommended to keep the image clearly visible.\n\n"
            "Export anyway?"
        ),
    )


def ui_strings(lang: UiLang) -> UIStrings:
    return _sv() if lang == "sv" else _en()


def resolve_language(preference: str) -> UiLang:
    """preference: 'auto' | 'sv' | 'en' → resolved 'sv' | 'en'."""
    if preference == "sv":
        return "sv"
    if preference == "en":
        return "en"
    lang = QLocale.system().language()
    if lang == QLocale.Swedish:
        return "sv"
    return "en"


def export_filter_all(tr: UIStrings) -> str:
    return f"{tr.filter_lossless};;{tr.filter_lossy}"
