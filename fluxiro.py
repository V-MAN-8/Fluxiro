import os
import sys
import shutil
from pathlib import Path
from urllib.parse import urlparse
import yt_dlp
import ssl
import certifi
import json
import urllib.request

class SocialMediaDownloader:
    def __init__(self, base_dir="downloads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.platform_configs = {}
        self.default_format = 'bestvideo*+bestaudio/best'
        self.ffmpeg_path = find_ffmpeg_path()
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    def _reddit_fallback_url(self, post_url):
        try:
            clean_url = post_url.split('?')[0].rstrip('/')
            api_url = clean_url + '.json'
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            }
            
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=180, context=self.ssl_context) as resp:
                content = resp.read()
                if resp.info().get('Content-Encoding') == 'gzip':
                    import gzip
                    content = gzip.decompress(content)
                data = json.loads(content.decode('utf-8'))
            
            post = data[0]['data']['children'][0]['data']
            
            rv = None
            if post.get('secure_media') and post['secure_media'].get('reddit_video'):
                rv = post['secure_media']['reddit_video']
            elif post.get('media') and post['media'].get('reddit_video'):
                rv = post['media']['reddit_video']
            
            if rv and rv.get('fallback_url'):
                return rv['fallback_url']
            return None
        except Exception:
            return None

    def _setup_ffmpeg_opts(self, opts):
        ff = find_ffmpeg_path()
        if ff:
            opts['ffmpeg_location'] = str(Path(ff).parent)
        opts['merge_output_format'] = 'mp4'
        pp_list = list(opts.get('postprocessors', []))
        if not any(pp.get('key') == 'FFmpegVideoRemuxer' for pp in pp_list):
            pp_list.append({'key': 'FFmpegVideoRemuxer', 'preferredformat': 'mp4'})
        opts['postprocessors'] = pp_list

    
    def sanitize_filename(self, filename):
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        filename = filename.encode('ascii', 'ignore').decode('ascii')
        filename = ' '.join(filename.split())
        return filename if filename else 'video'
    
    def get_platform_dir(self, platform):
        platform_dir = self.base_dir / platform
        platform_dir.mkdir(exist_ok=True)
        return platform_dir
    
    def get_ydl_opts(self, platform=None):
        if platform and platform != 'unknown':
            output_dir = self.get_platform_dir(platform)
        else:
            output_dir = self.get_platform_dir('other')
        
        base_opts = {
            'outtmpl': str(output_dir / '%(id)s.%(ext)s'),
            'progress_hooks': [self.progress_hook],
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'no_warnings': True,
            'quiet': True,
            'restrictfilenames': True,
            'windowsfilenames': True,
            'retries': 10,
            'fragment_retries': 10,
            'concurrent_fragment_downloads': 3,
            'continuedl': True,
            'ignore_no_formats_error': True,
            'noplaylist': True,
            'socket_timeout': 180,
            'geo_bypass': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            },
        }
        
        def _detect_js_runtimes():
            candidates = ["deno", "node", "quickjs", "gjs", "rhino"]
            return [r for r in candidates if shutil.which(r)]

        js_rt = _detect_js_runtimes()
        if js_rt:
            base_opts["js_runtimes"] = js_rt

        base_opts.setdefault("extractor_args", {})
        base_opts["extractor_args"].setdefault("youtube", {})
        base_opts["extractor_args"]["youtube"]["player_client"] = ["android", "tv"]

        if shutil.which('ffmpeg'):
            base_opts['merge_output_format'] = 'mp4'
            base_opts.setdefault('postprocessors', []).append({
                'key': 'FFmpegVideoRemuxer',
                'preferredformat': 'mp4'
            })

        return base_opts
    
    def progress_hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', 'N/A').strip()
            speed = d.get('_speed_str', 'N/A').strip()
            eta = d.get('_eta_str', 'N/A').strip()
            downloaded = d.get('_downloaded_bytes_str', '').strip()
            total = d.get('_total_bytes_str', '').strip()
            
            bar_length = 30
            try:
                percent_num = float(percent.replace('%', ''))
                filled = int(bar_length * percent_num / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
            except:
                bar = '░' * bar_length
            
            status = f"\r  Progress: [{bar}] {percent}"
            if downloaded and total:
                status += f" | {downloaded}/{total}"
            status += f" | Speed: {speed} | ETA: {eta}  "
            print(status, end='', flush=True)
        elif d['status'] == 'finished':
            print(f"\n  {'✓ Download completed! Processing...':<60}")
    
    def detect_platform(self, url):
        try:
            host = (urlparse(url).hostname or '').lower().strip('.')
            if not host:
                return 'unknown'
            parts = [p for p in host.split('.') if p]
            if len(parts) >= 2:
                name = parts[-2]
            else:
                name = parts[0]
            safe = ''.join(ch if ch.isalnum() or ch == '-' else '-' for ch in name)
            return safe or 'unknown'
        except Exception:
            return 'unknown'
    
    def download_video(self, url):
        try:
            platform = self.detect_platform(url)
            print(f"\n{'='*60}")
            print(f"URL: {url}")
            print(f"{'='*60}")
            
            base_opts = self.get_ydl_opts(platform)
            base_opts.setdefault('http_headers', {})['Referer'] = url
            ffmpeg_available = shutil.which('ffmpeg') is not None

            host = (urlparse(url).hostname or '').lower()
            
            if 'reddit.com' in host or 'v.redd.it' in host:
                fallback = self._reddit_fallback_url(url)
                if fallback:
                    print("\nUsing Reddit direct URL...")
                    url = fallback
                    opts = base_opts.copy()
                    opts['format'] = 'best'
                    if ffmpeg_available:
                        self._setup_ffmpeg_opts(opts)
                    
                    print("\nDownloading...")
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info)
                        print(f"\n✓ Successfully downloaded: {filename}")
                        return True

            opts = base_opts.copy()
            
            if ffmpeg_available:
                opts['format'] = 'bestvideo+bestaudio/best'
                self._setup_ffmpeg_opts(opts)
            else:
                opts['format'] = 'best'
            
            print("\nDownloading...")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info)
                        print(f"\n✓ Successfully downloaded: {filename}")
                        return True
                except Exception as e:
                    error_msg = str(e).lower()
                    if ('timed out' in error_msg or 'timeout' in error_msg) and attempt < max_retries - 1:
                        print(f"\n⚠ Connection timeout. Retrying ({attempt + 2}/{max_retries})...")
                        import time
                        time.sleep(2)
                        continue
                    raise
                
        except Exception as e:
            print(f"\n✗ Error downloading {url}: {str(e)}")
            return False
    
    def download_from_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            if not urls:
                print("No URLs found in file.")
                return
            print(f"\nFound {len(urls)} URLs to download\n")
            
            success = 0
            failed = 0
            
            for i, url in enumerate(urls, 1):
                print(f"\n[{i}/{len(urls)}] Processing: {url}")
                if self.download_video(url):
                    success += 1
                else:
                    failed += 1
            
            print(f"\n{'='*60}")
            print(f"Download Summary:")
            print(f"  Total: {len(urls)}")
            print(f"  Success: {success}")
            print(f"  Failed: {failed}")
            print(f"{'='*60}")
            
        except FileNotFoundError:
            print(f"Error: File '{filepath}' not found.")
        except Exception as e:
            print(f"Error reading file: {str(e)}")


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


