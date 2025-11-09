#!/usr/bin/env python3
"""
SaverX - Native desktop prototype (Tkinter)

Run: python desktop_app.py

Provides a simple Arabic RTL-friendly desktop UI that accepts a video URL,
starts a background download via yt-dlp, and shows inline logs and progress.
This is a minimal, dependency-light alternative to the Flet/web UI.
"""
import threading
import queue
import os
import sys
import time
import webbrowser
from pathlib import Path
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import yt_dlp
except Exception:
    print("Please install yt-dlp: pip install yt-dlp", file=sys.stderr)
    raise

# --- Config ---
DOWNLOADS_FOLDER_NAME = 'SaverX_Downloads'
TELEGRAM_CHANNEL_URL = 'https://t.me/mtt_Trading7'


def get_downloads_folder():
    home = Path.home()
    downloads = home / 'Downloads' / DOWNLOADS_FOLDER_NAME
    downloads.mkdir(parents=True, exist_ok=True)
    return str(downloads)


# Official icon sources (we'll try clearbit's logo service which returns PNGs)
ICON_SOURCES = {
    'تيك توك': 'https://logo.clearbit.com/tiktok.com',
    'انستغرام': 'https://logo.clearbit.com/instagram.com',
    'فيسبوك': 'https://logo.clearbit.com/facebook.com',
    'تويتر': 'https://logo.clearbit.com/twitter.com',
    'سناب شات': 'https://logo.clearbit.com/snapchat.com',
    'لايكي': 'https://logo.clearbit.com/likee.com',
    'بنترست': 'https://logo.clearbit.com/pinterest.com',
}


def ensure_icons():
    """Download icons into python_ui/assets/icons/ and return a mapping label->local_path.
    If download fails for an icon, it will be omitted and the UI will fallback to drawn initials.
    """
    base_dir = Path(__file__).resolve().parent
    assets_dir = base_dir / 'assets' / 'icons'
    assets_dir.mkdir(parents=True, exist_ok=True)
    local_paths = {}

    for label, url in ICON_SOURCES.items():
        safe_name = label.replace(' ', '_') + '.png'
        dest = assets_dir / safe_name
        if dest.exists():
            local_paths[label] = str(dest)
            continue
        try:
            # use urllib.request to download PNG
            urllib.request.urlretrieve(url, str(dest))
            local_paths[label] = str(dest)
        except Exception:
            # skip if any error; UI will fallback
            try:
                if dest.exists():
                    dest.unlink()
            except Exception:
                pass
            continue

    return local_paths


from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class DownloadItem:
    id: int
    title: str
    url: str
    status: str = 'pending'
    progress: int = 0
    speed: str = ''
    eta: Optional[int] = None
    filepath: str = ''
    cancel_event: Optional[threading.Event] = None
    thread: Optional[threading.Thread] = None
    widgets: dict = field(default_factory=dict)


class SaverXApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('SaverX - تحميل الفيديو')
        self.geometry('760x520')
        # Right-to-left: we'll align text to the right where appropriate

        self.log_q = queue.Queue()
        self.event_q = queue.Queue()
        self.download_thread = None
        self.downloads: Dict[int, DownloadItem] = {}
        self._download_counter = 1
        # prepare icons (download official icons if available)
        try:
            self.icon_paths = ensure_icons()
        except Exception:
            self.icon_paths = {}
        self.icon_images: Dict[str, tk.PhotoImage] = {}

        # thumbnail sizing and fonts (smaller for a tighter layout)
        self.THUMB_SIZE = 40  # size of thumbnail square (canvas)
        self.THUMB_PADX = 8
        self.THUMB_LABEL_FONT = ('Arial', 9)
        self.ICON_FONT = ('Segoe UI Emoji', 12, 'bold')

        self._build_ui()
        self.after(200, self._flush_logs)

    def _build_ui(self):
        pad = 8
        # Header
        header = tk.Frame(self, bg='#0A84FF', height=60)
        header.pack(fill='x')
        lbl = tk.Label(header, text='SaverX — تحميل الفيديو', bg='#0A84FF', fg='white', font=('Arial', 16, 'bold'))
        lbl.pack(side='right', padx=12, pady=12)

        body = tk.Frame(self)
        body.pack(fill='both', expand=True, padx=pad, pady=pad)

        # Top controls: platform thumbnails (circular icon + label)
        topf = tk.Frame(body)
        topf.pack(fill='x')

        def _make_platform_thumb(parent, label, bg_color, symbol, cmd, text_color='white'):
            # container frame for icon + label
            f = tk.Frame(parent)
            # canvas circle for icon
            c = tk.Canvas(f, width=self.THUMB_SIZE, height=self.THUMB_SIZE, highlightthickness=0, bg=parent['bg'])
            c.pack()
            # draw circle background (keeps look if image has transparent background)
            margin = 4
            size = self.THUMB_SIZE - margin * 2
            c.create_oval(margin, margin, margin + size, margin + size, fill=bg_color, outline='')
            # try to show downloaded official icon if available
            try:
                icon_path = self.icon_paths.get(label)
            except Exception:
                icon_path = None

            if icon_path and os.path.exists(icon_path):
                try:
                    photo = tk.PhotoImage(file=icon_path)
                    # keep a reference to avoid garbage collection
                    self.icon_images[label] = photo
                    # place icon centered (may be larger/smaller; use as-is)
                    c.create_image(self.THUMB_SIZE // 2, self.THUMB_SIZE // 2, image=photo)
                except Exception:
                    # fallback to drawing symbol
                    c.create_text(self.THUMB_SIZE // 2, int(self.THUMB_SIZE * 0.65), text=symbol, fill=text_color, font=self.ICON_FONT)
            else:
                # draw symbol (emoji or letter) centered
                c.create_text(self.THUMB_SIZE // 2, int(self.THUMB_SIZE * 0.65), text=symbol, fill=text_color, font=self.ICON_FONT)
            # label under icon
            lbl = tk.Label(f, text=label, anchor='center', font=self.THUMB_LABEL_FONT, fg='#111111')
            lbl.pack(pady=(4,0))
            # click handling (frame, canvas, label)
            def _on_click(e=None):
                cmd(label)
            f.bind('<Button-1>', _on_click)
            c.bind('<Button-1>', _on_click)
            lbl.bind('<Button-1>', _on_click)
            return f

        # platform thumbnails: right-to-left layout
        # We'll use neutral initials (no official logos) to avoid copyright issues.
        thumbs = [
            ('تيك توك', '#010101', 'TT', self._platform_click, 'white'),
            ('انستغرام', '#C13584', 'IG', self._platform_click, 'white'),
            ('فيسبوك', '#1877F2', 'FB', self._platform_click, 'white'),
            ('تويتر', '#1DA1F2', 'TW', self._platform_click, 'white'),
            ('سناب شات', '#FFFC00', 'SN', self._platform_click, 'black'),
            ('لايكي', '#FF6B6B', 'LK', self._platform_click, 'white'),
            ('بنترست', '#E60023', 'PT', self._platform_click, 'white'),
        ]

        for label, color, sym, cmd, txt_color in thumbs:
            w = _make_platform_thumb(topf, label, color, sym, cmd, text_color=txt_color)
            w.pack(side='right', padx=self.THUMB_PADX)

        # URL entry and start
        entryf = tk.Frame(body)
        entryf.pack(fill='x', pady=(12, 6))
        self.url_var = tk.StringVar()
        self.url_entry = tk.Entry(entryf, textvariable=self.url_var, justify='right', font=('Arial', 12))
        self.url_entry.pack(side='right', fill='x', expand=True, padx=(6, 0))
        self.url_entry.bind('<Return>', lambda e: self.start_download())

        # Auto-start when a full URL is pasted into the entry (debounced)
        self._paste_after_id = None
        def _on_url_var_changed(*args):
            try:
                v = self.url_var.get().strip()
            except Exception:
                return
            if v and 'http' in v and len(v) > 10:
                if self._paste_after_id:
                    try:
                        self.after_cancel(self._paste_after_id)
                    except Exception:
                        pass
                self._paste_after_id = self.after(350, lambda: self._maybe_start_from_paste(v))

        try:
            # trace_add for Python 3.6+
            self.url_var.trace_add('write', _on_url_var_changed)
        except Exception:
            try:
                self.url_var.trace('w', _on_url_var_changed)
            except Exception:
                pass

        btn_start = tk.Button(entryf, text='بدء التحميل الآن', bg='#0A84FF', fg='white', command=self.start_download)
        btn_start.pack(side='right', padx=6)

        # Info / log area
        midf = tk.Frame(body)
        midf.pack(fill='both', expand=True)

        leftf = tk.Frame(midf)
        leftf.pack(side='left', fill='both', expand=True)

        lbl_status = tk.Label(leftf, text='سجل العمليات:', anchor='e')
        lbl_status.pack(fill='x')
        self.log_text = tk.Text(leftf, height=12, wrap='word', state='disabled', bg='#121212', fg='white')
        self.log_text.pack(fill='both', expand=True)

        # Progress
        pf = tk.Frame(leftf)
        pf.pack(fill='x', pady=(6, 0))
        self.progress = ttk.Progressbar(pf, orient='horizontal', mode='determinate')
        self.progress.pack(fill='x')

        # Gallery list (recent downloads)
        tk.Label(leftf, text='المعرض:', anchor='e').pack(fill='x', pady=(8, 0))
        self.gallery_list = tk.Listbox(leftf, height=6)
        self.gallery_list.pack(fill='x')
        self.gallery_list.bind('<Double-1>', self._open_selected)

        # Right side: downloads list and tools
        rightf = tk.Frame(midf, width=320)
        rightf.pack(side='right', fill='y', padx=(6, 0))

        tk.Label(rightf, text='التحميلات الجارية / المكتملة:', anchor='e').pack(fill='x')

        # stats
        statsf = tk.Frame(rightf)
        statsf.pack(fill='x', pady=(4, 6))
        self.lbl_total = tk.Label(statsf, text='إجمالي التحميلات: 0', anchor='e')
        self.lbl_total.pack(fill='x')

        # scrollable downloads area
        self.canvas = tk.Canvas(rightf, height=320)
        self.dl_scroll = tk.Scrollbar(rightf, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.dl_scroll.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.dl_scroll.pack(side='right', fill='y')

        self.dl_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.dl_frame, anchor='nw')
        self.dl_frame.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))

        tk.Button(rightf, text='تحديث المعرض', command=self.refresh_gallery).pack(fill='x', pady=(6, 2))
        tk.Button(rightf, text='المزيد من الأدوات (Tools+)', command=self._open_telegram).pack(fill='x')

        # load initial gallery
        self.refresh_gallery()

    def _platform_click(self, platform_name):
        self.url_var.set('')
        self._log(f'اخترت: {platform_name} — ألصق رابط الفيديو أو اضغط بدء.')

    def _open_telegram(self):
        webbrowser.open(TELEGRAM_CHANNEL_URL)

    def _open_selected(self, event=None):
        sel = self.gallery_list.curselection()
        if not sel:
            return
        path = self.gallery_list.get(sel[0])
        if os.path.exists(path):
            webbrowser.open(path)
        else:
            messagebox.showinfo('خطأ', 'الملف غير موجود')

    def refresh_gallery(self):
        folder = get_downloads_folder()
        files = sorted(Path(folder).glob('*'), key=os.path.getmtime, reverse=True)
        # keep gallery_list for backward compatibility
        try:
            self.gallery_list.delete(0, tk.END)
            for p in files:
                self.gallery_list.insert(tk.END, str(p))
        except Exception:
            pass

        # update stats
        self.lbl_total.config(text=f'إجمالي التحميلات: {len(files)}')

    def _log(self, msg):
        ts = time.strftime('%H:%M:%S')
        self.log_q.put(f'[{ts}] {msg}')

    def _flush_logs(self):
        # process both log messages (str) and event tuples from event_q
        try:
            while True:
                item = self.log_q.get_nowait()
                if isinstance(item, str):
                    self.log_text.config(state='normal')
                    self.log_text.insert('end', item + '\n')
                    self.log_text.see('end')
                    self.log_text.config(state='disabled')
                elif isinstance(item, tuple):
                    # tuple events already handled in event_q
                    pass
        except queue.Empty:
            pass

        try:
            while True:
                ev = self.event_q.get_nowait()
                # ev types: ('add', id, title), ('progress', id, percent, speed, eta), ('status', id, text), ('done', id, filepath)
                if not isinstance(ev, tuple):
                    continue
                typ = ev[0]
                if typ == 'add':
                    _, dlid, title = ev
                    self._add_download_row(dlid, title)
                elif typ == 'progress':
                    _, dlid, percent, speed, eta = ev
                    self._update_download_row(dlid, percent, speed, eta)
                elif typ == 'status':
                    _, dlid, text = ev
                    self._set_download_status(dlid, text)
                elif typ == 'done':
                    _, dlid, filepath = ev
                    self._set_download_done(dlid, filepath)
        except queue.Empty:
            pass

        self.after(200, self._flush_logs)

    def start_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showinfo('مطلوب', 'الرجاء إدخال رابط فيديو صالح')
            return
        # create a download item and UI row
        dlid = self._download_counter
        self._download_counter += 1
        item = DownloadItem(id=dlid, title='قيد التحضير...', url=url)
        # prepare cancellation event and store
        item.cancel_event = threading.Event()
        self.downloads[dlid] = item
        self.event_q.put(('add', dlid, item.title))
        self._log('بدء التحضير للتحميل...')
        t = threading.Thread(target=self._download_worker, args=(dlid, url), daemon=True)
        item.thread = t
        t.start()

    def _maybe_start_from_paste(self, v: str):
        # Only start if the current entry still matches the pasted value
        try:
            cur = self.url_var.get().strip()
        except Exception:
            return
        if cur != v:
            return
        # start download
        self.start_download()

    def _add_download_row(self, dlid, title):
        row = tk.Frame(self.dl_frame, pady=6)
        row.pack(fill='x', padx=6)
        lbl = tk.Label(row, text=title, anchor='e')
        lbl.pack(fill='x')
        pb = ttk.Progressbar(row, orient='horizontal', mode='determinate')
        pb.pack(fill='x', pady=4)
        status_lbl = tk.Label(row, text='قيد الانتظار', anchor='e')
        status_lbl.pack(fill='x')
        btn_row = tk.Frame(row)
        btn_row.pack(fill='x', pady=(4,0))
        open_btn = tk.Button(btn_row, text='فتح', command=lambda d=dlid: self._open_file(d))
        open_btn.pack(side='right')
        try:
            open_btn.config(state='disabled')
        except Exception:
            pass
        stop_btn = tk.Button(btn_row, text='إيقاف', command=lambda d=dlid: self._stop_download(d))
        stop_btn.pack(side='right', padx=(6,0))
        # store widgets
        self.downloads[dlid].filepath = ''
        self.downloads[dlid].status = 'downloading'
        self.downloads[dlid].progress = 0
        self.downloads[dlid].title = title
        self.downloads[dlid].widgets = {'frame': row, 'label': lbl, 'pb': pb, 'status': status_lbl, 'open_btn': open_btn, 'stop_btn': stop_btn}
        self.refresh_gallery()

    def _update_download_row(self, dlid, percent, speed, eta):
        item = self.downloads.get(dlid)
        if not item:
            return
        item.progress = percent
        item.speed = speed
        item.eta = eta
        w = item.widgets
        w['pb']['value'] = percent
        w['status'].config(text=f'{percent}%  •  {speed}  •  ETA: {eta}s' if eta else f'{percent}%  •  {speed}')
        try:
            # disable open button while downloading
            w['open_btn'].config(state='disabled')
        except Exception:
            pass

    def _set_download_status(self, dlid, text):
        item = self.downloads.get(dlid)
        if not item:
            return
        item.status = text
        try:
            item.widgets['status'].config(text=text)
        except Exception:
            pass
        # If cancelled or error, disable stop button
        try:
            if 'أُلغي' in str(text) or 'خطأ' in str(text) or 'فشل' in str(text):
                item.widgets.get('stop_btn') and item.widgets['stop_btn'].config(state='disabled')
        except Exception:
            pass

    def _stop_download(self, dlid):
        item = self.downloads.get(dlid)
        if not item:
            return
        # signal cancellation
        if item.cancel_event:
            item.cancel_event.set()
        else:
            # create and set to be safe
            ev = threading.Event()
            ev.set()
            item.cancel_event = ev
        # update UI immediately
        try:
            item.widgets['status'].config(text='تم إيقاف التحميل')
            item.widgets['stop_btn'].config(state='disabled')
        except Exception:
            pass
        self._log(f'تم إيقاف التحميل #{dlid} بواسطة المستخدم')

    def _set_download_done(self, dlid, filepath):
        item = self.downloads.get(dlid)
        if not item:
            return
        item.status = 'done'
        item.filepath = filepath
        try:
            item.widgets['status'].config(text='مكتمل')
            item.widgets['pb']['value'] = 100
            # enable open, disable stop
            item.widgets['open_btn'].config(state='normal')
            try:
                item.widgets['stop_btn'].config(state='disabled')
            except Exception:
                pass
        except Exception:
            pass
        self.refresh_gallery()

    def _open_file(self, dlid):
        item = self.downloads.get(dlid)
        if item and item.filepath and os.path.exists(item.filepath):
            webbrowser.open(item.filepath)
        else:
            messagebox.showinfo('خطأ', 'الملف غير متوفر بعد')

    def _download_worker(self, dlid, url):
        folder = get_downloads_folder()

        def progress_hook(d):
            status = d.get('status')
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed_str', '')
                eta = d.get('eta')
                if total:
                    perc = int(downloaded / total * 100)
                else:
                    perc = 0
                # check for cancellation
                itm = self.downloads.get(dlid)
                if itm and itm.cancel_event and itm.cancel_event.is_set():
                    # raise a controlled exception to stop yt-dlp
                    raise Exception('USER_CANCELLED')
                # send event
                self.event_q.put(('progress', dlid, perc, speed or '', eta))
                self.log_q.put(f"{d.get('_percent_str','?')} {d.get('filename','')}")
            elif status == 'finished':
                self.event_q.put(('status', dlid, 'finalizing'))

        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': os.path.join(folder, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'progress_hooks': [progress_hook],
            'quiet': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                self.event_q.put(('done', dlid, filepath))
                self.log_q.put(f'اكتمل التحميل: {os.path.basename(filepath)}')
        except Exception as e:
            # detect user cancellation
            msg = str(e)
            if 'USER_CANCELLED' in msg or (self.downloads.get(dlid) and self.downloads[dlid].cancel_event and self.downloads[dlid].cancel_event.is_set()):
                self.event_q.put(('status', dlid, 'أُلغي'))
                self.log_q.put(f'أُلغي التحميل #{dlid} بواسطة المستخدم')
            else:
                self.event_q.put(('status', dlid, f'خطأ: {e}'))
                self.log_q.put('فشل التحميل: ' + str(e))
        finally:
            self.refresh_gallery()


if __name__ == '__main__':
    app = SaverXApp()
    app.mainloop()
