# main.py
from pylya.hook_loader import install_hooks
from pylya.analysis import AttrAccessAnalyzer

install_hooks(
    config_path="config.json",
    mode="learn",
    analyses=[AttrAccessAnalyzer(outfile="attr.log")]
)

import config

cfg = config.Config()
print(cfg.host)     
print(cfg.url())   
print(cfg.debug)    