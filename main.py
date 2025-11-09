# SaverX - Final Flet Application Code (Professional UI)
# Run: python3 saverx_flet_app.py

import flet as ft
import threading
import time
import webbrowser
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Callable

# Install yt-dlp: sudo pip3 install yt-dlp
import yt_dlp
import requests
import urllib.request
import pathlib
import traceback

print("SaverX: module imported — starting up", flush=True)

# --- Global Configuration ---
TELEGRAM_CHANNEL_URL = 'https://t.me/mtt_Trading7' # يجب استبدال هذا برابط قناة التلغرام الخاصة بك
DOWNLOADS_FOLDER_NAME = 'SaverX_Downloads'
YOUTUBE_ALLOWED = False # False للنسخة الآمنة على Google Play

# --- Colors and Styling (Based on Plan) ---
COLOR_BACKGROUND = ft.Colors.BLACK
COLOR_PRIMARY = ft.Colors.BLUE_ACCENT_700 # Sky Blue: #0A84FF
COLOR_SECONDARY = ft.Colors.GREY_800
COLOR_TEXT = ft.Colors.WHITE
COLOR_HINT = ft.Colors.GREY_500

# --- Data Model ---
@dataclass
class DownloadItem:
    title: str
    path: str
    url: str = ''
    progress: float = 0.0
    status: str = 'pending'  # pending, downloading, done, failed, error
    error: Optional[str] = None
    platform: str = ''
    timestamp: float = field(default_factory=time.time)

# Global list to hold download items
downloads: List[DownloadItem] = []

# --- Utility Functions ---
def get_downloads_folder() -> str:
    """الحصول على مسار مجلد التحميلات الافتراضي."""
    home = os.path.expanduser('~')
    if os.name == 'nt':
        base_dir = os.environ.get('USERPROFILE', home)
    else:
        base_dir = home
    
    downloads_path = os.path.join(base_dir, 'Downloads', DOWNLOADS_FOLDER_NAME)
    os.makedirs(downloads_path, exist_ok=True)
    return downloads_path

def is_youtube_url(url: str) -> bool:
    """التحقق مما إذا كان الرابط هو رابط يوتيوب."""
    return 'youtube.com' in url or 'youtu.be' in url

# --- Core Downloader Logic (using yt-dlp) ---
def download_video_yt_dlp(
    video_url: str, 
    save_path: str, 
    progress_cb: Callable[[float], None], 
    status_cb: Callable[[str], None]
) -> Optional[str]:
    """
    تحميل فيديو باستخدام yt-dlp مع تحديث شريط التقدم.
    :return: المسار النهائي للملف المحمل أو None في حالة الفشل.
    """
    
    if not YOUTUBE_ALLOWED and is_youtube_url(video_url):
        status_cb('فشل: التحميل من يوتيوب غير مسموح به في هذه النسخة.')
        return None

    # Use a single-file format selection to avoid requiring ffmpeg for merging
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [lambda d: _yt_dlp_hook(d, progress_cb, status_cb)],
    }

    try:
        status_cb('جاري التحضير للتحميل...')
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            final_path_template = ydl.prepare_filename(info)
            
            ydl.download([video_url])
            
            status_cb('اكتمل التحميل.')
            return final_path_template
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).split('\n')[-1].strip()
        status_cb(f'فشل التحميل: {error_msg}')
        return None
    except Exception as e:
        status_cb(f'خطأ غير متوقع: {e}')
        return None

def _yt_dlp_hook(d, progress_cb, status_cb):
    """Hook function to update progress and status."""
    if d['status'] == 'downloading':
        if d.get('total_bytes'):
            percent = d['downloaded_bytes'] / d['total_bytes']
            ft.app.page.run_thread(lambda: progress_cb(percent))
            speed = d.get('speed', 'N/A')
            if speed != 'N/A':
                speed = f"{d.get('speed_str', 'N/A')}"
            ft.app.page.run_thread(lambda: status_cb(f"جاري التحميل: {d['_percent_str']} بسرعة {speed}"))
        else:
            ft.app.page.run_thread(lambda: status_cb(f"جاري التحميل: {d['_percent_str']}"))
    elif d['status'] == 'finished':
        ft.app.page.run_thread(lambda: progress_cb(1.0))
        ft.app.page.run_thread(lambda: status_cb('اكتمل التحميل.'))
    elif d['status'] == 'error':
        ft.app.page.run_thread(lambda: status_cb('فشل التحميل.'))

