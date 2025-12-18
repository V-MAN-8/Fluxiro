import os
import sys
import time
import shutil
from pathlib import Path
import yt_dlp
import ssl
import certifi


class VideoDownloader:
    def __init__(self, download_dir="downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self._last_percent = -1
        self._last_update_time = 0
        self._finished_count = 0
        self._progress_printed = False
    
    def get_ydl_opts(self):
        opts = {
            'outtmpl': str(self.download_dir / '%(extractor)s/%(id)s.%(ext)s'),
            
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            
            'merge_output_format': 'mp4',
            
            'nocheckcertificate': True,
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            
            'progress_hooks': [self.progress_hook],
            
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
        }
        
        ffmpeg = shutil.which('ffmpeg')
        if ffmpeg:
            opts['ffmpeg_location'] = str(Path(ffmpeg).parent)
        
        return opts
    
    def progress_hook(self, d):
        """Simple progress display"""
        if d['status'] == 'downloading':
            if self._finished_count > 0:
                return
            
            import time
            current_time = time.time()
            
            percent = d.get('_percent_str', 'N/A').strip()
            speed = d.get('_speed_str', 'N/A').strip()
            eta = d.get('_eta_str', 'N/A').strip()
            
            try:
                percent_num = float(percent.replace('%', ''))
                time_elapsed = current_time - self._last_update_time
                
                if (abs(percent_num - self._last_percent) < 10 and 
                    time_elapsed < 0.5 and percent_num < 99):
                    return
                
                self._last_percent = percent_num
                self._last_update_time = current_time
                
                bar_length = 30
                filled = int(bar_length * percent_num / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
            except:
                bar = '░' * 30
            
            if not self._progress_printed:
                print()
                self._progress_printed = True
            
            status = f"\r  Progress: [{bar}] {percent} | Speed: {speed} | ETA: {eta}"
            status = f"{status:<100}"
            print(status, end='', flush=True)
        
        elif d['status'] == 'finished':
            if self._finished_count == 0 and self._progress_printed:
                print(f"\n  ✓ Download completed! Processing...")
            self._finished_count += 1
    
    def reset_progress(self):
        self._last_percent = -1
        self._last_update_time = 0
        self._finished_count = 0
        self._progress_printed = False
    
    def download_video(self, url):
        try:
            self.reset_progress()
            
            print(f"\n{'='*60}")
            print(f"URL: {url}")
            print(f"{'='*60}")
            
            opts = self.get_ydl_opts()
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                print(f"\n✓ Successfully downloaded: {filename}")
                return True
        
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return False
    
    def download_bulk(self, urls):
        print(f"\n{'='*60}")
        print(f"Bulk Download - {len(urls)} videos")
        print(f"{'='*60}")
        
        success_count = 0
        fail_count = 0
        
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] Downloading: {url}")
            
            if self.download_video(url):
                success_count += 1
            else:
                fail_count += 1
            
            if i < len(urls):
                time.sleep(2)
        
        print(f"\n{'='*60}")
        print(f"Summary: {success_count} succeeded, {fail_count} failed")
        print(f"{'='*60}")


def print_banner():
    banner = """
=======================================================================================
       ▄████████  ▄█       ███    █▄  ▀████    ▐████▀  ▄█     ▄████████  ▄██████▄ 
      ███    ███ ███       ███    ███   ███▌   ████▀  ███    ███    ███ ███    ███
      ███    █▀  ███       ███    ███    ███  ▐███    ███▌   ███    ███ ███    ███
     ▄███▄▄▄     ███       ███    ███    ▀███▄███▀    ███▌  ▄███▄▄▄▄██▀ ███    ███
    ▀▀███▀▀▀     ███       ███    ███    ████▀██▄     ███▌ ▀▀███▀▀▀▀▀   ███    ███
      ███        ███       ███    ███   ▐███  ▀███    ███  ▀███████████ ███    ███
      ███        ███▌    ▄ ███    ███  ▄███     ███▄  ███    ███    ███ ███    ███
      ███        █████▄▄██ ████████▀  ████       ███▄ █▀     ███    ███  ▀██████▀ 
                 ▀                                           ███    ███           
                            Social Media Video Downloader
                    Downloads videos and shorts from any platform
                                Telegram: @V_MAN_8                                  
=======================================================================================
"""
    print(banner, flush=True)


def print_menu():
    print("  1. Download single video (paste URL)")
    print("  2. Download from text file (bulk download)")
    print("  3. Exit")
    print()


def main():
    print_banner()
    
    downloader = VideoDownloader()
    
    while True:
        print_menu()
        choice = input("Choice: ").strip()
        
        if choice == '1':
            url = input("\nEnter video URL: ").strip()
            if url:
                downloader.download_video(url)
            else:
                print("No URL provided.")
        
        elif choice == '2':
            filepath = input("\nEnter path to text file: ").strip()
            if filepath and os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    urls = [line.strip() for line in f if line.strip()]
                
                if urls:
                    downloader.download_bulk(urls)
                else:
                    print("No URLs found in file.")
            else:
                print("File not found.")
        
        elif choice == '3':
            print("\nThank you for using Fluxiro!")
            break
        
        else:
            print("\nInvalid choice. Please enter 1-3.")


if __name__ == "__main__":
    main()
