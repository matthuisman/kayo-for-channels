import requests
from time import time

CONFIG_URL = 'https://resources.kayosports.com.au/production/ios-android-assets/v2/config/metadata.json'
CLIENT_ID = 'a0n14xap7jreEXPfLo9F6JLpRp3Xeh2l'
FORMAT_HLS_TS = 'hls-ts'
FORMAT_HLS_TS_SSAI = 'ssai-hls-ts'
FORMAT_HLS_FMP4 = 'hls-fmp4'
FORMAT_HLS_FMP4_SSAI = 'ssai-hls-fmp4'
CDN_AKAMAI = 'AKAMAI'
CDN_CLOUDFRONT = 'CLOUDFRONT'
CDN_AUTO = 'AUTO'
CHANNELS_PANEL = 'lbEFg0xe1P'
CHNO_URL = 'https://i.mjh.nz/Kayo/app.json'

AVAILABLE_CDNS = [CDN_AKAMAI, CDN_CLOUDFRONT, CDN_AUTO]
SUPPORTED_FORMATS = [FORMAT_HLS_TS, FORMAT_HLS_TS_SSAI, FORMAT_HLS_FMP4, FORMAT_HLS_FMP4_SSAI]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36',
}

class Kayo(object):
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._auth_header = {}
        self._userdata = {}
        self._set_authentication()

    def _set_authentication(self):
        access_token = self._userdata.get('access_token')
        if not access_token:
            return

        self._auth_header = {'authorization': 'Bearer {}'.format(access_token)}
        self.logged_in = True

    def _oauth_token(self, data):
        try:
            token_data = self._session.post('https://auth.streamotion.com.au/oauth/token', json=data, headers={'User-Agent': 'okhttp/3.10.0'}).json()
        except:
            raise Exception('Unable to fetch token. Check your location is in Australia.')

        if 'error' in token_data:
            raise Exception(token_data.get('error_description'))

        self._userdata['access_token'] = token_data['access_token']
        if 'refresh_token' in token_data:
            self._userdata['refresh_token'] = token_data['refresh_token']

        self._set_authentication()
        return True, token_data

    def _refresh_token(self):
        payload = {
            'client_id': CLIENT_ID,
            'refresh_token': self._userdata.get('refresh_token'),
            'grant_type': 'refresh_token',
            'scope': 'openid offline_access drm:low email',
        }

        self._oauth_token(payload)
        print('Token Refreshed')

    def play(self, asset_id):
        self._refresh_token()

        params = {
            'fields': 'alternativeStreams,assetType,markers,metadata.isStreaming,metadata.drmContentIdAvc,metadata.sport',
        }

        data = self._session.post('https://vmndplay.kayosports.com.au/api/v1/asset/{asset_id}/play'.format(asset_id=asset_id), params=params, json={}, headers=self._auth_header).json()
        if ('status' in data and data['status'] != 200) or 'errors' in data:
            raise Exception(data.get('detail') or data.get('errors', [{}])[0].get('detail'))

        asset = data['data'][0]
        streams = [asset['recommendedStream']]
        streams.extend(asset['alternativeStreams'])
        streams = [s for s in streams if s['mediaFormat'] in SUPPORTED_FORMATS]
        if not streams:
            raise Exception('No streams found')

        data = self._session.get('https://cdnselectionserviceapi.kayosports.com.au/usecdn/mobile/LIVE', params={'sport': asset['metadata'].get('sport')}, headers=self._auth_header).json()
        prefer_cdn = data['useCDN']
        prefer_format = 'ssai-{}'.format(data['mediaFormat']) if data['ssai'] else data['mediaFormat']
        if prefer_format.startswith('ssai-'):
            print('Stream Format: Ignoring ssai format')
            prefer_format = prefer_format[5:]

        providers = [prefer_cdn]
        providers.extend([s['provider'] for s in streams])

        formats = [prefer_format]
        formats.extend(SUPPORTED_FORMATS)

        streams = sorted(streams, key=lambda k: (providers.index(k['provider']), formats.index(k['mediaFormat'])))
        stream = streams[0]
        url = stream['manifest']['uri']

        print(url)
        print('Stream CDN: {provider} | Stream Format: {mediaFormat}'.format(**stream))

        return url

    def live_channels(self):
        self._refresh_token()

        data = self._session.get('https://vccapi.kayosports.com.au/v2/content/types/carousel/keys/{}'.format(CHANNELS_PANEL)).json()
        live_data = self._session.get(CHNO_URL).json()

        channels = []
        for row in data[0]['contents']:
            if row['contentType'] != 'video':
                continue

            row['data']['chno'] = None
            if row['data']['asset']['id'] in live_data:
                row['data']['chno'] = live_data[row['data']['asset']['id']]['chno']

            channels.append(row['data'])

        return channels

    def login(self, username, password):
        print("logging in....")

        payload = {
            'client_id': CLIENT_ID,
            'username': username,
            'password': password,
            'audience': 'streamotion.com.au',
            'scope': 'openid offline_access drm:low email',
            'grant_type': 'http://auth0.com/oauth/grant-type/password-realm',
            'realm': 'prod-martian-database',
        }

        self._oauth_token(payload)
        self._refresh_token()
        print('Logged in!')
