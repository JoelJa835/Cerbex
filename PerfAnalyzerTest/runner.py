
from pylya.hook_loader import install_hooks
from pylya.analysis import TypeExtractor, PerfAnalyzer
# load your hooks in learn mode (writes dependencies.json, events.json, and prints perf/type)
install_hooks(config_path='config.json',analyses=[PerfAnalyzer(outfile='perf.log')], mode='learn')
# install_hooks(config_path='config.json',analyses=[], mode='learn')
# install_hooks(mode='enforce',allowlist_path='allowlist.json')
# install_hooks(config_path='config.json',analyses=[AttrAccessAnalyzer(outfile='attr_access.log')], mode='learn')



import image_resizer
image_resizer.main()
# image_resizer.run()