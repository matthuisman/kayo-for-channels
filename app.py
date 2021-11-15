#!/usr/bin/python3
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import requests
from kayo import Kayo

PORT = 80
CHUNKSIZE = 64 * 1024
PLAYLIST_URL = 'playlist.m3u'
EPG_URL = 'epg.xml'
PLAY_URL = 'play'
STATUS_URL = ''
EPG_SOURCE = 'https://i.mjh.nz/Kayo/epg.xml'

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        routes = {
            PLAYLIST_URL: self._playlist,
            EPG_URL: self._epg,
            PLAY_URL: self._play,
            STATUS_URL: self._status,
        }

        func = self.path.split('/')[1]
        if func not in routes:
            self.send_response(404)
            self.end_headers()
            return

        try:
            routes[func]()
        except Exception as e:
            self._error(e)

    def _error(self, message):
        self.send_response(500)
        self.end_headers()
        self.wfile.write(f'Error: {message}'.encode('utf8'))
        raise Exception(message)

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

        self.wfile.write(b'#EXTM3U\n')
        for row in kayo.live_channels():
            self.wfile.write(u'#EXTINF:-1 tvg-id="{id}" tvg-chno="{channel}" channel-id="kayo-{id}" tvg-logo="{logo}",{name}\nhttp://{host}/{PLAY_URL}/{id}\n'.format(
                id=row['asset']['id'], channel=row['chno'] or '', logo='{}?location=carousel-item&imwidth=415'.format(row['asset']['images']['defaultUrl']), name=row['asset']['title'], host=host, PLAY_URL=PLAY_URL).encode('utf8'))

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
    kayo.login(os.getenv('USERNAME', '').strip(), os.getenv('PASSWORD', '').strip())
    print("Starting server...")
    run()
