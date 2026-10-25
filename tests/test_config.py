import json

from tvhplayer.core.config import ConfigStore, default_config


def test_config_roundtrip_normalizes_servers(tmp_path):
    path = tmp_path / 'tvhplayer.conf'
    store = ConfigStore(path)
    store.servers = [{'name': 'box', 'url': 'http://127.0.0.1:9981'}]
    store.data['last_server'] = 0
    store.save()

    loaded = ConfigStore(path)
    assert loaded.servers[0]['protocol'] == 'http'
    assert loaded.servers[0]['htsp_port'] == 9982
    assert loaded.data['window_geometry']['width'] == 1200
    assert loaded.servers[0]['remember_subtitle_selection'] is False


def test_per_server_subtitle_defaults_persist_without_changing_other_servers(tmp_path):
    path = tmp_path / 'tvhplayer.conf'
    store = ConfigStore(path)
    store.servers = [
        {'name': 'NAS', 'url': 'http://10.0.1.243:9981', 'subtitle_language': 'Romanian',
         'remember_subtitle_selection': True},
        {'name': 'Other', 'url': 'http://127.0.0.1:9981'},
    ]
    store.save()
    reloaded = ConfigStore(path)
    assert reloaded.servers[0]['subtitle_language'] == 'ron'
    assert reloaded.servers[1]['subtitle_language'] == ''
    assert reloaded.servers[0]['remember_subtitle_selection'] is True
    assert reloaded.servers[1]['remember_subtitle_selection'] is False

    reloaded.servers[1]['subtitle_language'] = 'eng'
    reloaded.servers[1]['remember_subtitle_selection'] = True
    reloaded.save()
    again = ConfigStore(path)
    assert [server['subtitle_language'] for server in again.servers] == ['ron', 'eng']
    assert all(server['remember_subtitle_selection'] for server in again.servers)

    # Off is a valid persistent default, not the same as losing the preference.
    again.servers[0]['subtitle_language'] = ''
    again.save()
    assert ConfigStore(path).servers[0]['subtitle_language'] == ''
    assert ConfigStore(path).servers[0]['remember_subtitle_selection'] is True

    # Legacy and unknown options must not accidentally enable subtitles.
    again.servers = [{'name': 'Box', 'url': 'http://box', 'subtitle_language': 'unknown'}]
    again.save()
    assert ConfigStore(path).servers[0]['subtitle_language'] == ''



def test_subtitle_language_labels_and_matching():
    from tvhplayer.core.subtitle_preferences import (
        normalize_subtitle_language,
        preferred_subtitle_track,
        subtitle_track_language,
    )

    assert normalize_subtitle_language('Română') == 'ron'
    assert normalize_subtitle_language('rum') == 'ron'
    assert normalize_subtitle_language('English') == 'eng'
    assert normalize_subtitle_language('unsupported') == ''
    assert preferred_subtitle_track([(1, 'English [eng]'), (8, 'DVB Subtitles (ron)')], 'română') == 8
    assert preferred_subtitle_track([(2, 'Track 2'), (3, 'English')], 'ron') is None
    assert preferred_subtitle_track([(1, 'Programs'), (2, 'Portuguese')], 'ron') is None
    assert preferred_subtitle_track([(4, 'DVB - magyar')], 'hun') == 4
    assert subtitle_track_language('DVB Subtitle (rum)') == 'ron'
    assert subtitle_track_language('English [eng]') == 'eng'
    assert subtitle_track_language('Subtitle track 3') is None
    assert subtitle_track_language('Romanian / English') is None


def test_corrupt_config_falls_back_to_defaults(tmp_path):
    path = tmp_path / 'tvhplayer.conf'
    path.write_text('{not json', encoding='utf-8')
    store = ConfigStore(path)
    assert store.data['servers'] == []
    assert store.data['volume'] == default_config()['volume']


def test_missing_file_uses_defaults(tmp_path):
    store = ConfigStore(tmp_path / 'missing.conf')
    assert store.data == default_config()
    store.save()
    assert json.loads((tmp_path / 'missing.conf').read_text())['volume'] == 50


def test_playlists_are_saved_and_cleaned(tmp_path):
    path = tmp_path / 'tvhplayer.conf'
    path.write_text(json.dumps({'playlists': [
        {'name': 'ir', 'location': 'http://a/ir.m3u', 'server': 'builtin', 'muxes': {'id:a': 'm1'}},
        'junk',
    ]}), encoding='utf-8')
    store = ConfigStore(path)
    assert store.data['playlists'] == [{
        'name': 'ir',
        'location': 'http://a/ir.m3u',
        'server': 'builtin',
        'network_uuid': '',
        'muxes': {'id:a': 'm1'},
        'allow_commands': False,
        'tags': [],
    }]