def find_ffmpeg_path():
    import shutil as _shutil
    import os as _os
    import sys as _sys
    from glob import glob as _glob
    from pathlib import Path as _Path

    def _normalize(p):
        if not p:
            return None
        p = _os.path.expanduser(p)
        p = _os.path.expandvars(p)
        return _os.path.abspath(p)

    def _is_exec(path):
        return path and _os.path.isfile(path) and _os.access(path, _os.X_OK)

    p = _shutil.which('ffmpeg')
    if p:
        return p

    env_path = _normalize(_os.environ.get('FFMPEG_PATH'))
    if env_path:
        if _os.path.isdir(env_path):
            for name in ('ffmpeg', 'bin/ffmpeg', 'FFMPEG', 'bin/FFMPEG'):
                cand = _os.path.join(env_path, name)
                if _os.name == 'nt' and not cand.lower().endswith('.exe'):
                    cand_exe = cand + '.exe'
                    if _is_exec(cand_exe):
                        return cand_exe
                if _is_exec(cand):
                    return cand
        if _is_exec(env_path):
            return env_path
    env_dir = _normalize(_os.environ.get('FFMPEG_DIR'))
    if env_dir and _os.path.isdir(env_dir):
        for name in ('ffmpeg', 'bin/ffmpeg'):
            cand = _os.path.join(env_dir, name)
            if _os.name == 'nt' and not cand.lower().endswith('.exe'):
                cand_exe = cand + '.exe'
                if _is_exec(cand_exe):
                    return cand_exe
            if _is_exec(cand):
                return cand

    try:
        import imageio_ffmpeg as _iio
        exe = _iio.get_ffmpeg_exe()
        exe = _normalize(exe)
        if _is_exec(exe):
            return exe
    except Exception:
        pass

        for sp in list(_sys.path):
            bin_candidates = _glob(_os.path.join(sp, 'imageio_ffmpeg', 'binaries', 'ffmpeg*'))
            for bc in bin_candidates:
                bc = _normalize(bc)
                if _is_exec(bc):
                    return bc
    except Exception:
        pass

    candidates = []
    
    candidates.extend([
        '/opt/homebrew/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        '/opt/local/bin/ffmpeg',
        '/usr/bin/ffmpeg',
    ])
    candidates.extend(_glob('/opt/homebrew/Cellar/ffmpeg/*/bin/ffmpeg'))
    candidates.extend(_glob('/usr/local/Cellar/ffmpeg/*/bin/ffmpeg'))
    
    candidates.append(str(_Path(_sys.prefix) / 'bin' / 'ffmpeg'))
    
    if _os.name == 'nt':
        candidates.extend([
            'C:/ffmpeg/bin/ffmpeg.exe',
            'C:/Program Files/ffmpeg/bin/ffmpeg.exe',
            'C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe',
        ])
        try:
            import string
            for drive in string.ascii_uppercase:
                drive_root = f"{drive}:/"
                if _os.path.exists(drive_root):
                    candidates.extend(_glob(f"{drive_root}**/ffmpeg.exe", recursive=True))
        except Exception:
            pass
    
    candidates.extend([
        '/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        '/snap/bin/ffmpeg',
    ])
    
    try:
        for prefix in ['/usr', '/usr/local', '/opt', _os.path.expanduser('~')]:
            if _os.path.isdir(prefix):
                candidates.extend(_glob(f"{prefix}/**/ffmpeg", recursive=False))
                candidates.extend(_glob(f"{prefix}/*/*/ffmpeg", recursive=False))
                candidates.extend(_glob(f"{prefix}/*/*/*/ffmpeg", recursive=False))
    except Exception:
        pass
    
    try:
        import site
        for sp_dir in site.getsitepackages() + [site.getusersitepackages()]:
            if sp_dir and _os.path.isdir(sp_dir):
                candidates.extend(_glob(_os.path.join(sp_dir, '**/ffmpeg'), recursive=True))
                candidates.extend(_glob(_os.path.join(sp_dir, '**/ffmpeg-*'), recursive=True))
                if _os.name == 'nt':
                    candidates.extend(_glob(_os.path.join(sp_dir, '**/ffmpeg.exe'), recursive=True))
    except Exception:
        pass

    seen = set()
    for c in candidates:
        c = _normalize(c)
        if c and c not in seen:
            seen.add(c)
            if _is_exec(c):
                return c
    return None

def check_dependencies():
    try:
        import yt_dlp as _yd
    except Exception as e:
        print("Error: yt-dlp is not installed or failed to import.")
        print("Fix: pip install -U yt-dlp")
        raise
    ff = find_ffmpeg_path()
    if not ff:
        print("Warning: ffmpeg not found. Some sites (e.g., Reddit) may fail or skip merging.\nSet FFMPEG_PATH to the ffmpeg binary or add it to PATH to enable MP4 merging.")

def main():
    print_banner()
    check_dependencies()

    downloader = SocialMediaDownloader()
    
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
            if filepath:
                downloader.download_from_file(filepath)
            else:
                print("No file path provided.")
        
        elif choice == '3':
            print("\nThank you for using Fluxiro!")
            break
        
        else:
            print("\nInvalid choice. Please enter 1-3.")
        
        input("\nPress Enter to continue...")
        print("\n" + "="*60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user.")
        sys.exit(0)
