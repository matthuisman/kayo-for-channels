#!/usr/bin/python3
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qsl

import requests
from kayo import Kayo

PORT = 80
USERNAME = os.getenv('USERNAME', '').strip()
PASSWORD = os.getenv('PASSWORD', '').strip()
CHUNKSIZE = 64 * 1024

PLAYLIST_URL = 'playlist.m3u'
EPG_URL = 'epg.xml'
PLAY_URL = 'play'
STATUS_URL = ''
EPG_SOURCE = 'https://i.mjh.nz/Kayo/epg.xml'

class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self._params = {}
        super().__init__(*args, **kwargs)

    def _error(self, message):
        self.send_response(500)
        self.end_headers()
        self.wfile.write(f'Error: {message}'.encode('utf8'))
        raise

    def do_GET(self):
        routes = {
            PLAYLIST_URL: self._playlist,
            EPG_URL: self._epg,
            PLAY_URL: self._play,
            STATUS_URL: self._status,
        }

        parsed = urlparse(self.path)
        func = parsed.path.split('/')[1]
        self._params = dict(parse_qsl(parsed.query, keep_blank_values=True))

        if func not in routes:
            self.send_response(404)
            self.end_headers()
            return

        try:
            routes[func]()
        except Exception as e:
            self._error(e)

    def _play(self):
        asset_id = self.path.split('/')[-1]
        url = kayo.play(asset_id)

        self.send_response(302)
        self.send_header('location', url)
        self.end_headers()

    def _epg(self):
        resp = requests.get(EPG_SOURCE)
        self.send_response(resp.status_code)
        self.send_header('content-type', resp.headers.get('content-type'))
        self.end_headers()
        if resp.ok:
            for chunk in resp.iter_content(CHUNKSIZE):
                self.wfile.write(chunk)
        else:
            self.wfile.write(f'{EPG_SOURCE} returned error {resp.status_code}'.encode('utf8'))

    def _playlist(self):
        host = self.headers.get('Host')
        self.send_response(200)
        self.end_headers()

        start_chno = int(self._params['start_chno']) if 'start_chno' in self._params else None
        include = [x for x in self._params.get('include', '').split(',') if x]
        exclude = [x for x in self._params.get('exclude', '').split(',') if x]

        self.wfile.write(b'#EXTM3U\n')
        for row in kayo.live_channels():
            channel_id = 'kayo-{}'.format(row['asset']['id'])
            if (include and channel_id not in include) or (exclude and channel_id in exclude):
                print(f"Skipping {channel_id} due to include / exclude")
                continue

            chno = ''
            if start_chno is not None:
                if start_chno > 0:
                    chno = f' tvg-chno="{start_chno}"'
                    start_chno += 1
            elif row.get('chno') is not None:
                chno = ' tvg-chno="{}"'.format(row['chno'])

            self.wfile.write(u'#EXTINF:-1 channel-id="{channel_id}" tvg-id="{id}" tvg-logo="{logo}"{chno},{name}\nhttp://{host}/{PLAY_URL}/{id}\n'.format(
                channel_id=channel_id, id=row['asset']['id'], logo='{}?location=carousel-item&imwidth=415'.format(row['asset']['images']['defaultUrl']), chno=chno,
                    name=row['asset']['title'], host=host, PLAY_URL=PLAY_URL).encode('utf8'))

    def _status(self):
        self.send_response(200)
        self.end_headers()
        host = self.headers.get('Host')
        self.wfile.write(f'Playlist URL: http://{host}/{PLAYLIST_URL}\nEPG URL: http://{host}/{EPG_URL}'.encode('utf8'))

class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    pass

def run():
    server = ThreadingSimpleServer(('0.0.0.0', PORT), Handler)
    server.serve_forever()

if __name__ == '__main__':
    kayo = Kayo()
    kayo.login(USERNAME, PASSWORD)
    print("Starting server...")
    run()
