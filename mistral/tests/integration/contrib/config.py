import os
from oslo.config import cfg


mistral_group = cfg.OptGroup(name='mistral', title='mistral')

MistralGroup = [
    cfg.StrOpt('auth_url',
               default='http://127.0.0.1:5000/v2.0/',
               help="keystone url"),
    cfg.StrOpt('mistral_url',
               default='http://127.0.0.1:8084',
               help="mistral url"),
    cfg.StrOpt('user',
               default='admin',
               help="keystone user"),
    cfg.StrOpt('password',
               default='password',
               help="password for keystone user"),
    cfg.StrOpt('tenant',
               default='admin',
               help='keystone tenant'),
    cfg.BoolOpt('service_available',
                default='True',
                help='mistral available')
]


def register_config(config, config_group, config_opts):
    config.register_group(config_group)
    config.register_opts(config_opts, config_group)

path = os.path.join("%s/config.conf" % os.getcwd())

if os.path.exists(path):
    cfg.CONF([], project='mistralintegration', default_config_files=[path])

register_config(cfg.CONF, mistral_group, MistralGroup)

mistral = cfg.CONF.mistral
