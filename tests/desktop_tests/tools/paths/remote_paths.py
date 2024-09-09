# -*- coding: utf-8 -*-
from posixpath import join


class RemotePaths:
    home_dir = join('/home', "user")
    script_path = join(home_dir, 'script.sh')
    script_dir = join(home_dir, 'scripts')
    desktop_testing_path = join(script_dir, 'desktop_testing')
    report_dir = join(desktop_testing_path, 'reports')
    custom_config_path = join(script_dir, 'custom_config.json')
    tg_dir = join(home_dir, '.telegram')
    tg_token_file = join(tg_dir, 'token')
    tg_chat_id_file = join(tg_dir, 'chat')
    proxy_config_file = join(tg_dir, 'proxy.json')
    services_dir = join('/etc', 'systemd', 'system')
    my_service_name = 'myscript.service'
    my_service_path = join(services_dir, my_service_name)
    lic_file = join(script_dir, 'test_lic.lickey')
