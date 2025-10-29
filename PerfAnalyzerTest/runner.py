from Cerbex.hook_loader import install_hooks
from Cerbex.analysis import TypeExtractor, PerfAnalyzer
# load your hooks in learn mode (writes dependencies.json, events.json, and prints perf/type)
install_hooks(config_path='config.json',analyses=[PerfAnalyzer(outfile='perf.log')], mode='learn')



import image_resizer
image_resizer.main()