# --- Flet UI Components ---

def create_platform_icon(page: ft.Page, icon_name: str, label: str, on_click_func: Callable):
    """إنشاء أيقونة منصة دائرية جذابة."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(name=icon_name, color=COLOR_TEXT, size=30),
                ft.Text(label, color=COLOR_TEXT, size=10, weight=ft.FontWeight.BOLD),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4
        ),
        width=70,
        height=70,
        border_radius=ft.border_radius.all(35),
        bgcolor=COLOR_PRIMARY,
        alignment=ft.alignment.center,
        on_click=on_click_func,
        tooltip=label
    )

def create_main_button(label: str, on_click_func: Callable):
    """إنشاء زر رئيسي أزرق."""
    return ft.Container(
        content=ft.Text(label, color=COLOR_TEXT, size=16, weight=ft.FontWeight.BOLD),
        alignment=ft.alignment.center,
        height=52,
        border_radius=ft.border_radius.all(12),
        bgcolor=COLOR_PRIMARY,
        on_click=on_click_func,
        ink=True
    )

def create_secondary_button(label: str, on_click_func: Callable):
    """إنشاء زر ثانوي رمادي."""
    return ft.Container(
        content=ft.Text(label, color=COLOR_TEXT, size=14, weight=ft.FontWeight.BOLD),
        alignment=ft.alignment.center,
        height=48,
        border_radius=ft.border_radius.all(12),
        bgcolor=COLOR_SECONDARY,
        on_click=on_click_func,
        ink=True
    )

# --- Flet Views (Screens) ---

class MainView(ft.View):
    def __init__(self, page: ft.Page):
        # build controls first, then initialize the View with controls to ensure rendering
        self.page = page
        self.url_input = ft.TextField(
            hint_text="رابط الفيديو (TikTok, Instagram, Facebook...)",
            text_align=ft.TextAlign.RIGHT,
            bgcolor=ft.Colors.GREY_900,
            border_radius=12,
            border_color=ft.Colors.TRANSPARENT,
            color=COLOR_TEXT,
            height=52,
            content_padding=15,
            cursor_color=COLOR_PRIMARY,
            selection_color=COLOR_PRIMARY,
            autofocus=True
        )
        # start download when user presses Enter
        self.url_input.on_submit = self.start_download_from_main
        # attempt to auto-start when a full URL is pasted
        def _on_change_auto_start(e):
            try:
                v = e.control.value.strip()
                if v and 'http' in v and len(v) > 10:
                    # small debounce: only trigger if looks like a full URL
                    self.start_download_from_main(None)
            except Exception:
                pass
        self.url_input.on_change = _on_change_auto_start
        # inline non-modal info area (no dialogs)
        self.inline_info = ft.Text("", color=COLOR_HINT, size=12, text_align=ft.TextAlign.RIGHT)
        controls = [
            # Header
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Text("S", color=COLOR_TEXT, size=24, weight=ft.FontWeight.BOLD),
                            width=48, height=48, border_radius=24, bgcolor=COLOR_PRIMARY, alignment=ft.alignment.center
                        ),
                        ft.Text("SaverX — تحميل الفيديو", color=COLOR_TEXT, size=20, weight=ft.FontWeight.BOLD),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                    spacing=12
                ),
                padding=ft.padding.only(bottom=20)
            ),
            self.inline_info,
            
            # Section 1: Platform Icons
            ft.Text("اختر منصة أو ألصق الرابط مباشرة", color=COLOR_HINT, size=14, text_align=ft.TextAlign.RIGHT),
            ft.Row(
                [
                    create_platform_icon(page, ft.Icons.VIDEOCAM, "تيك توك", lambda e: self.open_download_for("TikTok")),
                    create_platform_icon(page, ft.Icons.CAMERA_ALT, "انستغرام", lambda e: self.open_download_for("Instagram")),
                    create_platform_icon(page, ft.Icons.THUMB_UP, "فيسبوك", lambda e: self.open_download_for("Facebook")),
                    create_platform_icon(page, ft.Icons.CHAT, "تويتر", lambda e: self.open_download_for("Twitter (X)")),
                    create_platform_icon(page, ft.Icons.PIN_DROP, "بينترست", lambda e: self.open_download_for("Pinterest")),
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                wrap=True,
                spacing=16
            ),
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            
            # WhatsApp Status Downloader
            create_secondary_button("تحميل حالات واتساب (صور وفيديو)", self.show_whatsapp_status_info),
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            
            # Section 3: Direct Link Input
            ft.Text("أو ألصق رابط الفيديو هنا:", color=COLOR_HINT, size=14, text_align=ft.TextAlign.RIGHT),
            self.url_input,
            create_main_button("بدء التحميل الآن", self.start_download_from_main),
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            
            # Section 4: Navigation and Info
            ft.Row(
                [
                    ft.Container(expand=True, content=create_secondary_button("المزيد من الأدوات (Tools+)", lambda e: self.page.go("/tools"))),
                    ft.VerticalDivider(width=10, color=ft.Colors.TRANSPARENT),
                    ft.Container(expand=True, content=create_secondary_button("معرض التحميلات", lambda e: self.page.go("/gallery"))),
                ],
                spacing=12
            ),
            
            # Section 5: AdMob Placeholder and Info
            ft.Container(
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Text("إعلان AdMob (Banner Placeholder)", color=ft.Colors.GREY_600, size=12),
                            alignment=ft.alignment.center,
                            height=50,
                            bgcolor=ft.Colors.GREY_900
                        ),
                        ft.Text("نسخة متجر Google Play (آمنة) — لا تتضمن YouTube", color=COLOR_HINT, size=12, text_align=ft.TextAlign.RIGHT),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    spacing=5
                ),
                padding=ft.padding.only(top=20)
            )
        ]
        # initialize the base View with the controls list
        super().__init__(
            route="/",
            bgcolor=COLOR_BACKGROUND,
            scroll=ft.ScrollMode.ADAPTIVE,
            padding=ft.padding.all(16),
            controls=controls,
        )
        self.controls = controls

    def open_download_for(self, platform_name: str):
        self.page.session.set("platform_name", platform_name)
        self.page.go("/download")

    def start_download_from_main(self, e):
        url = self.url_input.value.strip()
        if not url:
            # show inline error on the input instead of a popup
            self.url_input.error_text = "الرجاء إدخال رابط فيديو صالح."
            self.inline_info.value = ""
            self.page.update()
            return
        # clear any previous error
        self.url_input.error_text = None
        self.inline_info.value = ""
        
        self.page.session.set("url_to_download", url)
        self.page.session.set("platform_name", "رابط مباشر")
        self.page.go("/download")

    def show_whatsapp_status_info(self, e):
        # show non-modal inline info instead of modal dialog
        msg = "ميزة تحميل حالات واتساب تتطلب صلاحية الوصول إلى مجلد حالات واتساب (عادةً في Android/Media/com.whatsapp/WhatsApp/Media/.Statuses). يرجى منح الصلاحية عند طلبها في التطبيق النهائي."
        self.inline_info.value = msg
        self.page.update()

    def close_dialog(self):
        # kept for compatibility but no-op (we don't use dialogs now)
        try:
            self.page.dialog.open = False
        except Exception:
            pass
        self.page.update()

class DownloadView(ft.View):
    def __init__(self, page: ft.Page):
        # build controls then init View with controls
        self.page = page
        self.url_input = ft.TextField(
            hint_text="ألصق رابط الفيديو هنا",
            text_align=ft.TextAlign.RIGHT,
            bgcolor=ft.Colors.GREY_900,
            border_radius=12,
            border_color=ft.Colors.TRANSPARENT,
            color=COLOR_TEXT,
            height=52,
            content_padding=15,
            cursor_color=COLOR_PRIMARY,
            selection_color=COLOR_PRIMARY,
            autofocus=True,
        )
        # support Enter to start and inline info (no pop-ups)
        self.url_input.on_submit = self.start_download
        self.inline_info = ft.Text("", color=COLOR_HINT, size=12, text_align=ft.TextAlign.RIGHT)
        self.status_text = ft.Text("", color=COLOR_TEXT, size=12, text_align=ft.TextAlign.RIGHT)
        self.progress_bar = ft.ProgressBar(width=float('inf'), value=0, color=COLOR_PRIMARY, bgcolor=ft.Colors.GREY_700)
        self.download_button = create_main_button("بدء التحميل", self.start_download)

        controls = [
            ft.Row(
                [
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.page.go("/")),
                    ft.Text(self.page.session.get("platform_name") or "تحميل الفيديو", color=COLOR_TEXT, size=18, weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=12,
            ),
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),

            # Input
            self.url_input,
            self.inline_info,

            # Info
            ft.Text("سيتم اختيار أفضل جودة متاحة تلقائيًا (MP4)", color=COLOR_HINT, size=12, text_align=ft.TextAlign.RIGHT),
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),

            # Button
            self.download_button,
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),

            # Status and Progress
            self.status_text,
            self.progress_bar,
            ft.Text("ملاحظة: قد يستغرق التحميل من 10 ثوانٍ إلى دقيقة حسب حجم الفيديو.", color=COLOR_HINT, size=10, text_align=ft.TextAlign.RIGHT),
        ]

        # initialize the base View with the controls list
        super().__init__(
            route="/download",
            bgcolor=COLOR_BACKGROUND,
            scroll=ft.ScrollMode.ADAPTIVE,
            padding=ft.padding.all(16),
            controls=controls,
        )
        self.controls = controls

    def did_mount(self):
        # Load URL if passed from main screen
        url = self.page.session.get("url_to_download")
        if url:
            self.url_input.value = url
            self.page.session.set("url_to_download", None) # Clear session
            # clear any previous errors
            self.url_input.error_text = None
            self.inline_info.value = ""
            self.page.update()

    def start_download(self, e):
        url = self.url_input.value.strip()
        if not url:
            # inline error instead of popup
            self.url_input.error_text = "الرجاء إدخال رابط فيديو صالح."
            self.inline_info.value = ""
            self.page.update()
            return
        
        self.download_button.disabled = True
        self.page.update()
        
        threading.Thread(target=self._download_thread, args=(url, self.page.session.get("platform_name")), daemon=True).start()

    def _download_thread(self, url, platform):
        downloads_dir = get_downloads_folder()
        
        item = DownloadItem(
            title=f"تحميل من {platform or 'رابط مباشر'}", 
            path='', 
            url=url, 
            status='downloading', 
            platform=platform
        )
        downloads.insert(0, item) # Add to global list
        
        def update_progress(progress):
            item.progress = progress
            self.progress_bar.value = progress
            self.page.update()

        def update_status(status):
            item.status = 'downloading'
            self.status_text.value = status
            # also append status to inline info so user sees all messages
            try:
                if self.inline_info.value:
                    self.inline_info.value = self.inline_info.value + "\n" + status
                else:
                    self.inline_info.value = status
            except Exception:
                pass
            self.page.update()

        final_path = download_video_yt_dlp(url, downloads_dir, update_progress, update_status)
        
        if final_path:
            item.status = 'done'
            item.title = os.path.basename(final_path)
            item.path = final_path
            self.status_text.value = 'اكتمل التحميل بنجاح!'
        else:
            item.status = 'error'
            item.error = self.status_text.value
            self.status_text.value = f'فشل: {item.error}'
        
        self.download_button.disabled = False
        self.page.update()

class GalleryView(ft.View):
    def __init__(self, page: ft.Page):
        # build controls then init view
        self.page = page
        self.downloads_list = ft.Column(spacing=10)
        self.inline_info_text = ft.Text("", color=COLOR_HINT, size=12, text_align=ft.TextAlign.RIGHT)
        
        controls = [
            # Header
            ft.Row(
                [
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.page.go("/")),
                    ft.Text("معرض التحميلات", color=COLOR_TEXT, size=18, weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=12
            ),
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            self.inline_info_text,
            self.downloads_list
        ]
        super().__init__(
            route="/gallery",
            bgcolor=COLOR_BACKGROUND,
            scroll=ft.ScrollMode.ADAPTIVE,
            padding=ft.padding.all(16),
            controls=controls,
        )
        self.controls = controls

    def did_mount(self):
        self.refresh_gallery()

    def refresh_gallery(self):
        self.downloads_list.controls.clear()
        
        sorted_downloads = sorted(downloads, key=lambda x: x.timestamp, reverse=True)
        
        for item in sorted_downloads:
            self.downloads_list.controls.append(self.create_download_list_item(item))
            
        self.page.update()

    def create_download_list_item(self, item: DownloadItem):
        
        def open_path(e):
            if not item.path or not os.path.exists(item.path):
                # inline, non-modal message
                self.inline_info_text.value = "لم يتم العثور على الملف. ربما تم حذفه."
                self.page.update()
                return
            webbrowser.open(item.path)

        def share_path(e):
            if not item.path or not os.path.exists(item.path):
                self.inline_info_text.value = "لم يتم العثور على الملف للمشاركة."
                self.page.update()
                return
            
            folder_path = os.path.dirname(item.path)
            webbrowser.open(folder_path)
            self.inline_info_text.value = "تم فتح مجلد التحميلات. يمكنك مشاركة الملف يدويًا."
            self.page.update()

        status_color = ft.Colors.GREEN_ACCENT_700 if item.status == 'done' else ft.Colors.RED_ACCENT_700 if item.status in ('failed', 'error') else ft.Colors.YELLOW_ACCENT_700
        status_text = {'done': 'مكتمل', 'downloading': 'جاري التحميل', 'failed': 'فشل', 'error': 'خطأ'}.get(item.status, 'قيد الانتظار')

        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(item.title, color=COLOR_TEXT, size=14, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT),
                            ft.Text(f"الحالة: {status_text}", color=status_color, size=10, text_align=ft.TextAlign.RIGHT),
                        ],
                        spacing=2,
                        expand=True,
                        horizontal_alignment=ft.CrossAxisAlignment.END
                    ),
                    ft.Column(
                        [
                            ft.IconButton(ft.Icons.OPEN_IN_NEW, on_click=open_path, disabled=item.status != 'done', tooltip="فتح الملف"),
                            ft.IconButton(ft.Icons.SHARE, on_click=share_path, disabled=item.status != 'done', tooltip="مشاركة الملف"),
                        ],
                        spacing=0
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.GREY_900,
            height=70
        )

class ToolsView(ft.View):
    def __init__(self, page: ft.Page):
        # build controls then initialize view
        self.page = page
        
        controls = [
            # Header
            ft.Row(
                [
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.page.go("/")),
                    ft.Text("المزيد من الأدوات (Tools+)", color=COLOR_TEXT, size=18, weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=12
            ),
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            
            # Content
            ft.Text("مزايا إضافية قيد التطوير:", color=COLOR_TEXT, size=16, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT),
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            ft.Text(
                "- دعم مواقع إضافية (مثل YouTube)\n- تحسين سرعة التحميل\n- خيارات جودة أعلى\n- أدوات مميزة حصرية",
                color=COLOR_HINT,
                size=14,
                text_align=ft.TextAlign.RIGHT,
                selectable=True
            ),
            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
            
            create_main_button("اضغط هنا للانتقال إلى صفحة مزايا إضافية", self.open_telegram),
            
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            ft.Text(
                "بالضغط على الزر أعلاه، ستنتقل إلى قناتنا على Telegram حيث يمكنك الحصول على النسخة الكاملة من التطبيق التي تدعم YouTube والمواقع الأخرى بدون قيود.",
                color=COLOR_HINT,
                size=12,
                text_align=ft.TextAlign.RIGHT,
                selectable=True
            )
        ]
        super().__init__(
            route="/tools",
            bgcolor=COLOR_BACKGROUND,
            scroll=ft.ScrollMode.ADAPTIVE,
            padding=ft.padding.all(16),
            controls=controls,
        )
        self.controls = controls

    def open_telegram(self, e):
        webbrowser.open(TELEGRAM_CHANNEL_URL)

# --- Main App Logic ---

def main(page: ft.Page):
    # Page Setup
    page.title = "SaverX - تحميل الفيديو"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = COLOR_BACKGROUND
    page.rtl = True # Enable Right-to-Left for Arabic
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = 0
    
    # Ensure local fonts exist and use them (use stdlib only: urllib.request + os)
    def ensure_fonts():
        print("SaverX: ensure_fonts() running...", flush=True)
        app_dir = os.path.dirname(os.path.abspath(__file__))
        fonts_dir = os.path.join(app_dir, 'fonts')
        os.makedirs(fonts_dir, exist_ok=True)

        # Map family name to remote TTF url and local filename
        font_map = {
            'Cairo': {
                'url': 'https://github.com/google/fonts/raw/main/ofl/cairo/Cairo-Regular.ttf',
                'file': os.path.join(fonts_dir, 'Cairo-Regular.ttf')
            },
            'NotoNaskhArabic': {
                'url': 'https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoNaskhArabic/NotoNaskhArabic-Regular.ttf',
                'file': os.path.join(fonts_dir, 'NotoNaskhArabic-Regular.ttf')
            }
        }

        fonts_loaded = {}
        for family, info in font_map.items():
            local_path = info['file']
            if not os.path.exists(local_path):
                try:
                    # Download using only stdlib
                    print(f"SaverX: downloading {family} from {info['url']}", flush=True)
                    urllib.request.urlretrieve(info['url'], local_path)
                    print(f"SaverX: saved font to {local_path}", flush=True)
                except Exception:
                    print(f"SaverX: failed to download font {family}:\n" + traceback.format_exc(), flush=True)
                    # If download fails, skip — Flet/Flutter will fallback to system fonts
                    continue
            # Add absolute path for Flet
            fonts_loaded[family] = local_path
        print(f"SaverX: fonts_loaded = {fonts_loaded}", flush=True)
        return fonts_loaded

    fonts_loaded = ensure_fonts()
    # If we downloaded or had local fonts, use them; else fallback to default
    if fonts_loaded:
        page.fonts = fonts_loaded
        # Prefer Arabic-capable font if available
        page.theme = ft.Theme(font_family=list(fonts_loaded.keys())[0])
    else:
        page.theme = ft.Theme(font_family="Cairo")
    page.update()

    def route_change(route):
        print(f"SaverX: route_change -> {page.route}", flush=True)
        page.views.clear()
        if page.route == "/":
            page.views.append(MainView(page))
        elif page.route == "/download":
            page.views.append(DownloadView(page))
        elif page.route == "/gallery":
            page.views.append(GalleryView(page))
        elif page.route == "/tools":
            page.views.append(ToolsView(page))
        page.update()

    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    
    # Initial setup
    get_downloads_folder()
    page.go(page.route)

    print("SaverX: main() completed setup; UI should be visible shortly", flush=True)

if __name__ == "__main__":
    # Launch native desktop app if available (user requested no web UI)
    print("SaverX: launching native desktop app if available...", flush=True)
    try:
        # prefer to run the Tkinter desktop app we added
        from desktop_app import SaverXApp
        app = SaverXApp()
        app.mainloop()
    except Exception as e:
        print("SaverX: failed to launch native desktop app:\n", e, flush=True)
        print("Falling back to Flet desktop/web UI...", flush=True)
        try:
            ft.app(target=main, view=ft.DESKTOP)
        except Exception as e2:
            print("SaverX: DESKTOP view failed, falling back to WEB_BROWSER:\n", e2, flush=True)
            ft.app(target=main, view=ft.WEB_BROWSER)
